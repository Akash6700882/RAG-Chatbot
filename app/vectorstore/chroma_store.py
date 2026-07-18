"""ChromaDB-backed vector store implementation."""

from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document as LCDocument

from app.config import get_settings
from app.embeddings.huggingface import get_embeddings
from app.vectorstore.base import filter_documents_by_metadata


class ChromaVectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        Path(settings.vector_db_path).mkdir(parents=True, exist_ok=True)
        self._store = Chroma(
            collection_name="documents",
            embedding_function=get_embeddings(),
            persist_directory=settings.vector_db_path,
        )

    def add_documents(self, documents: list[LCDocument], document_id: str) -> int:
        if not documents:
            return 0
        ids = [f"{document_id}:{i}" for i in range(len(documents))]
        self._store.add_documents(documents, ids=ids)
        return len(documents)

    def similarity_search(
        self, query: str, k: int, filter: dict[str, str] | None = None
    ) -> list[LCDocument]:
        fetch_k = k * 4 if filter else k
        results = self._store.similarity_search(query, k=fetch_k)
        return filter_documents_by_metadata(results, filter)[:k]

    def delete(self, document_id: str) -> None:
        self._store.delete(where={"document_id": document_id})
