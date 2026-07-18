"""Integration tests for /chat and /history, with the LLM nodes mocked out
(no real Anthropic API calls in CI)."""

import io

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

HANDBOOK_TEXT = (
    "Remote Work Policy\n"
    "Employees may work remotely up to 3 days per week, subject to manager approval.\n\n"
    "Paid Time Off\n"
    "Full-time employees accrue 18 days of PTO per year. Unused PTO up to 5 days may be "
    "carried over into the next calendar year."
)


@pytest.fixture()
def mock_rag_llms(monkeypatch):
    import app.rag.nodes.check_hallucination as hallucination_module
    import app.rag.nodes.generate as generate_module
    import app.rag.nodes.rewrite as rewrite_module
    import app.rag.nodes.validate_context as validate_module

    fakes = {
        "rewrite": FakeListChatModel(responses=["What is the PTO carryover policy?"] * 10),
        "validate": FakeListChatModel(responses=["SUFFICIENT"] * 10),
        "generate": FakeListChatModel(
            responses=["Employees can carry over up to 5 PTO days (handbook.txt)."] * 10
        ),
        "hallucination": FakeListChatModel(responses=["GROUNDED"] * 10),
    }
    monkeypatch.setattr(rewrite_module, "get_llm", lambda: fakes["rewrite"])
    monkeypatch.setattr(validate_module, "get_llm", lambda: fakes["validate"])
    monkeypatch.setattr(generate_module, "get_llm", lambda: fakes["generate"])
    monkeypatch.setattr(hallucination_module, "get_llm", lambda: fakes["hallucination"])
    return fakes


def _upload_handbook(client: TestClient, headers: dict[str, str]):
    return client.post(
        "/api/v1/upload",
        headers=headers,
        files={"file": ("handbook.txt", io.BytesIO(HANDBOOK_TEXT.encode("utf-8")), "text/plain")},
    )


def test_chat_requires_auth(client: TestClient):
    response = client.post("/api/v1/chat", json={"message": "hi"})
    assert response.status_code == 401


def test_chat_with_no_documents_returns_safe_fallback(client: TestClient, auth_headers: dict[str, str]):
    """No documents uploaded -> empty retrieval -> fallback node, with zero LLM calls."""
    response = client.post(
        "/api/v1/chat", headers=auth_headers, json={"message": "What is the PTO policy?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "don't have enough information" in body["answer"]
    assert body["sources"] == []


def test_chat_after_upload_returns_grounded_answer(
    client: TestClient, auth_headers: dict[str, str], mock_rag_llms
):
    _upload_handbook(client, auth_headers)

    response = client.post(
        "/api/v1/chat", headers=auth_headers, json={"message": "How many PTO days carry over?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Employees can carry over up to 5 PTO days (handbook.txt)."
    assert body["sources"] == ["handbook.txt"]
    assert body["session_id"]


def test_chat_maintains_session_history(client: TestClient, auth_headers: dict[str, str], mock_rag_llms):
    _upload_handbook(client, auth_headers)

    first = client.post(
        "/api/v1/chat", headers=auth_headers, json={"message": "How many PTO days carry over?"}
    )
    session_id = first.json()["session_id"]

    second = client.post(
        "/api/v1/chat",
        headers=auth_headers,
        json={"message": "And what about remote work?", "session_id": session_id},
    )
    assert second.json()["session_id"] == session_id

    history_response = client.get(
        f"/api/v1/history?session_id={session_id}", headers=auth_headers
    )
    assert history_response.status_code == 200
    messages = history_response.json()
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]


def test_history_requires_auth(client: TestClient):
    response = client.get("/api/v1/history")
    assert response.status_code == 401


def test_history_is_scoped_to_owner(client: TestClient, auth_headers: dict[str, str]):
    client.post("/api/v1/chat", headers=auth_headers, json={"message": "hello"})

    client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "supersecret1"})
    login = client.post("/api/v1/auth/login", json={"email": "other@example.com", "password": "supersecret1"})
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/v1/history", headers=other_headers)
    assert response.status_code == 200
    assert response.json() == []
