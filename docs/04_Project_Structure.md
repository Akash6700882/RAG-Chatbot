# 04 — Project Structure (Folder-by-Folder, File-by-File)

```
RAG-Chatbot/
├── app/                     # the entire application
│   ├── main.py              # FastAPI app factory & entrypoint
│   ├── api.py                # aggregates all versioned routers
│   ├── config.py             # typed settings, read from .env
│   ├── core/                 # cross-cutting concerns
│   ├── db/                   # SQLAlchemy models + session
│   ├── auth/                 # register/login
│   ├── ingestion/            # document loading + chunking
│   ├── embeddings/           # embedding model factory
│   ├── vectorstore/          # Chroma/FAISS abstraction
│   ├── rag/                  # LangGraph pipeline
│   ├── memory/               # conversation history
│   ├── documents/            # upload/list/delete endpoints
│   ├── chat/                 # chat/history endpoints
│   └── static/               # the /ui demo frontend
├── tests/                    # unit + integration tests
├── deploy/                   # nginx config + EC2 deploy script + certbot bootstrap
├── .github/workflows/        # ci.yml, cd.yml
├── data/                     # sample docs, gitignored runtime data (uploads, vector index, sqlite file)
├── Dockerfile, docker-compose.yml, .dockerignore
├── requirements.txt, .env.example, .gitignore
└── README.md
```

## `app/main.py`

**Purpose**: the FastAPI application factory. Defines `create_app()`, which:
- Instantiates `FastAPI(...)` with title/description/version and OpenAPI tag metadata
- Adds CORS middleware
- Registers exception handlers (`app/core/exceptions.py`)
- Includes the aggregated router (`app/api.py`)
- Mounts the static frontend at `/ui`
- Defines `/` (redirects to `/ui`) and `/health`
- Runs `init_db()` and `configure_logging()` in a `lifespan` context manager on startup

**Imported by**: nothing inside `app/` — it's the top of the dependency graph. **Run by**: `uvicorn app.main:app`.

## `app/api.py`

**Purpose**: a single `APIRouter` with prefix `/api/v1` that includes the `auth`, `documents`, and `chat` routers. Exists so `main.py` has exactly one thing to `include_router()`, and so adding a new feature router later means touching one line here rather than `main.py` itself.

## `app/config.py`

**Purpose**: one `Settings` class (pydantic-settings `BaseSettings`) holding every environment-configurable value — LLM provider/keys, embedding model, vector DB choice, JWT secret, database URL, chunking parameters, retry limits. Cached via `@lru_cache` so `.env` is parsed once per process. **Imported by**: nearly every other module — this is the single source of runtime configuration.

## `app/core/`

| File | Purpose |
|---|---|
| `logging.py` | Configures the root logger's format and level once at startup; quiets noisy third-party loggers (httpx, chromadb, etc.) |
| `exceptions.py` | Defines `AppError` and typed subclasses (`NotFoundError`, `ConflictError`, `UnauthorizedError`, `UnsupportedFileTypeError`), each carrying an HTTP status code, plus the FastAPI exception handlers that turn them into JSON responses |
| `security.py` | `hash_password` / `verify_password` (bcrypt via passlib), `create_access_token` / `decode_access_token` (JWT via python-jose) |

## `app/db/`

| File | Purpose |
|---|---|
| `session.py` | SQLAlchemy `engine`, `SessionLocal`, the `Base` declarative class, `get_db()` (a FastAPI dependency yielding a session per request), and `init_db()` (creates tables on startup) |
| `models.py` | The three ORM models: `User`, `Document`, `ChatMessage` — see `02_System_Architecture.md` for the schema |

## `app/auth/`

| File | Purpose |
|---|---|
| `schemas.py` | Pydantic request/response models: `RegisterRequest`, `LoginRequest`, `UserResponse`, `TokenResponse` |
| `dependencies.py` | `get_current_user` — a FastAPI dependency that decodes the bearer token and loads the `User` row; every protected route depends on this |
| `router.py` | `POST /register`, `POST /login` |

## `app/ingestion/`

