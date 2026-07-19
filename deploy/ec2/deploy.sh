#!/usr/bin/env bash
# Deploys the current image tag to this EC2 host. Invoked by the GitHub
# Actions cd.yml workflow over SSH; safe to run manually too.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/rag-chatbot}"
IMAGE="${IMAGE:?Set IMAGE to the fully-qualified image ref, e.g. ghcr.io/org/rag-chatbot:sha}"

cd "$APP_DIR"

echo "==> Pulling $IMAGE"
docker pull "$IMAGE"

echo "==> Retagging as local api:latest for docker-compose.yml"
docker tag "$IMAGE" rag-chatbot-api:latest

echo "==> Reloading stack"
docker compose pull --ignore-pull-failures || true
docker compose up -d --no-build

echo "==> Pruning old images"
docker image prune -f

echo "==> Waiting for health check"
# Checked through nginx on :80, not the api container directly — the api
# service intentionally has no host port published (nginx is the sole
# public entrypoint; see docker-compose.yml).
for _ in $(seq 1 20); do
    if curl -fs http://localhost/health > /dev/null; then
        echo "Service healthy."
        exit 0
    fi
    sleep 3
done

echo "Service did not become healthy in time" >&2
docker compose logs --tail=100 api
exit 1
