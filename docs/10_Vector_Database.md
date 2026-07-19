# 10 — Vector Database & Semantic Search

## The core idea: embeddings and semantic search

An **embedding** is a fixed-length list of numbers (a vector) that represents the *meaning* of a piece of text, produced by a neural network trained so that semantically similar text produces numerically nearby vectors. "How many vacation days do I get" and "What's the PTO policy" would embed to nearby vectors even though they share almost no words in common — that's the entire point: **semantic** search, matching on meaning, not keyword overlap.

This project uses `sentence-transformers/all-MiniLM-L6-v2` (via `langchain_huggingface.HuggingFaceEmbeddings`), which maps any input text to a 384-dimension vector, running entirely on CPU with no external API call.

## Similarity search & cosine similarity

To find which stored chunks are relevant to a question, you embed the question the same way you embedded the documents, then find the stored vectors *closest* to it. "Closest" here means **cosine similarity** — the cosine of the angle between two vectors, which measures how similarly *directed* they are regardless of magnitude. A cosine similarity near 1 means "pointing almost the same way" (semantically similar); near 0 means unrelated. Embeddings in this project are explicitly normalized (`encode_kwargs={"normalize_embeddings": True}`) so cosine similarity and dot-product similarity become equivalent — a common optimization, since dot product is cheaper to compute at scale.

`similarity_search(query, k=4)` returns the `k` stored chunks with the highest similarity to the query embedding — not a threshold-based "relevant or not" decision, which is exactly why the RAG pipeline's separate *validation* node exists (see `07_RAG_Pipeline.md`): top-k search always returns *something*, even if nothing is actually relevant.

## Why two vector store backends, behind one interface

```python
# app/vectorstore/base.py
class VectorStore(Protocol):
    def add_documents(self, documents: list[LCDocument], document_id: str) -> int: ...
    def similarity_search(self, query: str, k: int, filter: dict[str, str] | None = None) -> list[LCDocument]: ...
    def delete(self, document_id: str) -> None: ...
```

`ChromaVectorStore` and `FaissVectorStore` both implement this exact three-method shape, selected by `VECTOR_DB=chroma|faiss` via a factory:

```python
def get_vector_store() -> VectorStore:
    settings = get_settings()
    key = (settings.vector_db, settings.vector_db_path)
    if key not in _store_cache:
        _store_cache[key] = ChromaVectorStore() if settings.vector_db == "chroma" else FaissVectorStore()
    return _store_cache[key]
```

### ChromaDB

A persistent, purpose-built vector database — it manages its own on-disk storage (SQLite + a binary index) and collection semantics. Used as the default because it "just works" with minimal setup, closer to what a managed vector DB product would feel like.

### FAISS

Facebook AI Similarity Search — a bare, extremely fast in-process index library with **no built-in persistence and no concept of metadata-based deletion**. This project layers a small JSON manifest on top (`{document_id: [vector_ids]}`) specifically to support `DELETE /documents/{id}` — without it, there would be no way to know which of FAISS's raw vector IDs belonged to a given uploaded file:

```python
def delete(self, document_id: str) -> None:
    ids = self._manifest.pop(document_id, None)
    if ids and self._store is not None:
        self._store.delete(ids)
        self._persist()
```

Supporting both backends behind one interface is a deliberate demonstration that the abstraction *actually holds* — not just in the "happy path" of adding and searching, but in the harder case of understanding each backend's real limitations (FAISS's lack of native delete) well enough to work around them correctly.

## Owner-scoped filtering — applied uniformly, not trusted to either backend

```python
# app/vectorstore/base.py
def filter_documents_by_metadata(documents, filter):
    if not filter:
        return documents
    return [doc for doc in documents if all(doc.metadata.get(k) == v for k, v in filter.items())]
```

Both backends' `similarity_search` implementations over-fetch (`k * 4` candidates) and then apply this filter themselves, rather than relying on each backend's own native metadata-filter support (which differs in capability between Chroma and FAISS). This guarantees identical, correct owner-scoping behavior regardless of which backend is configured — a security property that shouldn't be backend-dependent.

## Metadata tagging at ingestion time

```python
# app/ingestion/pipeline.py
for chunk in chunks:
    chunk.metadata["document_id"] = document_id
    chunk.metadata["filename"] = filename
    chunk.metadata["owner_id"] = owner_id
```

Every chunk carries `owner_id` from the moment it's created — retrieval later filters on exactly this field (`app/rag/nodes/retrieve.py` passes `filter={"owner_id": state["owner_id"]}`), which is the entire multi-tenant isolation mechanism in one line.
