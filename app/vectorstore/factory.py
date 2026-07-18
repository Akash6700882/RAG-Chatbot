"""Selects and caches the configured vector store backend.

Cached per (backend, path) so production reuses a single instance across
requests, while tests (which use a fresh tmp_path per test) transparently
get an isolated store.
"""

from typing import Any

from app.config import get_settings
from app.vectorstore.base import VectorStore

_store_cache: dict[tuple[str, str], Any] = {}


def get_vector_store() -> VectorStore:
    settings = get_settings()
    key = (settings.vector_db, settings.vector_db_path)

    if key not in _store_cache:
        if settings.vector_db == "chroma":
            from app.vectorstore.chroma_store import ChromaVectorStore

            _store_cache[key] = ChromaVectorStore()
        else:
            from app.vectorstore.faiss_store import FaissVectorStore

            _store_cache[key] = FaissVectorStore()

    return _store_cache[key]
