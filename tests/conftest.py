"""Shared pytest fixtures: isolated test DB, fake embeddings, and FastAPI test client."""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")


class FakeEmbeddings(Embeddings):
    """Deterministic bag-of-words embedding stand-in, avoiding real model downloads in tests."""

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for word in text.lower().split():
            vector[hash(word) % self.dim] += 1.0
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


@pytest.fixture()
def client(monkeypatch, tmp_path) -> Generator[TestClient, None, None]:
    """A TestClient wired to an isolated SQLite DB, vector store dir, and fake embeddings."""
    db_file = tmp_path / "test.db"
    test_db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    monkeypatch.setenv("VECTOR_DB_PATH", str(tmp_path / "vectorstore"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))

    from app.config import get_settings

    get_settings.cache_clear()

    import app.db.session as db_session_module

    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    db_session_module.engine = engine
    db_session_module.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    from app.db.session import Base

    Base.metadata.create_all(bind=engine)

    fake_embeddings = FakeEmbeddings()
    import app.vectorstore.chroma_store as chroma_store_module
    import app.vectorstore.factory as factory_module
    import app.vectorstore.faiss_store as faiss_store_module

    monkeypatch.setattr(chroma_store_module, "get_embeddings", lambda: fake_embeddings)
    monkeypatch.setattr(faiss_store_module, "get_embeddings", lambda: fake_embeddings)
    factory_module._store_cache.clear()

    from app.main import create_app

    test_app = create_app()

    with TestClient(test_app) as test_client:
        yield test_client

    factory_module._store_cache.clear()
    get_settings.cache_clear()


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "supersecret1"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "supersecret1"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
