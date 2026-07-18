"""Integration tests for /register and /login."""

from fastapi.testclient import TestClient


def test_register_creates_user(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new-user@example.com", "password": "supersecret1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new-user@example.com"
    assert "id" in body


def test_register_duplicate_email_conflicts(client: TestClient):
    payload = {"email": "dup@example.com", "password": "supersecret1"}
    first = client.post("/api/v1/auth/register", json=payload)
    second = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 409


def test_login_success_returns_token(client: TestClient):
    payload = {"email": "login-user@example.com", "password": "supersecret1"}
    client.post("/api/v1/auth/register", json=payload)

    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_unauthorized(client: TestClient):
    payload = {"email": "wrongpass@example.com", "password": "supersecret1"}
    client.post("/api/v1/auth/register", json=payload)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@example.com", "password": "nope"},
    )
    assert response.status_code == 401


def test_login_unknown_email_unauthorized(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "whatever1"},
    )
    assert response.status_code == 401
