import { useState, useRef, useEffect } from "react";
import { marked } from "marked";

const API_URL = "/api/ask";
const UPLOAD_URL = "/api/documents/upload";

function Reticle() {
  return (
    <svg className="reticle" viewBox="0 0 40 40" aria-hidden="true">
      <circle className="reticle-ring reticle-ring-1" cx="20" cy="20" r="16" />
      <circle className="reticle-ring reticle-ring-2" cx="20" cy="20" r="16" />
      <line className="reticle-tick" x1="20" y1="2" x2="20" y2="8" />
      <line className="reticle-tick" x1="20" y1="32" x2="20" y2="38" />
      <line className="reticle-tick" x1="2" y1="20" x2="8" y2="20" />
      <line className="reticle-tick" x1="32" y1="20" x2="38" y2="20" />
      <circle className="reticle-core" cx="20" cy="20" r="2" />
    </svg>
  );
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);

  async function readJsonResponse(res) {
    const contentType = res.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) {
      const text = await res.text();
      throw new Error(text || `API returned ${res.status} ${res.statusText}`);
    }

    return res.json();
  }

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function handleFilesSelected(e) {
    const files = Array.from(e.target.files || []);
    setSelectedFiles(files);
  }

  async function handleUpload(e) {
    e?.preventDefault?.();
    if (!selectedFiles.length || uploading) return;

    setUploading(true);
    const formData = new FormData();
    selectedFiles.forEach((file) => formData.append("files", file));

    try {
      const res = await fetch(UPLOAD_URL, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const data = await readJsonResponse(res).catch(() => null);
        const message = data?.error || data?.detail || "Upload failed.";
        setMessages((prev) => [
          ...prev,
          { role: "assistant", text: message, id: crypto.randomUUID() },
        ]);
        return;
      }

      const data = await readJsonResponse(res);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Uploaded ${data.documents.join(", ")} and rebuilt the index with ${data.chunks} chunks.`,
          id: crypto.randomUUID(),
        },
      ]);
      setSelectedFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Upload failed: " + err.message, id: crypto.randomUUID() },
      ]);
    } finally {
      setUploading(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    const userMsg = { role: "user", text: question, id: crypto.randomUUID() };
    const history = messages.map((m) => ({
      role: m.role === "assistant" ? "assistant" : "user",
      content: m.text,
    }));

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history }),
      });

      if (!res.ok) {
        const data = await readJsonResponse(res).catch(() => null);
        const message = data?.error || data?.detail || "Something went wrong.";
        setMessages((prev) => [
          ...prev,
          { role: "assistant", text: message, id: crypto.randomUUID() },
        ]);
        return;
      }

      const data = await readJsonResponse(res);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.answer || data.error || "Something went wrong.",
          id: crypto.randomUUID(),
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Request failed: " + err.message, id: crypto.randomUUID() },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <div className="brand">
          <svg className="brand-mark" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="9" />
            <circle cx="12" cy="12" r="1.6" />
            <line x1="12" y1="1" x2="12" y2="5" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="1" y1="12" x2="5" y2="12" />
            <line x1="19" y1="12" x2="23" y2="12" />
          </svg>
          <h1>HUNTER AI</h1>
        </div>
        <span className="status">tracking · documents + live web</span>
      </header>

      <div className="chat">
        {messages.length === 0 && (
          <div className="empty-state">
            <Reticle />
            <p>Ask something. Hunter will track it down across your documents and the web.</p>
          </div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`msg ${m.role}`}
            dangerouslySetInnerHTML={{ __html: marked.parse(m.text) }}
          />
        ))}

        {loading && (
          <div className="msg assistant loading">
            <Reticle />
            <span>Tracking...</span>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      <form className="chat-form" onSubmit={handleSubmit}>
        <div className="upload-area">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".txt,.md,.pdf"
            onChange={handleFilesSelected}
          />
          <button type="button" className="secondary" onClick={() => fileInputRef.current?.click()}>
            Add docs
          </button>
          {selectedFiles.length > 0 && (
            <button type="button" className="secondary" onClick={handleUpload} disabled={uploading}>
              {uploading ? "Uploading..." : `Upload ${selectedFiles.length}`}
            </button>
          )}
        </div>

        <div className="ask-row">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask something..."
            autoComplete="off"
          />
          <button type="submit" disabled={loading}>
            Track
          </button>
        </div>
      </form>
    </div>
  );
}