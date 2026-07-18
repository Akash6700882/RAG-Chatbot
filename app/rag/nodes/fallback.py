"""Safe-fallback node.

Reached when retrieved context is insufficient, or when the answer still
fails the hallucination check after the configured retry budget. Returns a
canned, honest "I don't know" response instead of ever surfacing an
ungrounded answer to the user.
"""

from app.rag.prompts import FALLBACK_ANSWER
from app.rag.state import GraphState


def fallback_node(state: GraphState) -> dict:
    return {"answer": FALLBACK_ANSWER, "is_grounded": True}
