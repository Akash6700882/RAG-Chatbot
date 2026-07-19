# 13 — Docker

## What Docker is doing here, conceptually

Docker packages the application together with its exact runtime environment (Python version, system libraries, installed packages) into an **image** — an immutable, versioned artifact. Running that image produces a **container**: an isolated process with its own filesystem view, so "works on my machine" becomes "works in this exact, reproducible environment," whether that machine is a laptop or an EC2 instance on the other side of the world.

## The Dockerfile, instruction by instruction

```dockerfile
# syntax=docker/dockerfile:1

# --- Builder stage ---
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r requirements.txt

# --- Runtime stage ---
FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY app ./app
COPY data/sample_docs ./data/sample_docs
RUN mkdir -p /app/data/uploads /app/data/vectorstore && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- **`FROM python:3.12-slim AS builder`** — a multi-stage build starts here. `slim` (not `alpine`) is chosen because several Python ML packages (torch, chromadb) ship prebuilt `manylinux` wheels that assume glibc, which Alpine's musl libc doesn't provide — using slim avoids a class of "wheel not found, compiling from source" failures.
- **`build-essential`** — a C compiler and friends, needed only to build a couple of packages from source during install; deliberately confined to the builder stage so it never ends up in the shipped image.
- **CPU-only torch installed *before* `requirements.txt`** — this is the single most important line for image size and reliability. `sentence-transformers` (used for embeddings) depends on torch but doesn't pin a specific build. Left alone, pip resolves torch from the default PyPI index, which defaults to a multi-gigabyte CUDA-enabled build meant for GPU machines — enormous overkill (and slow to download) for a CPU-only embedding model running on a $ 7/month EC2 instance. Installing the CPU-only wheel first means the later `pip install -r requirements.txt` sees torch's requirement already satisfied and never re-resolves it.
- **`FROM python:3.12-slim AS runtime`** — the second, final stage starts completely fresh from the same slim base; nothing from the builder's `apt-get` layer or pip build cache carries over.
- **`COPY --from=builder /opt/venv /opt/venv`** — the *only* thing copied from the builder is the finished virtual environment. This is the entire point of a multi-stage build: the compiler toolchain and pip's download cache (which can be substantial) never appear in the final image layers.
- **`useradd ... appuser` / `USER appuser`** — the container runs as a non-root, unprivileged user. If the application process were somehow compromised, it would not have root privileges inside its own container — a standard container-hardening practice.
- **`PYTHONDONTWRITEBYTECODE=1`** — skip writing `.pyc` files (irrelevant in a container that's rebuilt from scratch each deploy, not reused across restarts).
- **`PYTHONUNBUFFERED=1`** — Python's stdout is unbuffered, so `docker logs` / `docker compose logs` shows output immediately rather than batched — this mattered directly when diagnosing the deploy incidents in `18_Debugging.md`, where reading real-time container logs was the actual debugging tool.
- **`HEALTHCHECK`** — Docker itself polls `/health` inside the container's own network namespace every 30 seconds; `docker compose ps` and `depends_on: condition: service_healthy` (in `docker-compose.yml`) both key off this.
- **Final image size**: ~2.6GB, dominated by torch + transformers + chromadb — an honest number, not hidden; the size trade-off is discussed in `17_Performance.md`.

## `docker-compose.yml` — service topology

```yaml
services:
  api:
    build: .
    env_file: [.env]
    volumes: [app-data:/app/data]
    # No host port published on purpose — nginx is the sole public entrypoint.
    healthcheck: { test: [...], interval: 30s, timeout: 5s, retries: 3, start_period: 30s }

  nginx:
    image: nginx:1.27-alpine
    depends_on: { api: { condition: service_healthy } }
    ports: ["80:80", "443:443"]
    volumes:
      - ./deploy/nginx/rag-chatbot.conf:/etc/nginx/conf.d/default.conf:ro
      - certbot-etc:/etc/letsencrypt
      - certbot-www:/var/www/certbot

  certbot:
    image: certbot/certbot:latest
    profiles: ["certbot"]     # not started by `docker compose up`
    volumes: [certbot-etc:/etc/letsencrypt, certbot-www:/var/www/certbot]

volumes: { app-data:, certbot-etc:, certbot-www: }
```

- **`api` has no `ports:` mapping** — the most consequential line in the whole file. It means the FastAPI container is reachable *only* from other containers on the same Docker-created network (as `api:8000`), never directly from the host's network interfaces. This was discovered as a necessity (an unrelated container on the dev machine already held port 8000) and then kept deliberately, since it's the correct security posture regardless — see `16_Security.md` and the incident in `18_Debugging.md` that this same decision later caused.
- **`depends_on: condition: service_healthy`** — nginx won't even start routing traffic until Docker's own healthcheck on `api` reports healthy, avoiding a startup race where nginx proxies to a container that isn't ready yet.
- **Named volumes** (`app-data`, `certbot-etc`, `certbot-www`) persist data across container recreation — critically, `app-data` is where the SQLite database and vector store live, so redeploying the `api` container (a new image, same volume) doesn't wipe user data.
- **`certbot` has `profiles: ["certbot"]`** — Compose "profiles" mean this service is defined but never started by a plain `docker compose up`; it only runs when explicitly invoked (`docker compose --profile certbot run ...`), which is exactly the one-shot, occasional nature of certificate issuance/renewal.

## `.dockerignore`

Excludes `.venv/`, `.git/`, `tests/`, cache directories, and (critically) `.env` from the build context — so a real secret can never accidentally end up baked into an image layer, and the build context sent to the Docker daemon stays small.

## Build → run lifecycle in this project

1. `docker compose build` (or the CD pipeline's `docker/build-push-action`) produces the image.
2. `docker compose up -d` creates and starts both containers, attaches them to a private bridge network, and creates the named volumes on first run.
3. On every redeploy, only the `api` container is recreated (`docker compose up -d --no-build` after a `docker pull` + `docker tag`, per `deploy/ec2/deploy.sh`) — `nginx` keeps running unless its own config changes.
4. `docker image prune -f` after each deploy removes now-unreferenced old image layers, keeping disk usage bounded on the small EC2 instance.
