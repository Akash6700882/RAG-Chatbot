"""Unit tests for document loaders and text splitting."""

import pytest

from app.core.exceptions import UnsupportedFileTypeError
from app.ingestion.loaders import SUPPORTED_EXTENSIONS, load_document
from app.ingestion.splitter import split_documents


def test_load_txt_document(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text(
        "Hello world. This is a plain text test file.", encoding="utf-8"
    )

    docs = load_document(str(file_path))

    assert len(docs) == 1
    assert "Hello world" in docs[0].page_content


def test_load_markdown_document(tmp_path):
    file_path = tmp_path / "notes.md"
    file_path.write_text("# Title\n\nSome markdown content.", encoding="utf-8")

    docs = load_document(str(file_path))

    assert len(docs) == 1
    assert "markdown content" in docs[0].page_content


def test_load_unsupported_extension_raises(tmp_path):
    file_path = tmp_path / "notes.exe"
    file_path.write_text("binary-ish", encoding="utf-8")

    with pytest.raises(UnsupportedFileTypeError):
        load_document(str(file_path))


def test_supported_extensions_contains_required_formats():
    assert SUPPORTED_EXTENSIONS == {".pdf", ".docx", ".txt", ".md"}


def test_split_documents_respects_chunking(tmp_path, monkeypatch):
    monkeypatch.setenv("CHUNK_SIZE", "50")
    monkeypatch.setenv("CHUNK_OVERLAP", "10")

    from app.config import get_settings

    get_settings.cache_clear()

    file_path = tmp_path / "long.txt"
    file_path.write_text("word " * 200, encoding="utf-8")
    docs = load_document(str(file_path))

    chunks = split_documents(docs)

    assert len(chunks) > 1
    assert all(len(chunk.page_content) <= 60 for chunk in chunks)

    get_settings.cache_clear()
