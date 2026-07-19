# 17 — Performance

## Where the real costs are

For a RAG system, the expensive operations are, in order: (1) LLM inference calls (network round-trip + provider-side generation time), (2) embedding computation, (3) vector similarity search, (4) everything else (DB queries, JSON serialization) is comparatively free. Performance work here is concentrated exactly where the cost actually is.

## LLM call count per `/chat` request

The pipeline makes up to **4 LLM calls** per request in the worst case (rewrite, validate, generate, hallucination-check), and as few as **2** in the best case (first-turn question with sufficient context on the first try — rewrite is skipped, and no retry is needed). This is a direct, deliberate latency/correctness trade-off: each extra call adds real round-trip latency, but removing the validation or hallucination-check calls would remove exactly the verification that's the point of this project (see `07_RAG_Pipeline.md`). The `rewrite` node's conditional skip on turn one is the one "free" optimization already taken — no history exists yet to rewrite against, so the call is skipped entirely rather than run and discarded.

## Embedding: local and cached, not per-call API cost

`sentence-transformers/all-MiniLM-L6-v2` runs locally on CPU via `HuggingFaceEmbeddings`, cached process-wide with `@lru_cache` (`app/embeddings/huggingface.py`) — the model is loaded into memory exactly once per process, not once per request. There is no per-embedding API charge, unlike using a hosted embedding API — a deliberate cost-control choice for a project meant to be run and demoed repeatedly without accumulating usage fees.

## Chunk size as a performance/quality trade-off

`CHUNK_SIZE=1000`, `CHUNK_OVERLAP=150` (both configurable). Smaller chunks mean more precise retrieval (less irrelevant text riding along with the relevant sentence) but more chunks to search and more total embedding calls at ingestion time; larger chunks mean fewer, cheaper embeddings but more diluted, less precise context handed to the LLM. 1000/150 is a reasonable general-purpose default, not empirically tuned against a specific corpus — a real optimization pass would measure retrieval quality against a labeled Q&A set for the *actual* documents being served, not a generic guess.

## Vector search cost

Both backends over-fetch (`k * 4` candidates) before applying the owner-scope metadata filter in application code (`10_Vector_Database.md`) — a small, deliberate performance/correctness trade-off: fetching more than strictly needed guarantees enough post-filter results remain even when a user's documents are a minority of the total index, at the cost of a marginally larger initial search. At the corpus sizes this project targets (single-user demo scale), this is negligible; at real scale, a vector store with native, efficient metadata pre-filtering (rather than post-filtering an over-fetch) would be the correct next step.

## Async I/O — used, but not everywhere it could be

FastAPI is async-native, and I/O-bound framework operations (routing, request parsing) benefit from that automatically. However, most route handlers in this project are defined as regular (`def`, not `async def`) functions — FastAPI runs these in a thread pool rather than the event loop directly, which is *correct* here because the actual bottleneck operations (SQLAlchemy's synchronous session API, the synchronous LangChain/LangGraph call chain) aren't async-compatible without switching to async-flavored equivalents of each dependency. Making the whole stack async (async SQLAlchemy sessions, async LangChain runnables) would let a single process handle more concurrent slow-LLM-call requests without adding worker threads — a legitimate next optimization if concurrent load became a real requirement.

## Ingestion runs synchronously, in-request

`POST /upload` blocks until the entire load → split → embed → store pipeline finishes before responding (`05_Backend.md`, `11_APIs.md`). For the file sizes this project is demoed with, that's a sub-few-seconds wait — acceptable. For a large document or a slow embedding backend, this should move to a background task (FastAPI's `BackgroundTasks`, or a real task queue like Celery/RQ for anything needing retries or horizontal scaling) so the client gets an immediate "processing" response and polls or gets notified on completion — the `Document.status` field (`"processing" → "ready"/"failed"`) already exists specifically to support that future change without a schema migration.

## Docker image size vs. build/pull time

The ~2.6GB image size (`13_Docker.md`) directly affects deploy latency — every deploy pulls this whole image (mitigated somewhat by Docker layer caching, so unchanged layers aren't re-transferred). The CPU-only-torch-first trick already avoids a much larger CUDA-wheel alternative; a further optimization would be trimming unused transformers/sentence-transformers submodules, or moving to a smaller, distilled embedding model if the very slight quality trade-off were acceptable.

## Database: SQLite's real limits

SQLite handles the read-heavy, low-concurrency traffic of a demo deployment without issue, but it locks the entire database file during writes — under real concurrent multi-user write load (many simultaneous chat messages being saved), this becomes a genuine bottleneck. `DATABASE_URL` is the only thing that needs to change to move to Postgres; the SQLAlchemy models and queries themselves are already portable.
