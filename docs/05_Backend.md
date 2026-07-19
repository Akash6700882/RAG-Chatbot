# 05 — Backend Deep Dive

## Framework: FastAPI

FastAPI is used for four things simultaneously, all built in rather than bolted on:

1. **Routing** — `@router.get/post/delete(...)` decorators map HTTP verbs+paths to Python functions.
2. **Validation** — request bodies are typed as Pydantic models; FastAPI parses and validates them before your function body ever runs, returning a 422 automatically on bad input.
3. **Dependency injection** — `Depends(...)` parameters are resolved per-request by FastAPI itself.
4. **Documentation** — every route, schema, and tag is introspected into a live OpenAPI schema, rendered at `/docs`.

## Routers

There is no single `app.py` with every route in it. Each feature owns its own `router.py` (`auth`, `documents`, `chat`), and `app/api.py` aggregates them under one `/api/v1` prefix:

```python
# app/api.py
from fastapi import APIRouter
from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.documents.router import router as documents_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(chat_router)
```

This is the closest thing to a "controller" layer in this codebase — but note there's no separate "service" layer beneath it in the traditional layered-architecture sense. Route handlers call directly into the ingestion/vectorstore/rag modules. For a codebase this size, an extra service-layer indirection would add ceremony without adding testability — the modules themselves (`ingestion.pipeline`, `rag.graph`, `vectorstore.factory`) already are the service layer, just not wrapped in a class hierarchy.

## Dependency injection in practice

Two dependencies are used constantly:

```python
# app/db/session.py
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

```python
# app/auth/dependencies.py
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    user_id = decode_access_token(token)
    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    return user
```

Every protected route declares `current_user: User = Depends(get_current_user)` as a parameter — FastAPI resolves the JWT, loads the user, and raises before the route body runs if either fails. This is what "authorization" means concretely in this codebase: it isn't a decorator or middleware, it's a typed function parameter.

## Pydantic schemas — validation and serialization

Every request body and response shape is an explicit Pydantic model (`app/*/schemas.py`), e.g.:

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
```

`EmailStr` rejects malformed emails before the handler runs; `min_length=8` rejects short passwords the same way. On the way out, `response_model=UserResponse` ensures the handler can only ever return the fields the client is meant to see — the ORM's `hashed_password` column, for instance, is structurally impossible to leak because `UserResponse` doesn't have that field.

## Full endpoint walkthrough: `/upload`

```python
@router.post("/upload", response_model=DocumentResponse, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    ...
    document = Document(owner_id=current_user.id, filename=file.filename, ..., status="processing")
    db.add(document); db.commit(); db.refresh(document)
    try:
        # save to disk, then ingest_file(...) → loaders → splitter → vector store
        document.status = "ready"
        document.chunk_count = chunk_count
    except Exception:
        document.status = "failed"
        raise
    finally:
        db.commit(); db.refresh(document)
    return document
```

Notice the row is created with `status="processing"` *before* ingestion runs, and updated to `"ready"` or `"failed"` in a `try/except/finally` — so a client that lists documents mid-upload sees an honest, real-time status rather than the row simply not existing yet or silently vanishing on failure.

## Full endpoint walkthrough: `/chat`

```python
@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session_id = payload.session_id or str(uuid.uuid4())
    history = get_recent_history(db, current_user.id, session_id)
    result = get_rag_graph().invoke({
        "question": payload.message, "owner_id": current_user.id,
        "chat_history": history, "retry_count": 0,
    })
    save_message(db, current_user.id, session_id, "user", payload.message)
    save_message(db, current_user.id, session_id, "assistant", result["answer"])
    sources = [] if result.get("used_fallback") else sorted({d.metadata.get("filename","unknown") for d in result.get("retrieved_docs", [])})
    return ChatResponse(session_id=session_id, answer=result["answer"], sources=sources)
```

The entire RAG pipeline is invoked as a single `graph.invoke(state_dict)` call — the route handler doesn't know or care how many nodes ran, whether a retry happened, or which LLM provider answered. That's the payoff of the LangGraph abstraction (`09_LangGraph.md`): the router's job is reduced to "build the initial state, invoke the graph, persist the result."

## Configuration

```python
# app/config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    llm_provider: Literal["anthropic", "gemini", "groq"] = "anthropic"
    vector_db: Literal["chroma", "faiss"] = "chroma"
    jwt_secret_key: str = "insecure-dev-secret-change-me"
    ...

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Every configurable value is typed and has a sane default, read once from `.env` via `pydantic-settings`, and cached with `@lru_cache` so the file is parsed exactly once per process (tests explicitly call `get_settings.cache_clear()` when they need to override values via `monkeypatch.setenv`).

## Error handling

Custom exceptions (`app/core/exceptions.py`) carry their own HTTP status code:

```python
class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    def __init__(self, detail: str):
        self.detail = detail

class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
```

Route handlers just `raise NotFoundError("Document not found")` — a single registered exception handler converts any `AppError` into the right JSON response with the right status code, and a catch-all handler logs and returns a generic 500 for anything unexpected (this catch-all is the exact gap discussed in `18_Debugging.md` — it works, but currently doesn't distinguish an unhandled upstream LLM failure from a genuine bug).

## Logging

```python
# app/core/logging.py
def configure_logging() -> None:
    settings = get_settings()
    logging.getLogger().setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    ...
```

A single structured format (`timestamp | LEVEL | logger name | message`) is applied at startup; noisy third-party loggers (httpx, chromadb, sentence_transformers) are turned down to `WARNING` so application logs aren't drowned out.
