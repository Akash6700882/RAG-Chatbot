"""Node 3: Context validation.

Judges whether the retrieved chunks actually contain enough information to
answer the question, before spending a generation call. If nothing was
retrieved at all, short-circuits without an LLM call — an empty context can
never be "sufficient".
"""

from app.rag.context import format_context
from app.rag.llm import get_llm
from app.rag.prompts import CONTEXT_VALIDATION_PROMPT
from app.rag.state import GraphState


def validate_context_node(state: GraphState) -> dict:
    docs = state.get("retrieved_docs") or []
    if not docs:
        return {"context_sufficient": False}

    context = format_context(docs)
    question = state.get("rewritten_query") or state["question"]
    chain = CONTEXT_VALIDATION_PROMPT | get_llm()
    result = chain.invoke({"question": question, "context": context})
    verdict = (result.content or "").strip().upper()
    return {"context_sufficient": verdict.startswith("SUFFICIENT")}
