# 18 — Debugging Journal (Real Incidents)

Every issue below actually happened during this project's build and deployment — none are hypothetical. Each is recorded as: symptom → root cause → fix → what it teaches. This is also the raw material for the STAR-format interview answers in `19_Interview_Preparation.md`.

---

### Incident 1 — `passlib` / `bcrypt` version incompatibility

- **Symptom**: `ValueError: password cannot be longer than 72 bytes, truncate manually if necessary`, thrown from inside `passlib`'s own internal bcrypt backend-detection routine — not from any application code, and not actually about a 72-byte password.
- **Root cause**: `passlib==1.7.4`'s bcrypt backend probes for a known historical bug in older bcrypt releases by hashing a test string; that probe itself broke against `bcrypt>=4.1`'s changed internal API, and `passlib` surfaced the resulting failure as a misleading error message.
- **Fix**: pinned `bcrypt==4.0.1` in `requirements.txt`, with an inline comment explaining exactly why, so a future contributor doesn't "helpfully" upgrade it back into the same failure.
- **Lesson**: when an error message doesn't match the code you actually wrote, check dependency versions before doubting your own logic.

### Incident 2 — a self-inflicted test bug: mocked LLM resetting on every call

- **Symptom**: a test asserting the hallucination-check retry loop actually retries kept producing the *first* (intentionally "bad") answer instead of the expected corrected second answer.
- **Root cause**: the test patched `get_llm` with `lambda: FakeListChatModel(responses=[...])` — a lambda that constructs a **brand-new** fake model instance on every call, silently resetting its scripted response index back to zero each time, so it always returned response #1.
- **Fix**: build the `FakeListChatModel` once, outside the lambda, and have the lambda return that single shared instance on every call.
- **Lesson**: test doubles need the exact same call-count/state semantics as the real object they're standing in for — a "fresh instance per call" is a very easy default to reach for that quietly breaks anything stateful.

### Incident 3 — Anthropic account blocked by billing, not code

- **Symptom**: `anthropic.BadRequestError: Your credit balance is too low to access the Anthropic API.`
- **Root cause**: account-level, not a bug — the request was correctly formed and authenticated, and reached Anthropic successfully.
- **Fix**: added Google Gemini and Groq as alternate providers behind the same `LLM_PROVIDER` switch (see Incident 4), rather than blocking further progress on one account's billing state.
- **Lesson**: an error surfacing all the way from a third-party API is not automatically your bug — verify where in the stack the failure actually originates before changing code.

### Incident 4 — Gemini free tier returning a hard zero quota

- **Symptom**: `429 RESOURCE_EXHAUSTED`, with the response body explicitly showing `limit: 0` for the free-tier request quota on that specific Google Cloud project.
- **Root cause**: the API key/project combination wasn't eligible for the expected free-tier allocation — most likely because the key wasn't generated as a fresh, dedicated AI Studio project.
- **Fix**: moved to Groq as the working provider for live verification; documented Gemini as a supported-but-currently-blocked option rather than silently dropping it.
- **Lesson**: "the request succeeded in reaching the provider and got a structured error back" is meaningfully different from "the request failed" — always read the actual error body, not just the status code.

### Incident 5 — `sources` field citing rejected documents on the fallback path

- **Symptom**: `/chat` returned its safe fallback answer ("I don't have enough information...") but still listed a `sources` array containing a document that was retrieved but explicitly judged *irrelevant* by the validation node.
- **Root cause**: the router built `sources` from whatever was in `retrieved_docs`, unconditionally — it had no way to know the final answer was the canned fallback rather than a real, context-grounded generation.
- **Fix**: added a `used_fallback: bool` field to `GraphState`, set only by the fallback node, and gated the `sources` list in `app/chat/router.py` on its absence.
- **Verification**: two new tests (one graph-level, one API-level) plus a live re-test against a real model — asked both an in-scope and an out-of-scope question and confirmed sources appeared only for the genuinely grounded answer.
- **Lesson**: this bug was only found by actually running the system against a real LLM and deliberately trying an adversarial input (an out-of-scope question) — it was invisible in every test that only exercised the happy path.

