"""Node 2: Retrieval.

Runs similarity search against the configured vector store, scoped to the
requesting user's own documents so no cross-tenant data ever reaches the
LLM context window.
"""

from app.config import get_settings
from app.rag.state import GraphState
from app.vectorstore.factory import get_vector_store


def retrieve_node(state: GraphState) -> dict:
    settings = get_settings()
    query = state.get("rewritten_query") or state["question"]
    store = get_vector_store()
    docs = store.similarity_search(
        query, k=settings.retrieval_top_k, filter={"owner_id": state["owner_id"]}
    )
    return {"retrieved_docs": docs}
