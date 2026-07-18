"""Node 4: Answer generation.

Generates a grounded answer strictly from retrieved context. When re-entered
after a failed hallucination check, injects a stricter regeneration notice
into the prompt instead of silently retrying with the same instructions.
"""

from app.rag.context import format_context
from app.rag.llm import get_llm
from app.rag.prompts import ANSWER_GENERATION_PROMPT, REGENERATION_NOTICE
from app.rag.state import GraphState


def generate_node(state: GraphState) -> dict:
    context = format_context(state.get("retrieved_docs") or [])
    question = state.get("rewritten_query") or state["question"]
    regeneration_notice = REGENERATION_NOTICE if state.get("retry_count", 0) > 0 else ""

    chain = ANSWER_GENERATION_PROMPT | get_llm()
    result = chain.invoke(
        {"context": context, "question": question, "regeneration_notice": regeneration_notice}
    )
    return {"answer": (result.content or "").strip()}
