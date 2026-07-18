"""Format-aware document loading using LangChain community loaders."""

from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document as LCDocument

from app.core.exceptions import UnsupportedFileTypeError

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def load_document(file_path: str) -> list[LCDocument]:
    """Dispatches to the appropriate LangChain loader based on file extension."""
    suffix = Path(file_path).suffix.lower()

    if suffix == ".pdf":
        loader = PyPDFLoader(file_path)
    elif suffix == ".docx":
        loader = Docx2txtLoader(file_path)
    elif suffix in (".txt", ".md"):
        loader = TextLoader(file_path, encoding="utf-8")
    else:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix}'. Supported types: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    return loader.load()
