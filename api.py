"""Flask backend exposing the RAG agent over HTTP.

Run with: python api.py
Then open http://localhost:5000 in your browser (plain HTML/JS UI),
or run the React dev server separately (see frontend/README.md) and
it'll talk to this backend via CORS on port 5000.
"""

import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from config import settings
from rag.agent import RAGAgent
from rag.embedder import Embedder
from rag.retriever import Retriever
from rag.vector_store import VectorStore
from services.job_queue import enqueue_job, get_job, list_jobs

load_dotenv()

INDEX_PATH = settings.index_path
RAW_DIR = "data/raw"
ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".md", ".pdf"}


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="")
    CORS(app)

    agent = None

    # Initialize auth DB if configured
    if settings.db_url:
        try:
            from services.auth import init_db

            init_db(settings.db_url)
        except Exception:
            # auth DB initialization should not prevent app startup; log and continue
            pass

    def require_api_key(f):
        """Decorator to require an API key when DB is configured. If no DB, auth is disabled."""
        from functools import wraps
        from flask import g, abort
        from services.auth import verify_api_key

        @wraps(f)
        def wrapper(*args, **kwargs):
            # If no DB, allow for backward compatibility (tests/dev)
            if not settings.db_url:
                return f(*args, **kwargs)

            auth_header = request.headers.get("Authorization", "")
            token = None
            if auth_header.startswith("ApiKey "):
                token = auth_header[len("ApiKey "):].strip()
            elif auth_header.startswith("Bearer "):
                token = auth_header[len("Bearer "):].strip()
            else:
                token = request.headers.get("X-API-Key")

            if not token:
                return jsonify({"error": "Missing API key"}), 401

            ws = verify_api_key(token)
            if not ws:
                return jsonify({"error": "Invalid API key"}), 401

            # attach workspace to flask.g for handlers
            g.workspace = ws
            return f(*args, **kwargs)

        return wrapper

    def get_agent():
        nonlocal agent
        if agent is None:
            if not os.path.exists(INDEX_PATH):
                raise FileNotFoundError("No index found. Run scripts/build_index.py first.")

            embedder = Embedder()
            store = VectorStore.load(INDEX_PATH)
            retriever = Retriever(embedder, store)
            agent = RAGAgent(retriever)
        return agent

    @app.route("/")
    def index():
        return send_from_directory("static", "index.html")

    @app.route("/api/ask", methods=["POST"])
    def ask():
        data = request.get_json(force=True) or {}
        question = (data or {}).get("question", "").strip()
        history = (data or {}).get("history", [])

        if not question:
            return jsonify({"error": "No question provided."}), 400

        if not os.path.exists(INDEX_PATH):
            return jsonify({"error": "No index found. Run scripts/build_index.py first."}), 400

        try:
            answer = get_agent().answer(question, history=history)
            return jsonify({"answer": answer})
        except Exception as e:
            return jsonify({"error": "The assistant could not answer that question.", "detail": str(e)}), 500

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "index_exists": os.path.exists(INDEX_PATH),
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "documents_directory": RAW_DIR,
        })

    @app.route("/api/documents", methods=["GET"])
    def documents():
        if not os.path.exists(RAW_DIR):
            return jsonify({"documents": []})

        files = []
        for name in sorted(os.listdir(RAW_DIR)):
            if name.startswith("."):
                continue
            path = os.path.join(RAW_DIR, name)
            if os.path.isfile(path):
                files.append({
                    "name": name,
                    "size": os.path.getsize(path),
                    "type": os.path.splitext(name)[1].lower(),
                })
        return jsonify({"documents": files})

    @app.route("/api/documents/upload", methods=["POST"])
    @require_api_key
    def upload_documents():
        """Save uploaded files and enqueue an indexing job.

        This returns immediately with a job id the frontend can poll.
        """
        uploaded_files = request.files.getlist("files")
        if not uploaded_files:
            return jsonify({"error": "No files were provided."}), 400

        os.makedirs(RAW_DIR, exist_ok=True)

        saved_names = []
        for file in uploaded_files:
            if not file or not file.filename:
                continue

            original_name = secure_filename(file.filename)
            ext = os.path.splitext(original_name)[1].lower()
            if ext not in ALLOWED_UPLOAD_EXTENSIONS:
                return jsonify({"error": f"Unsupported file type: {ext or 'unknown'}"}), 400

            target_path = os.path.join(RAW_DIR, original_name)
            file.save(target_path)
            saved_names.append(original_name)

        if not saved_names:
            return jsonify({"error": "No valid files were saved."}), 400

        # Enqueue an indexing job instead of running synchronously
        try:
            job_id = enqueue_job("index", {"files": saved_names})
            return jsonify({
                "status": "queued",
                "job_id": job_id,
                "documents": saved_names,
            })
        except Exception as e:
            return jsonify({"error": "Failed to enqueue indexing job.", "detail": str(e)}), 500

    @app.route("/api/reindex", methods=["POST"])
    @require_api_key
    def reindex():
        try:
            from scripts.build_index import build_index
            result = build_index()
            return jsonify({
                "status": "ok",
                "documents": result.get("documents", 0),
                "chunks": result.get("chunks", 0),
                "index_path": result.get("index_path"),
            })
        except Exception as e:
            return jsonify({"error": "Index rebuild failed.", "detail": str(e)}), 500

    @app.route("/api/jobs", methods=["GET"])
    @require_api_key
    def list_all_jobs():
        jobs = list_jobs()
        return jsonify({"jobs": jobs})

    @app.route("/api/jobs/<job_id>", methods=["GET"])
    @require_api_key
    def job_status(job_id: str):
        job = get_job(job_id)
        if not job:
            return jsonify({"error": "Job not found."}), 404
        return jsonify({"job": job})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=settings.host, debug=settings.debug, port=settings.port)
