"""LangGraph StateGraph wiring the RAG pipeline:

    rewrite -> retrieve -> validate_context -+-> generate -> check_hallucination -+-> END
                                              |                                   |
                                              +-> fallback <----------------------+ (retries exhausted)
                                                     |
                                                    END

validate_context routes straight to `fallback` when retrieval came back
empty or irrelevant, so we never attempt to generate from nothing.
check_hallucination loops back into `generate` (bounded by
MAX_GENERATION_RETRIES) before giving up and returning the safe fallback.
"""

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.config import get_settings
from app.rag.nodes.check_hallucination import check_hallucination_node
from app.rag.nodes.fallback import fallback_node
from app.rag.nodes.generate import generate_node
from app.rag.nodes.retrieve import retrieve_node
from app.rag.nodes.rewrite import rewrite_node
from app.rag.nodes.validate_context import validate_context_node
from app.rag.state import GraphState


def _route_after_validation(state: GraphState) -> str:
    return "generate" if state.get("context_sufficient") else "fallback"


def _route_after_hallucination_check(state: GraphState) -> str:
    if state.get("is_grounded"):
        return "end"
    if state.get("retry_count", 0) >= get_settings().max_generation_retries:
        return "fallback"
    return "retry"


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("rewrite", rewrite_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("validate_context", validate_context_node)
    graph.add_node("generate", generate_node)
    graph.add_node("check_hallucination", check_hallucination_node)
    graph.add_node("fallback", fallback_node)

    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "validate_context")
    graph.add_conditional_edges(
        "validate_context",
        _route_after_validation,
        {"generate": "generate", "fallback": "fallback"},
    )
    graph.add_edge("generate", "check_hallucination")
    graph.add_conditional_edges(
        "check_hallucination",
        _route_after_hallucination_check,
        {"end": END, "retry": "generate", "fallback": "fallback"},
    )
    graph.add_edge("fallback", END)

    return graph.compile()


_compiled_graph: CompiledStateGraph | None = None


def get_rag_graph() -> CompiledStateGraph:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
