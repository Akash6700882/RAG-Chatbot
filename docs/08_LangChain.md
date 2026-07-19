# 08 — LangChain

## What LangChain is used for here

LangChain is **not** the orchestration layer in this project — LangGraph is (see `09_LangGraph.md`). LangChain's role is narrower and more concrete: it supplies the reusable building blocks that LangGraph's nodes are made of.

| LangChain component | Used where | What it provides |
|---|---|---|
| `PyPDFLoader`, `Docx2txtLoader`, `TextLoader` | `app/ingestion/loaders.py` | A consistent `.load() -> list[Document]` interface across three completely different file formats and parsing libraries |
| `RecursiveCharacterTextSplitter` | `app/ingestion/splitter.py` | Paragraph/sentence/word-aware chunking (see `07_RAG_Pipeline.md`) |
| `Document` (the `langchain_core.documents.Document` class) | Everywhere in `ingestion/` and `vectorstore/` | A standard `page_content` + `metadata` dict shape, so a PDF chunk and a Markdown chunk are indistinguishable to everything downstream |
| `ChatPromptTemplate` | `app/rag/prompts.py` | Templated, role-tagged (`system`/`human`) prompts with `{placeholder}` interpolation |
| `BaseChatModel` interface (implemented by `ChatAnthropic`, `ChatGoogleGenerativeAI`, `ChatGroq`) | `app/rag/llm.py` | One `.invoke(...)` method signature regardless of which of the three providers is active |
| `HuggingFaceEmbeddings` | `app/embeddings/huggingface.py` | Wraps `sentence-transformers` behind the same `Embeddings` interface Chroma/FAISS expect |
| `Chroma`, `FAISS` vector store wrappers | `app/vectorstore/` | LangChain-native wrappers around the underlying Chroma/FAISS client libraries |

## The pattern that recurs everywhere: `prompt | llm`

LangChain's "runnable" abstraction lets you compose a prompt template and a chat model with the `|` (pipe) operator:

```python
chain = QUERY_REWRITE_PROMPT | get_llm()
result = chain.invoke({"chat_history": history_text, "question": state["question"]})
```

This reads almost like shell piping: take the prompt template, fill in variables, pass the resulting messages to the LLM, get a response object back with `.content`. Every LLM-calling node in `app/rag/nodes/` follows exactly this shape — build the input dict, `chain.invoke(...)`, extract `.content`.

## Why LangChain instead of calling provider SDKs directly

Without LangChain, switching from Anthropic to Groq would mean rewriting every call site to match a different SDK's method names and response shapes. With LangChain, `app/rag/llm.py` is the *only* file that imports a provider-specific class — everything else programs against the shared `BaseChatModel` interface, so `LLM_PROVIDER=groq` versus `LLM_PROVIDER=anthropic` never requires touching a node file.

## A known trade-off, worth naming honestly

LangChain is a large, fast-moving library, and its APIs have shifted across major versions (the loaders used here, for instance, live in `langchain-community`, which is explicitly marked as being phased out in favor of standalone per-integration packages upstream — a deprecation warning surfaces in this project's own test output as a result). This is a real, current trade-off of depending on it: you get broad integration coverage, at the cost of occasional churn as the ecosystem consolidates. The mitigation here is that dependencies are version-pinned in `requirements.txt`, so an upstream change doesn't silently break the deployed app.
