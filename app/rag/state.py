"""Shared state threaded through every node of the LangGraph RAG pipeline."""

from typing import TypedDict

from langchain_core.documents import Document as LCDocument


class GraphState(TypedDict, total=False):
    question: str
    owner_id: str
    chat_history: list[dict[str, str]]

    rewritten_query: str
    retrieved_docs: list[LCDocument]
    context_sufficient: bool

    answer: str
    is_grounded: bool
    hallucination_reason: str
    retry_count: int
