# 01 — Project Overview

## What this project is

An **Enterprise RAG (Retrieval-Augmented Generation) Chatbot** — a backend service that lets a user upload their own documents (PDF, DOCX, TXT, Markdown), then ask natural-language questions about them and get answers grounded strictly in those documents. It is not a general-purpose chatbot; it is a *domain-specific Q&A system* scoped to whatever the user has uploaded.

Live deployment: **https://akashwork.website** (`/ui` for a minimal demo frontend, `/docs` for interactive API documentation).

Repository: `Akash6700882/RAG-Chatbot` on GitHub.

## The problem it solves

Large Language Models are fluent but not trustworthy on facts outside their training data, and they will confidently fabricate answers ("hallucinate") when they don't actually know something. A RAG system solves this by:

1. Storing a user's own documents as searchable vector embeddings.
2. At question time, retrieving the most relevant chunks of those documents.
3. Handing the LLM *only* that retrieved context and instructing it to answer strictly from it.
4. Verifying afterward that the answer is actually supported by the context — and refusing to answer rather than guessing if it isn't.

That last point — verification, not just retrieval — is the part most tutorial-level RAG projects skip, and it's the central engineering decision in this codebase (see `07_RAG_Pipeline.md` and `09_LangGraph.md`).

## Who it's for (as a portfolio piece)

This project exists to demonstrate, with real working code, five specific engineering competencies:

| Competency | Where it's demonstrated |
|---|---|
| LLM application design | `app/rag/` — a LangGraph state machine, not a single prompt-and-pray call |
| Data/ingestion engineering | `app/ingestion/`, `app/vectorstore/` — multi-format loaders, chunking, pluggable vector backends |
| Secure API design | `app/auth/`, `app/core/security.py` — JWT + bcrypt, owner-scoped data access |
| Containerization & cloud deployment | `Dockerfile`, `docker-compose.yml`, `deploy/` — a real AWS EC2 deployment, not a description of one |
| CI/CD engineering | `.github/workflows/` — pipelines that were actually run against production and debugged when they broke |

## High-level facts

- **Language**: Python 3.12
- **Backend framework**: FastAPI
- **Frontend**: a single static HTML/CSS/JS page (no framework, no build step)
- **LLM orchestration**: LangChain + LangGraph
- **LLM providers** (swappable via one env var): Anthropic Claude, Google Gemini, Groq (Llama 3.1)
- **Embeddings**: HuggingFace `sentence-transformers/all-MiniLM-L6-v2` (runs locally, no API cost)
- **Vector stores** (swappable via one env var): ChromaDB, FAISS
- **Database**: SQLite via SQLAlchemy ORM
- **Auth**: JWT bearer tokens, bcrypt password hashing
- **Containerization**: Docker (multi-stage build), Docker Compose (API + NGINX)
- **Reverse proxy / TLS**: NGINX + Let's Encrypt (Certbot)
- **CI/CD**: GitHub Actions — lint, format-check, test, Docker build on every push; build+push to GHCR and SSH deploy to EC2 on `main`
- **Cloud**: AWS EC2 (t3.micro), Elastic IP, IAM-scoped credentials, security groups
- **Domain/DNS**: Namecheap-registered domain, A record to a static IP
- **Tests**: 45 automated tests (unit + integration), all LLM/embedding calls mocked — zero API cost or network dependency in CI

## How to read the rest of these docs

Each file in this `docs/` directory covers one layer of the system in depth, in roughly the order you'd explain it to a new engineer:

```
01 Overview → 02 Architecture → 03 Stack → 04 Structure
   → 05 Backend → 06 Frontend
   → 07 RAG Pipeline → 08 LangChain → 09 LangGraph → 10 Vector DB
   → 11 APIs → 12 Auth
   → 13 Docker → 14 AWS → 15 GitHub Actions
   → 16 Security → 17 Performance → 18 Debugging (real incidents)
   → 19 Interview Prep → 20 Non-Technical Explanations
```

`Architecture_Diagrams/` holds the Mermaid source for every diagram referenced across these files, renderable natively on GitHub.
