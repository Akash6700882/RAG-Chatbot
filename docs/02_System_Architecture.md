# 02 — System Architecture

## Architectural style

This is a **layered, modular-monolith** backend — one deployable FastAPI application, internally organized into clearly separated packages by responsibility (`auth`, `documents`, `chat`, `ingestion`, `vectorstore`, `rag`, `memory`, `db`, `core`). It is **not** microservices — there is one process, one database, one container for the app. That's a deliberate scope decision: a portfolio/demo project doesn't need distributed-systems complexity, and a modular monolith is easier to reason about, test, and deploy while still demonstrating clean separation of concerns.

Within that monolith, three design patterns recur intentionally:

| Pattern | Where | Why |
|---|---|---|
| **Strategy pattern** | `app/vectorstore/factory.py`, `app/rag/llm.py` | Vector backend (Chroma/FAISS) and LLM provider (Anthropic/Gemini/Groq) are each selected at runtime from one env var, behind one interface. Swapping either requires zero code changes elsewhere. |
| **State machine / orchestration graph** | `app/rag/graph.py` | The RAG pipeline is modeled as an explicit `StateGraph` with named nodes and conditional edges, not an implicit sequence of function calls — control flow (retries, fallback) is visible and independently testable. |
| **Dependency injection via FastAPI's `Depends`** | `app/auth/dependencies.py`, every router | Request-scoped resources (the current authenticated user, a DB session) are injected into route handlers by FastAPI's own dependency system — no custom DI container, because FastAPI's built-in one is sufficient and idiomatic. |

## High-level system diagram

See `Architecture_Diagrams/01_system_overview.md` for the Mermaid source. In prose:

1. A client (browser hitting `/ui`, Swagger UI at `/docs`, or a raw HTTP client) sends a request over HTTPS.
2. **NGINX** terminates TLS and reverse-proxies everything to the FastAPI app over the internal Docker network — NGINX is the *only* component with a port published to the host.
3. **FastAPI** routes the request through one of three routers (`auth`, `documents`, `chat`), each guarded by a JWT dependency where appropriate.
4. Document uploads flow through the **ingestion pipeline** into a **vector store**.
5. Chat requests flow through the **LangGraph RAG pipeline**, which reads from the vector store and calls out to an **LLM provider**.
6. All persistent state (users, document metadata, chat history) lives in **SQLite via SQLAlchemy**.

## Why NGINX sits in front instead of exposing FastAPI directly

Three real reasons, not just convention:

- **TLS termination** — Let's Encrypt certificates are configured once, in NGINX, rather than needing to be handled inside the Python process.
- **Single public surface** — only NGINX has a host port published in `docker-compose.yml`; the `api` container is reachable only from inside the Docker network. This was actually enforced by necessity (see `18_Debugging.md`, incident 1) and then kept because it's the correct pattern regardless.
- **Static asset / future scaling headroom** — NGINX can serve static files or front multiple app replicas later without touching application code.

## Data model

```
users            documents                chat_messages
─────            ─────────                ─────────────
id (PK)          id (PK)                  id (PK)
email (unique)   owner_id (FK → users)    owner_id (FK → users)
hashed_password  filename                 session_id
created_at       file_type                role ("user" | "assistant")
                 chunk_count              content
                 status                   created_at
                 created_at
```

`owner_id` is the load-bearing column of the entire security model: every document chunk stored in the vector database is tagged with it at ingestion time, and every retrieval query filters on it — so one user's uploaded content can never surface in another user's chat answers, even though they share the same vector store instance.

## Request/response contract

All API routes are versioned under `/api/v1`, return JSON, and use Pydantic schemas for both request validation and response serialization (see `05_Backend.md` and `11_APIs.md`). Auth-protected routes expect `Authorization: Bearer <jwt>`.

## Why this isn't over-engineered

A few things this project *deliberately does not* do, and why:

- **No microservices / message queue** — a single moderate-traffic demo doesn't need one, and adding one would obscure the actual point of the project (the RAG pipeline design) behind infrastructure ceremony.
- **No custom ORM or query builder** — SQLAlchemy's own session/query API is used directly; there's no repository-pattern abstraction layer on top of it, because the query surface is small enough that the extra indirection wouldn't pay for itself.
- **No frontend framework** — the demo UI is one static HTML file with vanilla JS `fetch()` calls (see `06_Frontend.md`). A SPA framework would add a build step and bundle complexity for a page with three forms and a chat log.
