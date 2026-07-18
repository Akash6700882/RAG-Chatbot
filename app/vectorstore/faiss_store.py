"""FAISS-backed vector store implementation.

FAISS has no native concept of "delete by metadata", so a small JSON
manifest tracks which vector ids belong to which document_id, enabling
DELETE /documents/{id} to remove exactly the right vectors.
"""

import json
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument

from app.config import get_settings
from app.embeddings.huggingface import get_embeddings
from app.vectorstore.base import filter_documents_by_metadata


class FaissVectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        base_dir = Path(settings.vector_db_path)
        base_dir.mkdir(parents=True, exist_ok=True)

        self._index_dir = base_dir / "faiss_index"
        self._manifest_path = base_dir / "faiss_manifest.json"
        self._embeddings = get_embeddings()
        self._store: FAISS | None = None
        self._manifest: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        if self._index_dir.exists():
            self._store = FAISS.load_local(
                str(self._index_dir), self._embeddings, allow_dangerous_deserialization=True
            )
        if self._manifest_path.exists():
            self._manifest = json.loads(self._manifest_path.read_text())

    def _persist(self) -> None:
        if self._store is not None:
            self._store.save_local(str(self._index_dir))
        self._manifest_path.write_text(json.dumps(self._manifest))

    def add_documents(self, documents: list[LCDocument], document_id: str) -> int:
        if not documents:
            return 0
        ids = [f"{document_id}:{i}" for i in range(len(documents))]
        if self._store is None:
            self._store = FAISS.from_documents(documents, self._embeddings, ids=ids)
        else:
            self._store.add_documents(documents, ids=ids)
        self._manifest[document_id] = ids
        self._persist()
        return len(documents)

    def similarity_search(
        self, query: str, k: int, filter: dict[str, str] | None = None
    ) -> list[LCDocument]:
        if self._store is None:
            return []
        fetch_k = k * 4 if filter else k
        results = self._store.similarity_search(query, k=fetch_k)
        return filter_documents_by_metadata(results, filter)[:k]

    def delete(self, document_id: str) -> None:
        ids = self._manifest.pop(document_id, None)
        if ids and self._store is not None:
            self._store.delete(ids)
            self._persist()
