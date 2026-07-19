# 15 — GitHub Actions (CI/CD)

Two workflow files: `ci.yml` (validates every change) and `cd.yml` (ships every change on `main` to production). This document walks through both, line by line.

## `ci.yml` — continuous integration

```yaml
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }
```

**Trigger**: every push to `main`, and every pull request targeting `main`. This means a PR gets validated *before* merge, not just after.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    env:
      ANTHROPIC_API_KEY: ci-test-key
      JWT_SECRET_KEY: ci-test-secret
```

**Runner**: a fresh, ephemeral `ubuntu-latest` GitHub-hosted VM — no state persists between runs. The env vars here are deliberately fake — every LLM/embedding call in the test suite is mocked (see `03_Tech_Stack.md`), so no real credential, and no network call to any LLM provider, ever happens in CI. This is what makes the pipeline free to run as often as needed and immune to a provider being down or out of quota.

```yaml
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: "pip" }
      - run: pip install -r requirements.txt
      - run: ruff check app tests
      - run: ruff format --check app tests
      - run: pytest -q
```

Five steps: fetch the code, install Python 3.12 with pip's cache enabled (faster repeat runs), install dependencies, lint, format-check, then run all 45 tests. Any non-zero exit code from any step fails the job and blocks the workflow from proceeding — `ruff check`/`ruff format --check`/`pytest` all exit non-zero on any violation or test failure.

```yaml
  docker-build:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v6
        with: { context: ., push: false, tags: rag-chatbot-api:ci, cache-from: type=gha, cache-to: type=gha,mode=max }
```

**`needs: test`** — this second job only runs if `test` succeeded, avoiding wasting a multi-minute Docker build on code that already failed linting or tests. `push: false` — the image is built to prove the `Dockerfile` is valid and buildable, but never published; that's `cd.yml`'s job. `cache-from`/`cache-to: type=gha` caches Docker layers in GitHub Actions' own cache backend, so unchanged layers (like the CPU-torch install) aren't rebuilt from scratch on every run.

## `cd.yml` — continuous deployment

```yaml
on:
  push: { branches: [main] }
  workflow_dispatch: {}
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
```

**Trigger**: every push to `main` (deploy-on-merge), plus `workflow_dispatch` — a manual "Run workflow" button in the GitHub UI, used repeatedly during development to re-trigger a deploy without needing a new commit each time.

### Job 1 — `build-and-push`

```yaml
    permissions: { contents: read, packages: write }
```

**Explicit least-privilege permissions** for the auto-generated `GITHUB_TOKEN` used in this job — it can read repo contents and write to GitHub Packages (GHCR), nothing more.

```yaml
      - uses: docker/login-action@v3
        with: { registry: ghcr.io, username: ${{ github.actor }}, password: ${{ secrets.GITHUB_TOKEN }} }
```

Logs in to GHCR using the workflow's own automatically-provided `GITHUB_TOKEN` — no separate registry credential needed to be created or stored.

```yaml
      - name: Compute lowercase image name
        run: echo "lowercase=$(echo '${{ env.IMAGE_NAME }}' | tr '[:upper:]' '[:lower:]')" >> "$GITHUB_OUTPUT"
```

This step exists because of a real bug found in production — see `18_Debugging.md`, incident 2. `github.repository` preserves the repository's actual case (`Akash6700882/RAG-Chatbot`), but Docker image references must be lowercase. This step normalizes the name once and every later step reuses that single output, guaranteeing the tag used to *build* and the tag used to *deploy* can never drift apart again.

```yaml
      - uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ steps.image_name.outputs.lowercase }}
          tags: |
            type=sha,prefix=,format=long
            type=raw,value=latest,enable={{is_default_branch}}
```

Generates two tags per build: the full git commit SHA (always) and `latest` (only on the default branch) — so every image is traceable back to an exact commit, while `latest` still exists for convenience.

```yaml
      - uses: docker/build-push-action@v6
        with: { context: ., push: true, tags: ..., cache-from: type=gha, cache-to: type=gha,mode=max }
    outputs:
      image_sha_tag: ${{ env.REGISTRY }}/${{ steps.image_name.outputs.lowercase }}:${{ github.sha }}
```

Actually builds and pushes (`push: true`, unlike CI's build check). The job's `outputs.image_sha_tag` is how the *next* job learns exactly which image tag to deploy.

### Job 2 — `deploy`

```yaml
  deploy:
    needs: build-and-push
    if: github.ref == 'refs/heads/main'
```

Only runs after `build-and-push` succeeds, and only on `main` (so a manual `workflow_dispatch` on a different ref wouldn't attempt to deploy from it).

```yaml
      - name: Check whether EC2 deploy secrets are configured
        run: |
          if [ -n "$EC2_HOST" ] && [ -n "$EC2_SSH_KEY" ]; then
            echo "configured=true" >> "$GITHUB_OUTPUT"
          else
            echo "configured=false" >> "$GITHUB_OUTPUT"
          fi
```

A deliberate design choice: **before any EC2 infrastructure existed**, this check let the pipeline run to completion and log a clear, actionable message rather than fail — so CI/CD stayed green from the very first commit that introduced it, and only started performing a real deploy once secrets were added weeks later, with no code change required to "turn it on."

```yaml
      - name: Deploy to EC2 over SSH
        if: steps.check.outputs.configured == 'true'
        uses: appleboy/ssh-action@v1.2.0
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USER || 'ubuntu' }}
          key: ${{ secrets.EC2_SSH_KEY }}
          envs: IMAGE
          script: |
            export IMAGE="${{ needs.build-and-push.outputs.image_sha_tag }}"
            cd /opt/rag-chatbot && ./deploy/ec2/deploy.sh
```

The actual deploy: SSH into the EC2 host using the stored private key, export the exact image tag just built as an environment variable, and run the deploy script (`deploy/ec2/deploy.sh`, fully documented in `14_AWS_Deployment.md`) — which pulls that specific image, retags it, reloads the compose stack, and polls a health check before declaring success or failure back to the Actions run.

## Secrets

Three repository secrets power the deploy job: `EC2_HOST` (the Elastic IP), `EC2_SSH_KEY` (the private half of the key pair created during provisioning), and `EC2_USER` (defaults to `ubuntu` if unset). None of these — nor any LLM API key — ever appear in a workflow file; they're referenced only via `${{ secrets.NAME }}`, which GitHub redacts from all logs automatically.

## Rollback

There is currently no automated rollback step. If a bad deploy shipped, the fastest manual recovery is: `workflow_dispatch` a re-run of `cd.yml` pointed at a previous good commit (by checking out that ref before deploying), or SSH in directly and run `deploy/ec2/deploy.sh` with `IMAGE` manually set to a known-good previous tag (every image is tagged by commit SHA specifically to make this possible). Automating this — e.g., keeping the last N image tags and a one-command rollback script — is a reasonable next hardening step.