| File | Purpose |
|---|---|
| `loaders.py` | `load_document(path)` — dispatches to `PyPDFLoader` / `Docx2txtLoader` / `TextLoader` by file extension; raises `UnsupportedFileTypeError` for anything else |
| `splitter.py` | Wraps `RecursiveCharacterTextSplitter`, configured from `Settings.chunk_size` / `chunk_overlap` |
| `pipeline.py` | `ingest_file(...)` — the orchestration function: load → split → tag each chunk with `document_id`/`filename`/`owner_id` → hand off to the active vector store |

## `app/embeddings/huggingface.py`

**Purpose**: `get_embeddings()`, an `@lru_cache`d factory returning a `HuggingFaceEmbeddings` instance configured from `Settings.embedding_model`. Cached because loading the model is expensive and should happen once per process.

## `app/vectorstore/`

| File | Purpose |
|---|---|
| `base.py` | The `VectorStore` `Protocol` (structural interface) both backends satisfy, plus `filter_documents_by_metadata` — a shared post-search filter used by both backends so owner-scoping behaves identically regardless of backend |
| `chroma_store.py` | `ChromaVectorStore` — wraps `langchain_chroma.Chroma` |
| `faiss_store.py` | `FaissVectorStore` — wraps `langchain_community.vectorstores.FAISS`, plus a hand-rolled JSON manifest mapping `document_id → [vector ids]` so deletion is possible (FAISS has no native delete-by-metadata) |
| `factory.py` | `get_vector_store()` — returns the backend selected by `Settings.vector_db`, cached per `(backend, path)` so production reuses one instance while tests get isolated ones |

## `app/rag/` — the LangGraph pipeline (see `07`–`09` for full depth)

| File | Purpose |
|---|---|
| `state.py` | `GraphState` — the `TypedDict` threaded through every node |
| `context.py` | `format_context(docs)` — turns retrieved chunks into the context block injected into prompts |
| `prompts.py` | All four `ChatPromptTemplate`s (rewrite, validate, generate, hallucination-check) and the fixed `FALLBACK_ANSWER` string, centralized so wording can be tuned in one place |
| `llm.py` | `get_llm()` — the provider-switching factory described in `03_Tech_Stack.md` |
| `nodes/rewrite.py`, `retrieve.py`, `validate_context.py`, `generate.py`, `check_hallucination.py`, `fallback.py` | The six node functions (five pipeline stages + the safe-fallback node) |
| `graph.py` | `build_graph()` / `get_rag_graph()` — wires the nodes and conditional edges into a compiled `StateGraph` |

## `app/memory/conversation.py`

**Purpose**: `get_recent_history` (reads the last N turns for a session from `chat_messages`) and `save_message` — the DB-backed conversation memory fed into the rewrite node.

## `app/documents/` and `app/chat/`

The two remaining feature routers: `documents/router.py` (`POST /upload`, `GET /documents`, `DELETE /documents/{id}`) and `chat/router.py` (`POST /chat`, `GET /history`), each paired with a `schemas.py`. See `11_APIs.md` for full per-endpoint documentation.

## `app/static/index.html`

The entire `/ui` demo frontend — one file, no build step. See `06_Frontend.md`.

## `tests/`

`conftest.py` defines the shared `client` fixture (an isolated SQLite DB + vector store dir + fake embeddings per test) and `auth_headers`. `unit/` tests individual functions in isolation; `integration/` tests full HTTP request/response cycles through FastAPI's `TestClient`.

## `deploy/`

`nginx/rag-chatbot.conf` (the live reverse-proxy config, HTTPS-enabled), `nginx/init-letsencrypt.sh` (certificate bootstrap), `ec2/deploy.sh` (pull → retag → reload → health-check, run by the CD pipeline over SSH).

## Execution flow, top to bottom

1. `docker compose up` (or `uvicorn app.main:app` locally) starts the process.
2. `app/main.py` builds the app, which imports `app/api.py`, which imports every router, which import their respective `schemas.py`, `app/auth/dependencies.py`, `app/db/session.py`, and (for `chat`) `app/rag/graph.py`.
3. On startup, `init_db()` creates tables if they don't exist.
4. Each incoming request is routed by path/method to exactly one handler function, which depends on `get_db` and (if protected) `get_current_user`, then calls into `ingestion/`, `vectorstore/`, or `rag/` as appropriate.
