"""Shared pytest fixtures: isolated test DB and FastAPI test client."""

import os
import tempfile
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")


@pytest.fixture()
def db_path(tmp_path) -> Generator[str, None, None]:
    path = tmp_path / "test.db"
    yield str(path)


@pytest.fixture()
def client(monkeypatch, tmp_path) -> Generator[TestClient, None, None]:
    """A TestClient wired to a fresh, isolated SQLite database per test."""
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
    db_session_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.db.session import Base

    Base.metadata.create_all(bind=engine)

    from app.main import create_app

    test_app = create_app()

    with TestClient(test_app) as test_client:
        yield test_client

    get_settings.cache_clear()


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    client.post("/api/v1/auth/register", json={"email": "test@example.com", "password": "supersecret1"})
    response = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "supersecret1"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
