"""Node 5: Hallucination checking.

Fact-checks the generated answer against the retrieved context. Increments
retry_count on failure so the graph's conditional edge can bound how many
times generation is retried before falling back to a safe response.
"""

from app.rag.context import format_context
from app.rag.llm import get_llm
from app.rag.prompts import HALLUCINATION_CHECK_PROMPT
from app.rag.state import GraphState


def check_hallucination_node(state: GraphState) -> dict:
    context = format_context(state.get("retrieved_docs") or [])
    chain = HALLUCINATION_CHECK_PROMPT | get_llm()
    result = chain.invoke({"context": context, "answer": state["answer"]})
    verdict = (result.content or "").strip()
    is_grounded = verdict.upper().startswith("GROUNDED")

    return {
        "is_grounded": is_grounded,
        "hallucination_reason": "" if is_grounded else verdict,
        "retry_count": state.get("retry_count", 0) + (0 if is_grounded else 1),
    }
