"""Chunking of loaded documents via RecursiveCharacterTextSplitter."""

from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    settings = get_settings()
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def split_documents(documents: list[LCDocument]) -> list[LCDocument]:
    return get_text_splitter().split_documents(documents)
