# 11 — API Reference

All routes are versioned under `/api/v1`. Interactive, always-current documentation is auto-generated at `/docs` (Swagger UI) and `/redoc`, plus the raw schema at `/openapi.json` — this file describes the *intent and internal flow* behind each one; the live docs describe the exact current request/response shapes.

---

## `POST /api/v1/auth/register`

- **Purpose**: create a new user account.
- **Request**: `{ "email": string, "password": string (8–128 chars) }`
- **Auth**: none.
- **Internal flow**: check for an existing user with that email (→ `409 Conflict` if found) → `hash_password()` via bcrypt → insert `User` row → return `{id, email}`.
- **Validation**: `EmailStr` rejects malformed addresses at the schema layer, before the handler runs.
- **Error cases**: `409` (email already registered), `422` (malformed body).

## `POST /api/v1/auth/login`

- **Purpose**: exchange credentials for a JWT bearer token.
- **Request**: `{ "email": string, "password": string }`
- **Auth**: none.
- **Internal flow**: look up user by email → `verify_password()` (bcrypt comparison) → on success, `create_access_token(subject=user.id)` → return `{access_token, token_type: "bearer"}`.
- **Error cases**: `401` for either a nonexistent email *or* a wrong password — deliberately the same error and status for both, so a caller can't use response differences to enumerate valid registered emails.

## `POST /api/v1/upload`

- **Purpose**: ingest a document into the current user's searchable knowledge base.
- **Request**: `multipart/form-data` with a `file` field.
- **Auth**: Bearer JWT required.
- **Internal flow**: validate extension against `{.pdf, .docx, .txt, .md}` (→ `415` if unsupported) → create a `Document` row (`status="processing"`) → save the raw file to disk → run the ingestion pipeline (load → split → embed → store) → update the row to `status="ready"` with a real `chunk_count`, or `status="failed"` on any exception.
- **Performance consideration**: ingestion runs synchronously in-request — acceptable for demo-scale files, but a large corpus or a slow embedding model would benefit from a background task/queue instead (see `17_Performance.md`).

## `GET /api/v1/documents`

- **Purpose**: list the current user's uploaded documents.
- **Auth**: Bearer JWT required.
- **Internal flow**: `SELECT * FROM documents WHERE owner_id = :current_user ORDER BY created_at DESC`.
- **Owner scoping**: enforced by the `WHERE` clause — there is no code path that returns another user's documents.

## `DELETE /api/v1/documents/{document_id}`

- **Purpose**: remove a document — its DB row, its raw file, and its vector-store chunks.
- **Auth**: Bearer JWT required.
- **Internal flow**: fetch the row → `404` if it doesn't exist *or* belongs to a different owner (same error for both, so ownership can't be probed) → `vector_store.delete(document_id)` → delete the raw file from disk if present → delete the DB row.
- **Response**: `204 No Content` on success.

## `POST /api/v1/chat`

- **Purpose**: ask a question, answered by the LangGraph RAG pipeline.
- **Request**: `{ "message": string (1–4000 chars), "session_id": string | null }` — omitting `session_id` starts a new conversation.
- **Auth**: Bearer JWT required.
- **Internal flow**: load recent history for `(owner_id, session_id)` → invoke the compiled LangGraph → persist both the user's message and the assistant's answer → build the `sources` list (empty if the fallback path was used) → return `{session_id, answer, sources}`.
- **Full pipeline detail**: `07_RAG_Pipeline.md`, `09_LangGraph.md`.

## `GET /api/v1/history`

- **Purpose**: retrieve conversation history for the current user.
- **Request**: optional `?session_id=` query parameter — omitted, returns every message across all sessions for that user; provided, scopes to one session.
- **Auth**: Bearer JWT required.
- **Internal flow**: `SELECT * FROM chat_messages WHERE owner_id = :current_user [AND session_id = :session_id] ORDER BY created_at ASC`.

## `GET /health`

- **Purpose**: liveness check for orchestrators (Docker healthcheck, load balancers, uptime monitors).
- **Auth**: none.
- **Response**: `{"status": "ok"}` — deliberately has zero dependencies on the database, vector store, or any LLM provider, so it reflects only "is the process itself alive," not "are all downstream dependencies healthy." A separate, deeper readiness check would be the next addition for a stricter production setup.

## `GET /ui`

Serves the static demo frontend (see `06_Frontend.md`). Not part of the JSON API surface.
