from io import BytesIO

from api import create_app


def test_health_endpoint_reports_runtime_state():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/health")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["status"] == "ok"
    assert "index_exists" in payload


def test_document_upload_endpoint_accepts_files():
    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/documents/upload",
        data={"files": (BytesIO(b"sample knowledge text"), "sample.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    # uploads are now enqueued; accept either immediate ok (legacy) or queued
    assert payload["status"] in ("ok", "queued")
    assert payload["documents"] == ["sample.txt"]
