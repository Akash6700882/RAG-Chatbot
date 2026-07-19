# 09 — LangGraph

## Why a graph, and not just a Python function calling five other functions

You could write the RAG pipeline as one function that calls `rewrite()`, then `retrieve()`, then `validate()`, then `generate()`, then `check()`, in a straight line. The problem is the control flow isn't actually a straight line: **generation might need to run twice**, and **two different failure points both need to reach the same fallback**. Expressing "call `generate()` again, but only up to N times, and only from this one specific failure condition" as nested `if`/`while` statements gets tangled fast, and it's hard to unit-test one stage in isolation from the rest.

LangGraph's `StateGraph` makes the control flow a first-class, inspectable object: nodes are named, edges (including conditional ones) are declared explicitly, and the whole thing compiles into something you can visualize, trace, and test node-by-node.

## The actual graph, as built

```python
graph.set_entry_point("rewrite")
graph.add_edge("rewrite", "retrieve")
graph.add_edge("retrieve", "validate_context")
graph.add_conditional_edges(
    "validate_context", _route_after_validation,
    {"generate": "generate", "fallback": "fallback"},
)
graph.add_edge("generate", "check_hallucination")
graph.add_conditional_edges(
    "check_hallucination", _route_after_hallucination_check,
    {"end": END, "retry": "generate", "fallback": "fallback"},
)
graph.add_edge("fallback", END)
```

```
rewrite → retrieve → validate_context ─┬─ (sufficient) → generate → check_hallucination ─┬─ (grounded) → END
                                        │                                                  ├─ (ungrounded, retries left) → generate  [loop]
                                        └─ (insufficient) → fallback ← ────────────────────┘ (retries exhausted)
                                                              ↓
                                                             END
```

Two routing functions decide the conditional edges, and they are plain Python — no magic, fully unit-testable on their own:

```python
def _route_after_validation(state: GraphState) -> str:
    return "generate" if state.get("context_sufficient") else "fallback"

def _route_after_hallucination_check(state: GraphState) -> str:
    if state.get("is_grounded"):
        return "end"
    if state.get("retry_count", 0) >= get_settings().max_generation_retries:
        return "fallback"
    return "retry"
```

## `GraphState` — the shared state object

```python
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
    used_fallback: bool
```

Every node receives the *entire* state dict and returns a partial dict of just the keys it updates — LangGraph merges the returned keys into the running state before invoking the next node. This is why `retry_count` can be incremented by `check_hallucination_node` and still be visible when `_route_after_hallucination_check` runs immediately after, and why the router (`app/chat/router.py`) can read `result["used_fallback"]` after the whole graph finishes, regardless of which path was taken to get there.

## The retry loop, concretely

If `check_hallucination_node` determines an answer is ungrounded and the retry budget (`MAX_GENERATION_RETRIES`, default 2) isn't exhausted, the graph **loops back into `generate`** — not into `retrieve` or `validate` again, since the context itself wasn't the problem, the generation was. The regenerated prompt includes an explicit notice:

```python
regeneration_notice = REGENERATION_NOTICE if state.get("retry_count", 0) > 0 else ""
```

> "NOTE: Your previous answer was flagged as not fully supported by the context. Regenerate a stricter answer using only facts explicitly stated in the context below."

This is a small but meaningful detail: the second attempt isn't identical to the first with the same inputs (which would likely produce the same mistake) — it's explicitly told it failed a check and why.

## Compiling and caching the graph

```python
_compiled_graph: CompiledStateGraph | None = None

def get_rag_graph() -> CompiledStateGraph:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
```

The graph is built once per process (compiling wires up the node/edge structure) and reused for every request — there's no per-request graph-construction overhead, only per-request `graph.invoke(state)` calls.

## How this is tested without calling a real model

`tests/unit/test_rag_graph.py` builds a fresh graph and monkeypatches each node's `get_llm()` to return a `FakeListChatModel` with a scripted list of responses — e.g. `["UNGROUNDED: invented a number", "GROUNDED"]` for the hallucination-check node, verifying the graph actually loops back to `generate` exactly once and then exits, without ever making a network call. One subtle bug was caught this way during development: constructing the fake model fresh inside a `lambda` on every call reset its response index back to zero each time, masking the retry logic entirely — a shared instance had to be captured once and reused. See `18_Debugging.md`.
