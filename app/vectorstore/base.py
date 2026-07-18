"""Common interface implemented by every vector store backend.

Both backends apply metadata filtering themselves (rather than trusting
backend-specific `filter` kwargs) so retrieval scoping (e.g. by owner_id)
behaves identically regardless of which store is configured.
"""

from typing import Protocol

from langchain_core.documents import Document as LCDocument


class VectorStore(Protocol):
    def add_documents(self, documents: list[LCDocument], document_id: str) -> int: ...

    def similarity_search(
        self, query: str, k: int, filter: dict[str, str] | None = None
    ) -> list[LCDocument]: ...

    def delete(self, document_id: str) -> None: ...


def filter_documents_by_metadata(
    documents: list[LCDocument], filter: dict[str, str] | None
) -> list[LCDocument]:
    if not filter:
        return documents
    return [
        doc
        for doc in documents
        if all(doc.metadata.get(key) == value for key, value in filter.items())
    ]
