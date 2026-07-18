"""Node 1: Query rewriting.

Rewrites the latest user question into a standalone search query using
conversation history. Skipped on the first turn of a session (no history
to resolve pronouns against), saving an LLM call.
"""

from app.rag.llm import get_llm
from app.rag.prompts import QUERY_REWRITE_PROMPT
from app.rag.state import GraphState


def rewrite_node(state: GraphState) -> dict:
    history = state.get("chat_history") or []
    if not history:
        return {"rewritten_query": state["question"]}

    history_text = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
    chain = QUERY_REWRITE_PROMPT | get_llm()
    result = chain.invoke({"chat_history": history_text, "question": state["question"]})
    rewritten = (result.content or "").strip()
    return {"rewritten_query": rewritten or state["question"]}
