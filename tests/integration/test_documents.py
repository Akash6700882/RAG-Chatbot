"""Integration tests for /upload, GET /documents, DELETE /documents/{id}."""

import io

from fastapi.testclient import TestClient


def _upload_txt(client: TestClient, headers: dict[str, str], name: str = "notes.txt", text: str = "Hello world, this is a test document about refund policies."):
    return client.post(
        "/api/v1/upload",
        headers=headers,
        files={"file": (name, io.BytesIO(text.encode("utf-8")), "text/plain")},
    )


def test_upload_requires_auth(client: TestClient):
    response = _upload_txt(client, headers={})
    assert response.status_code == 401


def test_upload_txt_document_succeeds(client: TestClient, auth_headers: dict[str, str]):
    response = _upload_txt(client, auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "notes.txt"
    assert body["status"] == "ready"
    assert body["chunk_count"] >= 1


def test_upload_unsupported_extension_rejected(client: TestClient, auth_headers: dict[str, str]):
    response = client.post(
        "/api/v1/upload",
        headers=auth_headers,
        files={"file": ("malware.exe", io.BytesIO(b"binary"), "application/octet-stream")},
    )
    assert response.status_code == 415


def test_list_documents_returns_uploaded_files(client: TestClient, auth_headers: dict[str, str]):
    _upload_txt(client, auth_headers, name="doc1.txt")
    _upload_txt(client, auth_headers, name="doc2.txt")

    response = client.get("/api/v1/documents", headers=auth_headers)

    assert response.status_code == 200
    filenames = {doc["filename"] for doc in response.json()}
    assert filenames == {"doc1.txt", "doc2.txt"}


def test_documents_are_scoped_to_owner(client: TestClient, auth_headers: dict[str, str]):
    _upload_txt(client, auth_headers)

    client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "supersecret1"})
    login = client.post("/api/v1/auth/login", json={"email": "other@example.com", "password": "supersecret1"})
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/v1/documents", headers=other_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_delete_document_removes_it(client: TestClient, auth_headers: dict[str, str]):
    upload = _upload_txt(client, auth_headers)
    document_id = upload.json()["id"]

    delete_response = client.delete(f"/api/v1/documents/{document_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    list_response = client.get("/api/v1/documents", headers=auth_headers)
    assert list_response.json() == []


def test_delete_unknown_document_returns_404(client: TestClient, auth_headers: dict[str, str]):
    response = client.delete("/api/v1/documents/does-not-exist", headers=auth_headers)
    assert response.status_code == 404
