"""Formatting of retrieved documents into an LLM-ready context block."""

from langchain_core.documents import Document as LCDocument


def format_context(docs: list[LCDocument]) -> str:
    if not docs:
        return "(no documents retrieved)"
    return "\n\n".join(
        f"[Source: {doc.metadata.get('filename', 'unknown')}]\n{doc.page_content}"
        for doc in docs
    )
