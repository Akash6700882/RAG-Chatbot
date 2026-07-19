# 19 — Interview Preparation

Organized by category. The first ~30 questions get full depth (expected answer, common mistakes, a follow-up, best practice). The reference table after that covers the remaining questions concisely — enough to recognize and answer confidently, without needing four paragraphs per line item.

---

## A. Architecture & RAG concepts

### 1. What is RAG, and why not just fine-tune a model on your documents instead?

**Expected answer**: RAG retrieves relevant text at query time and injects it into the prompt, rather than baking knowledge into model weights. Fine-tuning is expensive to update (every document change needs retraining), doesn't cleanly support per-user data isolation, and doesn't reduce hallucination on its own — the model can still confidently state something wrong. RAG lets you add, remove, or scope documents instantly (just update the vector store) and grounds answers in retrievable, citable source text.
**Common mistake**: describing RAG as "giving the model more training data" — it isn't training at all, it's context-window injection at inference time.
**Follow-up**: "When would you combine both?" — fine-tune for domain *style/format*, RAG for domain *facts*.
**Best practice**: keep retrieval and generation as separately testable stages (this project's LangGraph nodes), not one opaque call.

### 2. Walk me through what happens, end to end, when a user asks a question.

**Expected answer**: see `07_RAG_Pipeline.md` and the full trace in `06_Code_Flow` (build journal artifact) / `05_Backend.md` — auth → load history → rewrite (conditional) → retrieve (owner-scoped) → validate → generate or fallback → hallucination-check → retry or end → persist → respond.
**Common mistake**: skipping the validate/hallucination-check steps as if retrieval→generate were the whole pipeline.
**Follow-up**: "What if retrieval returns zero documents?" — validation short-circuits without an LLM call, routes straight to fallback.

### 3. Why LangGraph instead of a single prompt or a linear chain?

**Expected answer**: the retry loop (ungrounded → regenerate, bounded) is a genuine cycle with conditional branching from two different decision points (validation, hallucination-check) into a shared fallback — hard to express cleanly as nested conditionals, easy to express as named nodes and edges.
**Common mistake**: claiming LangGraph is "required" for any multi-step LLM app — it's justified specifically by the branching/cycles here, not by mere multi-step-ness.
**Best practice**: keep node functions pure and independently unit-testable (verified in `tests/unit/test_rag_graph.py`).

### 4. How do you actually prevent hallucination — walk through the mechanism, not just the concept.

**Expected answer**: two LLM-backed checkpoints (validation before generating, fact-check after), a bounded retry loop, and a fixed fallback string as the only allowed "I don't know" — never a model-generated non-answer. See Incident 5 in `18_Debugging.md` for how a real bug in this exact mechanism was found and fixed.
**Common mistake**: saying "the prompt tells it not to hallucinate" as if wording alone solves it — this project's actual answer is a verification *pipeline*, not prompt wording.

### 5. Why two vector store backends?

**Expected answer**: demonstrates the abstraction (`VectorStore` Protocol) actually holds across two backends with materially different capabilities (Chroma's built-in persistence vs. FAISS's bare index + hand-rolled delete manifest) — a real engineering exercise in interface design, not just calling one library's SDK.
**Follow-up**: "Which would you pick for production?" — depends on scale and ops appetite; a managed vector DB (e.g., Pinecone, Weaviate Cloud) removes both options' self-hosting burden.

### 6. How is one user's data kept separate from another's?

**Expected answer**: `owner_id` tagged on every document/chunk/message at creation, filtered on every read — both at the SQL layer (`WHERE owner_id = ...`) and the vector-store layer (post-search metadata filter). See `10_Vector_Database.md`, `16_Security.md`.
**Common mistake**: assuming the vector store's own native filtering is trusted — this project deliberately applies the filter in shared application code so both backends behave identically.

### 7. What's the actual retry limit, and what happens when it's exhausted?

**Expected answer**: `MAX_GENERATION_RETRIES` (default 2), enforced in `_route_after_hallucination_check`. Exhausted → routes to the fixed fallback node, never a third attempt, never surfacing an unverified answer.

### 8. Why skip the rewrite step on the first turn?

**Expected answer**: nothing exists yet to rewrite against (no prior chat history to resolve pronouns from) — running the LLM call anyway would just return the same question, wasting a call and adding latency for no benefit.

---

## B. LangChain / LangGraph specifics

### 9. What does `prompt | llm` actually do?

**Expected answer**: LangChain's Runnable composition — pipes the filled prompt's messages into the chat model's `.invoke()`, returning a message object with `.content`. Same shape regardless of which of the three providers is active.

### 10. What's `GraphState`, and why `total=False`?

**Expected answer**: a `TypedDict` threaded through every node; `total=False` because not every key is present at every point in execution (e.g., `rewritten_query` doesn't exist until after the rewrite node runs) — nodes must use `.get()` with defaults, never direct indexing, for keys that might not be set yet.

### 11. How would you add a sixth node to this graph?

**Expected answer**: write a new node function taking/returning partial `GraphState` dict, register it with `graph.add_node(...)`, wire edges (plain or conditional) to/from it in `build_graph()`. No other file needs to change.

### 12. How are the LLM calls tested without hitting a real API?

**Expected answer**: `FakeListChatModel` from `langchain_core`'s testing utilities, monkeypatched over each node's `get_llm()`, scripted with an ordered list of responses — see `09_LangGraph.md` and Incident 2 in `18_Debugging.md` for the subtlety of keeping one shared instance across calls.

---

## C. Vector databases & embeddings

### 13. Explain cosine similarity like you would to a junior engineer.

**Expected answer**: two vectors pointing in nearly the same direction (regardless of length) have a cosine similarity near 1; perpendicular vectors near 0; opposite near -1. Normalizing embeddings first makes cosine similarity equivalent to a plain dot product, which is cheaper to compute at scale.

### 14. Why `all-MiniLM-L6-v2` specifically?

**Expected answer**: a small, fast, CPU-friendly sentence-transformer with a good speed/quality trade-off for a demo-scale corpus, and zero per-call API cost since it runs locally.

### 15. How does deletion work for FAISS, given it has no native delete-by-metadata?

**Expected answer**: a JSON manifest (`{document_id: [vector_ids]}`) maintained alongside the index, updated on every add, consulted on delete to look up exactly which raw vector IDs belong to a given document.

### 16. What happens if retrieval returns irrelevant chunks?

**Expected answer**: the validation node catches this — it doesn't matter that *something* was retrieved; the LLM judges the retrieved content against the actual question and can (and does) return `INSUFFICIENT`.

---

## D. Authentication & security

### 17. Why bcrypt instead of, say, SHA-256, for passwords?

**Expected answer**: SHA-256 is fast — a property that's good for file integrity checks and terrible for password hashing, since it makes brute-force/rainbow-table attacks cheap. bcrypt is deliberately slow and includes a per-hash salt, making both attacks computationally expensive at scale while staying fast enough for legitimate single-login use.

### 18. What's actually inside a JWT, and is it encrypted?

**Expected answer**: a base64-encoded, *signed* (not encrypted) payload — here, just `{sub: user_id, exp: expiry}`. Signed means tampering is detectable (via HMAC with the server's secret key); not encrypted means anyone can decode and read it, which is why no sensitive data lives in the payload.

### 19. What happens when a JWT expires?

**Expected answer**: `decode_access_token` raises `UnauthorizedError` on any `JWTError` (including expiry) → HTTP 401. No refresh-token flow exists yet — the client must call `/login` again (a named, honest limitation, see `12_Authentication.md`).

### 20. How would you add rate limiting?

**Expected answer**: at the NGINX layer (`limit_req_zone` + `limit_req`), since it's the single public entrypoint — avoids needing per-request logic inside the FastAPI app itself. Currently not implemented; a named open follow-up (`16_Security.md`).

---

## E. FastAPI / backend

### 21. How does FastAPI validate requests before your code runs?

**Expected answer**: route parameters typed as Pydantic models are parsed and validated by FastAPI/Pydantic automatically; a malformed body never reaches the handler function body — FastAPI returns a 422 with details about exactly which field failed.

### 22. What does `Depends(get_current_user)` actually do, mechanically?

**Expected answer**: FastAPI calls `oauth2_scheme` to extract the bearer token from the `Authorization` header, then calls `get_current_user(token, db)`, which decodes the JWT and loads the user row — all *before* the route handler's own body executes. If either step raises, the handler body never runs.

### 23. Why no separate "service layer" or DI container?

**Expected answer**: the codebase is small enough that router functions calling directly into `ingestion/`, `vectorstore/`, `rag/` modules *is* the service layer — an additional abstraction layer would add indirection without adding testability at this scale. FastAPI's own `Depends` system is DI enough for request-scoped resources (DB session, current user).

---

## F. Docker

### 24. Why a multi-stage build?

**Expected answer**: keeps the compiler toolchain (`build-essential`) and pip's build cache out of the final image — only the finished virtual environment is copied into the runtime stage. See `13_Docker.md`.

### 25. Why install torch separately, before `requirements.txt`?

**Expected answer**: forces the CPU-only wheel (from PyTorch's own index) to be installed first, so `sentence-transformers`'s later, unpinned torch dependency is already satisfied and pip never resolves a multi-gigabyte CUDA build meant for GPU machines.

### 26. Why does the `api` service have no `ports:` mapping?

**Expected answer**: NGINX is the sole public entrypoint; the API is reachable only over the internal Docker network as `api:8000`. Originally forced by a real port conflict on the dev machine, kept because it's the architecturally correct pattern regardless — and directly caused (and then fixed) a real deploy bug (`18_Debugging.md`, Incident 8).

---

## G. AWS / cloud

### 27. Why IAM-scoped credentials instead of root?

**Expected answer**: least privilege — a dedicated IAM user with only `AmazonEC2FullAccess` bounds the blast radius of a leaked credential to EC2 resources, not the whole AWS account.

### 28. Why an Elastic IP?

**Expected answer**: a plain EC2 public IP changes on stop/start; an Elastic IP is static (and free while attached to a running instance) — required so DNS and the `EC2_HOST` CI/CD secret don't need updating every time the instance restarts.

### 29. Why a swap file on a 1GB instance?

**Expected answer**: torch + sentence-transformers + ChromaDB together can exceed 1GB of RAM under load; a 2GB swap file absorbs memory-pressure spikes rather than the kernel OOM-killing the process — a deliberate mitigation for a knowingly-tight free-tier instance choice.

---

## H. CI/CD

### 30. How does your pipeline avoid needing real API keys in CI?

**Expected answer**: every LLM/embedding call in the test suite is mocked (`FakeListChatModel`, a custom `FakeEmbeddings`) — CI sets deliberately fake env var values and never makes a real network call to any provider.

---

## Reference table — remaining questions (concise answers)

| # | Question | Expected answer, briefly |
|---|---|---|
| 31 | What's the difference between authentication and authorization? | Who you are vs. what you're allowed to do — JWT decode vs. `owner_id` comparison. |
| 32 | Why `EmailStr` instead of a plain `str` for email fields? | Pydantic validates the format at the schema layer, before handler code runs. |
| 33 | What's the purpose of `response_model` in FastAPI routes? | Guarantees only the declared fields are ever serialized out — e.g. `hashed_password` can't leak even if the ORM object has it. |
| 34 | Why does `/login` return the same error for wrong password and unknown email? | Prevents email enumeration via response differences. |
| 35 | What is `@lru_cache` doing on `get_settings()` and `get_embeddings()`? | Caches an expensive-to-construct object for the process lifetime instead of rebuilding it per call. |
| 36 | Why is `RETRIEVAL_TOP_K` configurable rather than hardcoded? | Different corpora/use-cases need different context breadth vs. precision trade-offs. |
| 37 | What would you change to support real-time streaming answers? | Convert the LLM calls to streaming mode and the `/chat` route to a streaming response (SSE or chunked). |
| 38 | Why `RecursiveCharacterTextSplitter` over a fixed-size splitter? | Prefers splitting on natural boundaries (paragraph/sentence) before falling back to a hard character cut, preserving semantic coherence. |
| 39 | What's chunk overlap for? | Prevents a sentence that straddles a chunk boundary from losing context in both neighboring chunks. |
| 40 | How would you support real-time collaborative documents? | Out of scope for the current design; would need a different ingestion trigger (webhook/event) rather than a one-shot upload endpoint. |
| 41 | What does `status_code=204` mean, and why no response body on delete? | "No Content" — the operation succeeded and there's nothing meaningful to return. |
| 42 | Why is `session_id` optional on `/chat`? | Omitting it starts a new conversation; providing it continues an existing one — same endpoint serves both cases. |
| 43 | What's stored in `chat_messages`, and why both roles? | Both user and assistant turns, so `/history` can reconstruct the full conversation, and so the rewrite node has real prior context. |
| 44 | Why SQLite for now, and what's the migration path to Postgres? | Zero-ops for a demo; only `DATABASE_URL` changes, since SQLAlchemy abstracts the engine. |
| 45 | What is `Mapped[str]` (SQLAlchemy 2.0 style)? | Typed ORM column declarations — gives IDEs/type-checkers real types instead of untyped `Column(...)`. |
| 46 | Why does `Document` have a `status` field at all? | Tracks async-in-spirit ingestion state (`processing`/`ready`/`failed`) even though it currently runs synchronously — forward-compatible with a future background-task version. |
| 47 | What's the risk of running ingestion synchronously in-request? | A large file or slow embedding step blocks the request/response cycle; should move to a background task at scale. |
| 48 | Why `python-jose` over `PyJWT`? | Functionally similar; `python-jose` was the chosen library — both are standard, well-maintained JWT libraries. |
| 49 | What does `OAuth2PasswordBearer(tokenUrl=...)` actually enable? | Tells FastAPI's OpenAPI generation to render the Swagger "Authorize" lock icon pointing at the login endpoint; doesn't itself enforce anything. |
| 50 | How is the frontend prevented from XSS via chat content? | User/LLM text is inserted via `.textContent`, never `.innerHTML` — see `06_Frontend.md`. |
| 51 | Why no build step for the frontend? | The page is small enough (3 forms, a chat log) that a framework/bundler would add complexity without proportional benefit. |
| 52 | How does the frontend avoid CORS issues? | Served from the same origin as the API it calls — no cross-origin request ever happens. |
| 53 | What's the risk of storing the JWT in a JS variable instead of `localStorage`? | Lost on refresh (acceptable for a demo); the alternative trade-offs are `localStorage` (XSS-vulnerable) vs. `httpOnly` cookies (needs CSRF protection instead). |
| 54 | Why `useradd --create-home --uid 1000 appuser` in the Dockerfile? | Runs the app as an unprivileged, non-root user inside the container. |
| 55 | What does `HEALTHCHECK` in the Dockerfile actually enable? | `docker compose ps` status and `depends_on: condition: service_healthy` both key off it. |
| 56 | Why `--no-build` in the deploy script's `docker compose up`? | The image was already pulled and retagged; rebuilding from source on the tiny EC2 instance would be slow and pointless. |
| 57 | What's the purpose of `docker image prune -f` after every deploy? | Reclaims disk space from now-unreferenced old image layers on a small EBS volume. |
| 58 | Why does NGINX depend on the API's healthcheck before starting? | Avoids a startup race where NGINX proxies to a container that isn't actually ready yet. |
| 59 | What is the ACME HTTP-01 challenge, conceptually? | Let's Encrypt asks the server to publish a specific token at a specific URL under the domain being verified — only the real owner of that domain's DNS/server could satisfy that. |
| 60 | Why would a proxying DNS provider (e.g., default Cloudflare) break Let's Encrypt? | The HTTP-01 challenge needs to reach the actual origin server directly; a proxy sitting in front can intercept or alter that request. |
| 61 | What's the difference between a security group and a network ACL? | Security groups are stateful, instance-level; NACLs are stateless, subnet-level — this project only uses a security group. |
| 62 | Why choose the default VPC instead of creating a custom one? | Appropriate for a single-instance deployment; a custom VPC with public/private subnet separation matters more at multi-tier scale. |
| 63 | What would break if the EC2 instance were terminated and recreated? | The Elastic IP would need re-associating, the `EC2_HOST` secret would need to stay pointed at it (it would, since the IP itself doesn't change), and the Docker volumes (and their data) would be lost unless backed by a separate persistent volume/snapshot. |
| 64 | How would you back up the vector store / database today? | Not automated currently — an honest gap; would add scheduled EBS snapshots or an application-level export job. |
| 65 | What's the blast radius if the EC2 SSH private key leaked? | Full shell access to that one instance — bounded by the security group's own restrictions, but a real risk; rotating the key pair would be the immediate response. |
| 66 | Why `workflow_dispatch` in addition to `push`? | Lets a deploy be manually re-triggered without needing a new commit — used repeatedly while debugging the pipeline itself. |
| 67 | What does `needs: build-and-push` do in the `deploy` job? | Makes `deploy` wait for and depend on `build-and-push`'s success (and lets it read that job's `outputs`). |
| 68 | Why check for secrets' existence before attempting SSH, instead of just letting it fail? | Produces a clear, actionable log message instead of a cryptic connection failure, and lets the pipeline stay "green" before infrastructure exists. |
| 69 | What does GHCR image visibility (public vs. private) affect here? | Whether the EC2 host can `docker pull` without needing its own registry credentials — this project's image is public specifically to avoid that extra complexity. |
| 70 | How would you implement blue-green deployment here? | Run a second `api` container on a different internal port/tag, switch NGINX's upstream once it's confirmed healthy, then tear down the old one — not implemented today (single in-place container swap). |
| 71 | What's a realistic RTO (recovery time objective) for this deployment today? | Minutes (manual redeploy or instance restart) — there's no automated failover, single instance, single region. |
| 72 | Why pin exact dependency versions in `requirements.txt`? | Reproducible builds — an upstream library release shouldn't be able to silently change production behavior between deploys. |
| 73 | How was a version conflict between three different LLM SDKs resolved? | Let pip's resolver pick compatible versions across `langchain-anthropic`, `langchain-google-genai`, and `langchain-groq` rather than hand-pinning and risking an unsatisfiable set — verified the resolved `langchain-core` version didn't regress. |
| 74 | What does `ruff format --check` add beyond `ruff check`? | Enforces consistent code *style* (whitespace, line wrapping, quoting) as a CI gate, separate from *correctness* linting. |
| 75 | Why mock embeddings in tests instead of using the real (free) local model? | Speed and determinism — downloading/running the real ~90MB model on every CI run would be slow and unnecessary when only the *pipeline logic*, not embedding quality, is under test. |
| 76 | What does the custom `FakeEmbeddings` actually compute? | A deterministic bag-of-words hash into a fixed-size vector — enough to produce distinguishable, repeatable similarity results without downloading any real model. |
| 77 | Why does the vector store factory cache instances per `(backend, path)` tuple? | Production reuses one instance across requests (avoiding repeated expensive initialization), while tests using unique temp paths per test still get properly isolated instances. |
| 78 | What happens if two requests hit `/upload` for the same filename simultaneously? | Each gets its own generated `document_id` (UUID) and its own file path on disk — no collision, since the filename itself isn't used as the storage key. |
| 79 | Why validate file extension instead of trusting the client's declared MIME type? | Client-supplied metadata (including MIME type) is untrusted input; extension-allowlisting against `SUPPORTED_EXTENSIONS` is a simple, explicit server-side check. |
| 80 | What's the actual failure mode if an unsupported file type is uploaded? | `UnsupportedFileTypeError` → HTTP 415, before any file is written to disk or any DB row is created. |
| 81 | How does `GET /history` differ with and without `session_id`? | Without it: every message across all of that user's sessions; with it: scoped to one conversation. |
| 82 | Why order history ascending but truncate to the most recent N turns? | Recency matters for relevance (only the last N turns feed the rewrite node), but the model needs them in chronological, readable order once selected. |
| 83 | What's a plausible next feature, given the current architecture? | Streaming responses (token-by-token), given the pipeline already produces a final answer string that could instead be yielded incrementally from the last LLM call. |
| 84 | How would you add per-user rate limiting instead of global? | Rate-limit by the authenticated `user.id` (available post-auth-dependency) rather than by IP at the NGINX layer, which can't see inside the JWT. |
| 85 | Why does this project avoid a custom repository/DAO abstraction over SQLAlchemy? | The query surface is small; direct session/query use is simpler and equally testable at this scale — added abstraction should be justified by actual pain, not applied preemptively. |
| 86 | What's the risk of the current single-instance deployment during a deploy? | Brief downtime during container recreation — no rolling/blue-green strategy yet (see #70). |
| 87 | How would a CTO-level reviewer evaluate this project's readiness for "real" production traffic? | Positively on architecture/security fundamentals (JWT, owner-scoping, non-root containers, IAM-scoped access); with named gaps on scaling (SQLite, single instance), observability (no centralized logging/metrics), and rate limiting — all explicitly acknowledged, not hidden. |
| 88 | What's the single most defensible engineering decision in this project? | The verification-before-trust RAG design (validate context, then fact-check the answer) — it's the one piece of prompt/pipeline engineering that's genuinely non-obvious and directly addresses the stated goal (reducing hallucination), rather than being infrastructure boilerplate. |
| 89 | What's the weakest part of the current implementation, honestly? | No rate limiting and no prompt-injection defense — both named explicitly in `16_Security.md` rather than glossed over. |
| 90 | If you had one more week, what would you build next? | Automated cert renewal (a cron job calling `certbot renew`), a background task queue for ingestion, and structured request logging/metrics. |

---

## Behavioral — STAR-format debugging stories

Full three stories (health-check port mismatch, passlib/bcrypt incompatibility, self-inflicted test-mock bug) are written out in the published build-journal artifact and summarized identically in `18_Debugging.md`, incidents 8, 1, and 2 respectively — use those as your source material; they are all real, specific, and verifiable against actual commits.

---

## Resume mapping

| Resume bullet | Evidence |
|---|---|
| "Built an enterprise-grade conversational AI assistant using LLMs, LangChain, and LangGraph, powering domain-specific Q&A." | `app/rag/graph.py` (5-node `StateGraph`), `app/rag/llm.py` (3 swappable providers) |
| "Developed a multi-format document ingestion pipeline with intelligent chunking and semantic embeddings." | `app/ingestion/` (loaders, splitter), `app/embeddings/huggingface.py` |
| "Implemented ChromaDB/FAISS vector search with prompt engineering to reduce hallucinations." | `app/vectorstore/` (dual backend), `app/rag/nodes/validate_context.py` + `check_hallucination.py` |
| "Containerized with Docker and deployed on AWS using GitHub Actions CI/CD." | `Dockerfile`, `docker-compose.yml`, `.github/workflows/cd.yml`, live at akashwork.website |
| "Exposed secure REST APIs through FastAPI with JWT authentication." | `app/core/security.py`, `app/auth/`, 7 documented endpoints |
| *(earned, not originally scoped)* "Provisioned and hardened cloud infrastructure end-to-end, achieving a live HTTPS deployment on a custom domain." | `14_AWS_Deployment.md`, `deploy/`, Let's Encrypt via `init-letsencrypt.sh` |
