# 20 — Explaining This Project to Different Audiences

The same project, explained nine times, each with more technical depth than the last. Useful for calibrating how you talk about this in different rooms — a recruiter screen and a staff-engineer interview should not sound the same.

---

## 1. To a 10-year-old

Imagine you have a big pile of homework papers and you want to ask "what's the answer to question 5?" without reading every single page. I built a robot helper that reads all your papers first, remembers where everything is, and when you ask it a question, it goes and finds the exact right page before answering — and if it can't find the answer anywhere in your papers, it says "I don't know" instead of making something up. That's the honest part that's actually hard to build.

## 2. To a non-technical person

I built a chatbot you can upload your own documents to — a PDF, a Word file, whatever — and then ask it questions in plain English about what's in them. Unlike a generic chatbot, it only answers from what you actually gave it, and it's built to say "I'm not sure" rather than guess when the document doesn't cover something. It runs live on the internet, with a real website address and a secure connection, the same way a real product would.

## 3. To an HR recruiter

This is a full-stack, cloud-deployed AI application — not a tutorial project. It covers backend API development (Python/FastAPI), applied AI/LLM engineering (LangChain, LangGraph, vector databases), and DevOps (Docker, AWS, CI/CD pipelines with GitHub Actions). It's live at a real domain with HTTPS, and the candidate can speak concretely to real production issues they found and fixed during deployment — not just describe the tech stack from memory.

## 4. To a college student

Think of it as three layers stacked on top of each other. The bottom layer is a normal web backend (like you'd build in a web dev class) — it handles logins and stores data in a database. The middle layer is where the "AI" part lives: it takes your uploaded files, breaks them into chunks, turns each chunk into a list of numbers (an "embedding") that represents its meaning, and stores those so it can later find the most relevant chunks for any question using math (comparing how "similar" two lists of numbers are). The top layer sends the relevant chunks plus your question to a large language model and asks it to answer using *only* that information — then double-checks the answer before sending it back to you.

## 5. To a software engineer (general)

A modular FastAPI backend: JWT auth, SQLAlchemy models, and three feature routers (`auth`, `documents`, `chat`). The interesting engineering is in `app/rag/` — a LangGraph state machine with five nodes and two conditional edges implementing a retrieval-then-verify pattern, not a single prompt call. Vector storage is abstracted behind one interface with two interchangeable backends (Chroma, FAISS). 45 tests, all LLM/embedding calls mocked, so CI never touches a real API. Containerized, CI/CD'd to a real EC2 instance behind NGINX/Let's Encrypt.

## 6. To a senior backend engineer

Deliberate scope control: a modular monolith, not microservices, because the problem doesn't need distributed-systems complexity yet — and I can articulate exactly what would have to change if it did (Postgres over SQLite, a managed vector store, a load balancer over multiple app instances, async-everywhere instead of sync-in-threadpool). Data isolation is enforced at the application layer (`owner_id` filtering) rather than trusted to either vector-store backend's native filter support, specifically because the two backends don't offer identical guarantees there. Error handling distinguishes typed domain errors (`AppError` subclasses with their own status codes) from a catch-all — though I'd point out myself that the catch-all currently doesn't distinguish an upstream LLM provider failure from a genuine bug, which is a named, real gap.

## 7. To an AI engineer

The core design bet is that a single-pass RAG chain isn't trustworthy enough to ship, so the pipeline adds two verification checkpoints around generation: a context-sufficiency judgment *before* generating (skip generation entirely rather than answer from irrelevant retrieval) and an independent groundedness check *after* generating (bounded retry, then a fixed fallback — never a second unverified guess). I verified this live against a real model (Groq/Llama 3.1) by deliberately asking an out-of-scope question and confirming it refused rather than hallucinated, not just relying on mocked test coverage. Chunking is `RecursiveCharacterTextSplitter` at 1000/150 — a reasonable default, not empirically tuned against a labeled eval set, which I'd want to build next. Embeddings are local (`all-MiniLM-L6-v2`), which caps quality somewhat versus a larger hosted embedding API but keeps the whole pipeline free to run repeatedly.

## 8. To a cloud engineer

IAM-scoped credentials (a dedicated user, `AmazonEC2FullAccess` only — not root) provisioned a `t3.micro` in the default VPC, a security group open on exactly 22/80/443, and an Elastic IP for stable addressing across restarts. The app container publishes no host port at all — NGINX is the sole ingress, terminating TLS via Let's Encrypt (HTTP-01 challenge) and reverse-proxying over the internal Docker network. CD is a real SSH-based pipeline (GitHub Actions → GHCR → `deploy.sh` on the host), and I can walk through three genuine production incidents found getting that pipeline working: a missing file permission bit, a Docker image-tag case-sensitivity bug, and a health-check probing a port that had been intentionally closed by an earlier architecture decision — each root-caused from raw logs, fixed, and re-verified against the live system, not simulated.

## 9. To a CTO

This demonstrates the specific judgment that matters at any scale: knowing when *not* to add complexity (no microservices, no custom DI framework, no premature abstraction layers) while being fully able to articulate the real production gaps that exist today — no rate limiting, no centralized observability, a single point of failure at the instance level, SQLite's concurrency ceiling — and what specifically I'd do about each, in priority order, if this had to carry real traffic tomorrow. Equally important: every claim here is backed by a real, live, working deployment with real commit history and real incidents, not a description of an architecture that was never actually run under any conditions harder than a local `pytest` pass.
