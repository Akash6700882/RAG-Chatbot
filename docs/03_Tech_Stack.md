# 03 — Technology Stack

Every dependency in `requirements.txt`, what it's for, and why it was chosen over an alternative.

## Web framework

| Library | Role | Why this, not an alternative |
|---|---|---|
| **FastAPI** | HTTP framework, routing, dependency injection, OpenAPI generation | Async-native, Pydantic-integrated request/response validation, and automatic interactive docs (`/docs`, `/openapi.json`) for free — no separate Swagger/OpenAPI tooling needed. Chosen over Flask (no built-in async or validation) and Django (too much unused batteries — no admin site, no templating, no ORM needed beyond SQLAlchemy). |
| **Uvicorn** | ASGI server | The standard production server for FastAPI; runs the async event loop FastAPI is built on. |
| **Pydantic v2** | Data validation & settings | Used both for request/response schemas (`app/*/schemas.py`) and typed application settings (`app/config.py` via `pydantic-settings`). Rejects malformed input before it reaches business logic. |
| **python-multipart** | Multipart form parsing | Required by FastAPI to accept file uploads (`UploadFile`) in `POST /upload`. |

## Auth & security

| Library | Role | Why |
|---|---|---|
| **python-jose** | JWT encode/decode | Issues and verifies the bearer tokens that authenticate every protected request. |
| **passlib + bcrypt** | Password hashing | bcrypt is a deliberately slow, salted hash designed to resist brute-force/rainbow-table attacks — never store or compare plaintext passwords. Pinned to `bcrypt==4.0.1` due to a real incompatibility with `passlib==1.7.4` on newer bcrypt releases (see `18_Debugging.md`). |

## Data layer

| Library | Role | Why |
|---|---|---|
| **SQLAlchemy 2.0** | ORM | Typed model definitions (`Mapped[...]` style), session management, and query building without hand-written SQL. Swapping SQLite for Postgres in production is a one-line `DATABASE_URL` change. |
| **SQLite** | Database engine | Zero-ops for a demo/portfolio deployment — no separate DB server to provision, back up, or secure. Explicitly *not* what you'd choose for real concurrent production traffic (see `17_Performance.md`). |

## LLM orchestration

| Library | Role | Why |
|---|---|---|
| **LangChain** (`langchain-core`, `langchain-community`, `langchain-text-splitters`) | Document loaders, text splitting, prompt templates, chat-model abstraction | Gives one consistent interface (`BaseChatModel`, `Document`, `PromptTemplate`) across three different LLM providers and multiple document formats, instead of hand-rolling adapters for each. |
| **LangGraph** | Stateful orchestration | Models the RAG pipeline as an explicit graph with conditional edges and cycles (the hallucination-retry loop), which a linear chain of function calls can't express as cleanly. See `09_LangGraph.md`. |

## LLM providers (swappable)

| Provider | Package | Notes |
|---|---|---|
| **Anthropic Claude** | `langchain-anthropic` | Default provider; requires a funded Anthropic account. |
| **Google Gemini** | `langchain-google-genai` | Free tier available via Google AI Studio; quota is per-project. |
| **Groq** (Llama 3.1) | `langchain-groq` | Free tier, very low latency; the provider actually used for live verification in this project (see `18_Debugging.md`). |

All three sit behind one factory function (`app/rag/llm.py`) selected by `LLM_PROVIDER` — the graph nodes that call `get_llm()` never know or care which provider is active.

## Embeddings

| Library | Role | Why |
|---|---|---|
| **sentence-transformers** (`all-MiniLM-L6-v2`) via `langchain-huggingface` | Turns text chunks into vectors for similarity search | Runs entirely locally on CPU — no per-embedding API cost, no external dependency for the ingestion pipeline. 384-dimension vectors, a good speed/quality trade-off for a demo-scale corpus. |

## Vector stores (swappable)

| Library | Role | Why both |
|---|---|---|
| **ChromaDB** (`langchain-chroma`) | Persistent vector store, default | Feels like a lightweight managed store — handles its own persistence and collection management. |
| **FAISS** (`faiss-cpu`) | In-process vector index, alternative | Represents the "bare index, roll your own persistence" end of the spectrum — this project layers a small JSON manifest on top to support delete-by-document, since FAISS itself has no such concept. |

Both implement the same three-method interface (`add_documents`, `similarity_search`, `delete`) defined in `app/vectorstore/base.py`, selected by `VECTOR_DB=chroma|faiss`.

## Document loaders

| Format | Loader |
|---|---|
| PDF | `PyPDFLoader` (`pypdf`) |
| DOCX | `Docx2txtLoader` (`docx2txt`) |
| TXT / MD | `TextLoader` |

## Testing

| Library | Role |
|---|---|
| **pytest**, **pytest-asyncio** | Test runner |
| **httpx** (via FastAPI's `TestClient`) | In-process HTTP testing without a real network socket |
| **FakeListChatModel** (`langchain_core` testing utilities) | Scripts deterministic LLM responses so the graph's control flow (retries, fallback) can be tested without any real API call |
| A custom **`FakeEmbeddings`** | A deterministic bag-of-words hash embedding, purpose-built for this project's tests to avoid downloading the real ~90MB model in CI |

## Lint & formatting

| Library | Role |
|---|---|
| **ruff** | Both linting (`ruff check`) and formatting (`ruff format`) — a single fast tool replacing the traditional `flake8` + `black` + `isort` combination. |

## Infrastructure

| Tool | Role |
|---|---|
| **Docker** / **Docker Compose** | Containerization; multi-stage build; `api` + `nginx` services |
| **NGINX** | Reverse proxy, TLS termination |
| **Certbot** | Let's Encrypt certificate issuance/renewal |
| **GitHub Actions** | CI (lint/format/test/build) and CD (build, push to GHCR, SSH-deploy) |
| **GHCR** (GitHub Container Registry) | Image registry — public, so the deploy target can `docker pull` without extra credentials |
| **AWS EC2, IAM, VPC/Security Groups, Elastic IP** | Compute, access control, network isolation, static addressing |
| **AWS CLI** | Used directly (not Terraform/CloudFormation) to provision infrastructure — appropriate for a single-instance deployment; see `14_AWS_Deployment.md` for the trade-off discussion |

## Frontend

| Tool | Role |
|---|---|
| Vanilla HTML/CSS/JavaScript, Fetch API | The entire `/ui` demo page — no framework, no bundler, no build step (see `06_Frontend.md`) |
