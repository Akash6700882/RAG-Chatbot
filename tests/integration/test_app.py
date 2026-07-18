"""Integration tests for top-level app wiring: health, docs, OpenAPI schema."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_redirects_to_docs(client: TestClient):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/docs"


def test_openapi_schema_lists_expected_routes(client: TestClient):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]

    for expected_path in [
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/upload",
        "/api/v1/documents",
        "/api/v1/documents/{document_id}",
        "/api/v1/chat",
        "/api/v1/history",
    ]:
        assert expected_path in paths

    tag_names = {tag["name"] for tag in schema["tags"]}
    assert tag_names == {"system", "auth", "documents", "chat"}


def test_docs_ui_is_served(client: TestClient):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()
