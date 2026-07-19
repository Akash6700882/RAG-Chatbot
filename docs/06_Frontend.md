# 06 — Frontend

## Correcting a common assumption

If you've seen a generic documentation template for this kind of project, it probably assumes **React + Vite + TypeScript**. That is *not* what this project uses, and this document describes what's actually there rather than a fictional stack — claiming React/hooks/routing/state-management in an interview for a project that doesn't have any of that would fall apart on the first follow-up question.

## What's actually there

`app/static/index.html` — **one file**. No framework, no bundler, no build step, no `node_modules`, no TypeScript. Plain HTML, a `<style>` block, and a `<script>` block using the browser's native `fetch()` API.

It's served by FastAPI itself:

```python
# app/main.py
static_dir = Path(__file__).parent / "static"
app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")
```

`StaticFiles(..., html=True)` tells Starlette to serve `index.html` when the mounted path is requested directly — so visiting `/ui` (or `/ui/`) just works, with zero routing code beyond that one line.

## Why a static single-page file, deliberately

- **The job it does is small**: three forms (auth, upload, chat) and a scrolling message log. A component framework's benefits (reusable stateful components, virtual DOM diffing, client-side routing) don't pay for themselves at this scale.
- **Zero build step** means zero build-tool version drift, zero `npm install` step in Docker, and zero possibility of "works on my machine, breaks in CI" caused by a lockfile mismatch.
- **Same-origin API calls**: the frontend calls `/api/v1/...` with a *relative* path, not an absolute URL:

```javascript
const API_BASE = "/api/v1";
async function api(path, options = {}) {
  const headers = options.headers || {};
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(API_BASE + path, { ...options, headers });
  ...
}
```

Because the frontend is served by the exact same FastAPI process (and, in production, from behind the exact same NGINX host) as the API it calls, there is **no CORS configuration needed at all** — a cross-origin request never happens. This is a direct, deliberate consequence of not splitting frontend and backend into separate deployments.

## What the page actually does

1. **Auth section** — email/password inputs, `Register` and `Login` buttons. On login, the returned JWT is held in a plain JS variable (`let token = null;`) — not `localStorage`, so it's cleared on page refresh. That's an intentional simplicity trade-off for a demo, not a production session-persistence strategy.
2. **Documents section** — a file input + `Upload` button (posts `multipart/form-data` to `/api/v1/upload`), and a list of the current user's documents with per-row `Delete` buttons, refreshed after every upload/delete.
3. **Chat section** — a scrolling message log and a text input. Each response's `sources` array (when non-empty) is rendered under the assistant's bubble.

## A security detail worth naming in an interview

Message content is inserted into the DOM via `textContent`, not `innerHTML`:

```javascript
div.innerHTML = `<div class="role">${role}</div><div class="bubble"></div>${sourcesHtml}`;
div.querySelector(".bubble").textContent = content;
```

The static wrapper markup (role label, empty bubble div, sources block) is built with `innerHTML`, but the actual **user- and LLM-generated text** is assigned via `.textContent`, which the browser treats as plain text, never as HTML/script — closing off a straightforward stored-XSS vector where a malicious chat message or filename containing `<script>` tags could otherwise execute in another user's browser.

## What would change if this needed to become a "real" frontend

If requirements grew — multiple pages, client-side routing, complex shared state, a design system — the natural next step would be React (or similar) with Vite as the dev/build tool and TypeScript for the API contract types, served as a separate static build artifact (potentially still from the same NGINX, just a different mounted path or a CDN). That's a real, defensible next step to describe in an interview — but it's future work, not what exists today.
