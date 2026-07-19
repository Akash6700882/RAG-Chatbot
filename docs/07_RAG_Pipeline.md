# 07 — RAG Pipeline (Conceptual Overview)

## What RAG is, and the problem with naive implementations

Retrieval-Augmented Generation means: instead of asking an LLM a question directly (relying entirely on what it learned during training), you first **retrieve** relevant text from your own data, then **generate** an answer by giving the LLM that retrieved text as context alongside the question.

A *naive* RAG implementation is exactly three steps: embed the question → similarity search → stuff the top-k chunks into a prompt → generate. That's what the original prototype in this repo did (`VectorstoreIndexCreator` + `RetrievalQA.from_chain_type`, one call, no verification). The problem: it has no way to know whether the retrieved chunks were actually relevant, and no way to catch the LLM inventing details anyway — a hallucination silently ships as a confident-sounding answer.

## What this project does instead

Two extra checkpoints, each backed by a dedicated LLM call:

1. **Before generating** — a *context validation* step asks: "does what we retrieved actually contain the answer?" If not, skip generation entirely and return an honest "I don't know" rather than attempting a guess from irrelevant context.
2. **After generating** — a *hallucination check* step asks a second, independent question: "is this specific answer actually supported by the context we gave it?" If not, retry generation with a stricter prompt (bounded — it won't loop forever), and only fall back to the safe answer once the retry budget is exhausted.

This is the concrete implementation of "prompt engineering to reduce hallucinations": it's not a clever wording trick in a single prompt, it's a **verification pipeline** that assumes the first generation attempt might be wrong and checks before trusting it.

## End-to-end walkthrough (with the actual data)

Say a user uploads `employee_handbook.md` (containing a PTO policy) and asks: *"How many PTO days carry over to next year?"*

1. **Rewrite**: no prior chat history on turn one → skipped, question passed through unchanged (saves an LLM call — see `09_LangGraph.md`).
2. **Retrieve**: the question is embedded and compared against every stored chunk *belonging to this user* (owner-scoped). The top `RETRIEVAL_TOP_K` (default 4) chunks come back, including the one mentioning "Unused PTO up to 5 days may be carried over."
3. **Validate**: an LLM call is given the question + the retrieved chunk and asked `SUFFICIENT` or `INSUFFICIENT`. It says `SUFFICIENT`.
4. **Generate**: a second LLM call is given the same context and a strict instruction to answer only from it, citing the source filename. It produces: *"Unused PTO up to 5 days may be carried over into the next calendar year. (employee_handbook.md)"*
5. **Check hallucination**: a third LLM call is shown the context and the generated answer and asked to verify it. It says `GROUNDED`.
6. Done — the graph reaches `END`, and the router persists both messages and returns the answer with `sources: ["employee_handbook.md"]`.

Now say the user instead asks *"What is the capital of France?"* — a question the handbook can't answer:

1. **Retrieve** still returns *some* chunks (similarity search always returns its top-k, even if none are truly relevant).
2. **Validate** sees the question doesn't match the retrieved content and returns `INSUFFICIENT`.
3. The graph routes straight to **fallback** — generation never runs — returning the fixed, honest answer: *"I don't have enough information in the ingested documents to answer that confidently..."*, with an empty `sources` list.

This exact scenario was verified against a real deployed model (Groq), not just a mocked test — see `18_Debugging.md`.

## Chunking strategy

Documents are split with `RecursiveCharacterTextSplitter` (via LangChain), which tries to split on paragraph breaks first, then sentences, then words — only falling back to a hard character cut if nothing else fits within `CHUNK_SIZE`. Default: 1000 characters per chunk, 150 characters of overlap between consecutive chunks (so a sentence that straddles a chunk boundary isn't orphaned from its context in *both* neighboring chunks).

## Why validation and hallucination-checking are separate steps, not one

They check different things at different times. Validation asks a question about the *retrieved context relative to the question*, before any answer exists. Hallucination-checking asks a question about a *specific generated answer relative to that context*, after generation. Merging them into one step would conflate "we don't have the right information" with "the model made something up despite having the right information" — two different failure modes that call for two different responses (immediate fallback vs. bounded retry).
