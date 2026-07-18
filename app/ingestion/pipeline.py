"""End-to-end ingestion: load -> split -> embed -> store."""

from app.ingestion.loaders import load_document
from app.ingestion.splitter import split_documents
from app.vectorstore.factory import get_vector_store


def ingest_file(file_path: str, document_id: str, filename: str, owner_id: str) -> int:
    """Loads, chunks, and indexes a file. Returns the number of chunks stored."""
    raw_documents = load_document(file_path)
    chunks = split_documents(raw_documents)

    for chunk in chunks:
        chunk.metadata["document_id"] = document_id
        chunk.metadata["filename"] = filename
        chunk.metadata["owner_id"] = owner_id

    store = get_vector_store()
    return store.add_documents(chunks, document_id=document_id)
