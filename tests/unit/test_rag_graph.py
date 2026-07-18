"""Unit tests for individual RAG graph nodes and routing logic."""

from langchain_core.documents import Document as LCDocument
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.rag.graph import (
    _route_after_hallucination_check,
    _route_after_validation,
    build_graph,
)
from app.rag.nodes.fallback import fallback_node
from app.rag.nodes.rewrite import rewrite_node
from app.rag.nodes.validate_context import validate_context_node
from app.rag.prompts import FALLBACK_ANSWER


def test_rewrite_skips_llm_when_no_history():
    state = {"question": "What is the PTO policy?", "chat_history": []}
    result = rewrite_node(state)
    assert result == {"rewritten_query": "What is the PTO policy?"}


def test_rewrite_calls_llm_when_history_present(monkeypatch):
    import app.rag.nodes.rewrite as rewrite_module

    monkeypatch.setattr(
        rewrite_module,
        "get_llm",
        lambda: FakeListChatModel(responses=["standalone query"]),
    )
    state = {
        "question": "What about carryover?",
        "chat_history": [{"role": "user", "content": "What is the PTO policy?"}],
    }
    result = rewrite_node(state)
    assert result == {"rewritten_query": "standalone query"}


def test_validate_context_skips_llm_when_no_docs():
    result = validate_context_node({"question": "anything", "retrieved_docs": []})
    assert result == {"context_sufficient": False}


def test_validate_context_calls_llm_when_docs_present(monkeypatch):
    import app.rag.nodes.validate_context as validate_module

    monkeypatch.setattr(
        validate_module, "get_llm", lambda: FakeListChatModel(responses=["SUFFICIENT"])
    )
    docs = [
        LCDocument(
            page_content="PTO carries over up to 5 days.",
            metadata={"filename": "handbook.md"},
        )
    ]
    result = validate_context_node(
        {"question": "PTO carryover?", "retrieved_docs": docs}
    )
    assert result == {"context_sufficient": True}


def test_fallback_node_returns_canned_answer():
    result = fallback_node({})
    assert result == {"answer": FALLBACK_ANSWER, "is_grounded": True}


def test_route_after_validation():
    assert _route_after_validation({"context_sufficient": True}) == "generate"
    assert _route_after_validation({"context_sufficient": False}) == "fallback"


def test_route_after_hallucination_check_grounded():
    assert (
        _route_after_hallucination_check({"is_grounded": True, "retry_count": 0})
        == "end"
    )


def test_route_after_hallucination_check_retries(monkeypatch):
    monkeypatch.setenv("MAX_GENERATION_RETRIES", "2")
    from app.config import get_settings

    get_settings.cache_clear()
    assert (
        _route_after_hallucination_check({"is_grounded": False, "retry_count": 1})
        == "retry"
    )
    assert (
        _route_after_hallucination_check({"is_grounded": False, "retry_count": 2})
        == "fallback"
    )
    get_settings.cache_clear()


def test_graph_retries_generation_until_grounded(monkeypatch):
    """End-to-end graph test: first answer is flagged ungrounded, second passes."""
    import app.rag.graph as graph_module
    import app.rag.nodes.check_hallucination as hallucination_module
    import app.rag.nodes.generate as generate_module
    import app.rag.nodes.validate_context as validate_module

    # NOTE: each fake model is built once and captured by reference — get_llm() must
    # keep returning the *same* instance across calls, otherwise its response cycle
    # resets to index 0 on every invocation instead of advancing.
    docs = [
        LCDocument(
            page_content="PTO carries over up to 5 days.",
            metadata={"filename": "handbook.md"},
        )
    ]
    validate_llm = FakeListChatModel(responses=["SUFFICIENT"] * 5)
    generate_llm = FakeListChatModel(
        responses=["bad answer with made-up numbers", "good grounded answer"]
    )
    hallucination_llm = FakeListChatModel(
        responses=["UNGROUNDED: invented a number", "GROUNDED"]
    )

    monkeypatch.setattr(
        graph_module, "retrieve_node", lambda state: {"retrieved_docs": docs}
    )
    monkeypatch.setattr(validate_module, "get_llm", lambda: validate_llm)
    monkeypatch.setattr(generate_module, "get_llm", lambda: generate_llm)
    monkeypatch.setattr(hallucination_module, "get_llm", lambda: hallucination_llm)

    graph = build_graph()
    result = graph.invoke(
        {
            "question": "PTO carryover?",
            "owner_id": "user-1",
            "chat_history": [],
            "retry_count": 0,
        }
    )

    assert result["answer"] == "good grounded answer"
    assert result["is_grounded"] is True
    assert result["retry_count"] == 1


def test_graph_falls_back_when_context_insufficient(monkeypatch):
    import app.rag.graph as graph_module

    monkeypatch.setattr(
        graph_module, "retrieve_node", lambda state: {"retrieved_docs": []}
    )

    graph = build_graph()
    result = graph.invoke(
        {
            "question": "Unrelated question?",
            "owner_id": "user-1",
            "chat_history": [],
            "retry_count": 0,
        }
    )

    assert result["answer"] == FALLBACK_ANSWER
    assert result["context_sufficient"] is False