### Incident 6 — deploy script missing its executable bit

- **Symptom**: the CD pipeline's SSH deploy step failed with `./deploy/ec2/deploy.sh: Permission denied` (exit code 126).
- **Root cause**: the file was authored via a tool that writes file content without setting the executable bit; `git` tracked it as mode `644`, so it was never executable on any clone, including the one on the EC2 host.
- **Fix**: `chmod +x` directly on the running server for an immediate unblock, and `git update-index --chmod=+x deploy/ec2/deploy.sh` committed so every future clone gets the correct mode `755`.
- **Lesson**: file permissions are part of a repository's tracked state, not just local filesystem metadata — and are easy to lose silently depending on how a file was created.

### Incident 7 — Docker rejecting a mixed-case image reference

- **Symptom**: `invalid reference format: repository name (Akash6700882/RAG-Chatbot) must be lowercase`.
- **Root cause**: `github.repository` preserves the repository's real case. The image *build and push* step worked anyway, because `docker/metadata-action` normalizes case internally — but the deploy job used a separately constructed string built from the raw, un-normalized value, so the two didn't actually match at the byte level even though they looked equivalent.
- **Fix**: added one workflow step to lowercase the name exactly once, and made every later reference (build tags *and* the deploy target) reuse that single computed value.
- **Lesson**: when two code paths need to agree on a derived value (here: an image tag), compute it once and share it — don't let it be independently re-derived in two places that can silently drift apart.

### Incident 8 — health check probing a port that was intentionally closed

- **Symptom**: `deploy.sh` reported `Service did not become healthy in time` and failed the pipeline — while the container's own logs, visible in the same failed run, showed `/health` returning `200 OK` repeatedly, and Docker's own healthcheck already reported the container `healthy`.
- **Root cause**: the deploy script's health probe checked `http://localhost:8000/health` directly on the EC2 host — but that host port had been deliberately removed from `docker-compose.yml` much earlier (NGINX is the sole public entrypoint; see `13_Docker.md`). The deploy script was simply never updated to reflect that earlier, unrelated architectural decision.
- **Fix**: changed the probe to `http://localhost/health`, routed through NGINX on port 80 — matching how the service is actually reachable from anywhere, including from the host itself.
- **Lesson**: a passing container-level healthcheck and a passing *external* health probe are two different claims — a script written before an architecture change can silently stop testing what it thinks it's testing, and only a live deployment run exposes the gap.

### Incident 9 — DNS pointing at a parking page, not the server

- **Symptom**: the purchased domain resolved to `162.255.119.127` (the registrar's default parking-page IP) instead of the server's Elastic IP, for several checks in a row.
- **Root cause**: a new A record had been added in the registrar's UI, but not actually saved — a specific "click the green checkmark to commit this row" step in Namecheap's Advanced DNS editor had been missed.
- **Diagnosis method**: direct DNS queries to public resolvers (`1.1.1.1`, `8.8.8.8`) were silently blocked on the local network, producing misleading timeouts. Switching to a DNS-over-HTTPS query (`https://dns.google/resolve?...`, plain HTTPS, unaffected by that block) against the domain's *authoritative* nameservers gave a reliable, unambiguous answer: no A record existed at all yet, ruling out a propagation-delay explanation.
- **Fix**: the record was re-entered and explicitly saved; DNS then resolved correctly within minutes.
- **Lesson**: when a network-level diagnostic tool gives suspicious results, question the diagnostic path itself (a blocked query looks a lot like "no answer yet") before concluding the thing you're testing is broken.

---

## The pattern across all of these

None of incidents 6–9 were catchable by the automated test suite — they exist entirely at the seam between the repository and a real external system (a real server's filesystem permissions, a real registry's case-sensitivity rules, a real network topology, a real DNS registrar's UI). This is the single strongest argument, in this project, for why "I deployed it and debugged the real failures" is a materially stronger claim than "I wrote deployment configuration."
