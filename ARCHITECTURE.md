# Architecture

This document explains how every piece of Doc RAG fits together — from the moment a file hits the system to the moment an answer reaches the user.

---

## Table of Contents

- [System Overview](#system-overview)
- [Data Flow: Ingestion](#data-flow-ingestion)
- [Data Flow: Querying](#data-flow-querying)
- [Data Flow: Live File Sync](#data-flow-live-file-sync)
- [Component Deep Dives](#component-deep-dives)
  - [FastAPI Backend](#fastapi-backend)
  - [Agentic Query Router](#agentic-query-router)
  - [RAG Pipeline](#rag-pipeline)
  - [Vector Store Layer](#vector-store-layer)
  - [Database Layer](#database-layer)
  - [File Reader](#file-reader)
  - [Chunking Engine](#chunking-engine)
  - [Sync Service](#sync-service)
  - [Folder Watcher](#folder-watcher)
  - [Streamlit Frontend](#streamlit-frontend)
- [Database Schema](#database-schema)
- [Key Design Decisions](#key-design-decisions)
- [How to Run](#how-to-run)

---

## System Overview

```
   ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
   │                  │       │                  │       │                  │
   │  Streamlit UI    │       │  API Clients     │       │  File Drop       │
   │  (Browser)       │       │  (curl, scripts) │       │  (./data folder) │
   │                  │       │                  │       │                  │
   └────────┬─────────┘       └────────┬─────────┘       └────────┬─────────┘
            │                          │                          │
            │ HTTP                     │ HTTP                     │ File Events
            │                          │                          │
            ▼                          ▼                          ▼
   ┌───────────────────────────────────────────┐       ┌────────────────────┐
   │                                           │       │                    │
   │       FastAPI Backend (main.py)           │       │   Folder Watcher   │
   │                                           │       │(folder_watcher.py) │
   │ ┌────────────────┐     ┌────────────────┐ │       │                    │
   │ │   /documents   │     │ /chat & /query │ │       │ ┌────────────────┐ │
   │ │  (Ingestion)   │     │   (Retrieval)  │ │       │ │  SyncHandler   │ │
   │ └──────┬─────────┘     └────────┬───────┘ │       │ └────────┬───────┘ │
   │        │                        │         │       │          │         │
   │        │                        ▼         │       │          ▼         │
   │        │               ┌────────────────┐ │       │ ┌────────────────┐ │
   │        │               │ Agent Service  │ │       │ │  Sync Service  │ │
   │        │               │ (Query Router) │ │       │ │ (Ingest/Erase) │ │
   │        │               └────────┬───────┘ │       │ └────────┬───────┘ │
   │        │                        │         │       │          │         │
   │        │                        ▼         │       │          │         │
   │        │               ┌────────────────┐ │       │          │         │
   │        │               │  RAG Service   │ │       │          │         │
   │        │               │(Retrieve & Gen)│ │       │          │         │
   │        │               └────────┬───────┘ │       │          │         │
   └────────┼────────────────────────┼─────────┘       └──────────┼─────────┘
            │                        │                            │
            ▼                        ▼                            ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │                              DATA STORES                               │
   │                                                                        │
   │  ┌──────────────────┐   ┌──────────────────┐   ┌───────────────────┐   │
   │  │                  │   │                  │   │                   │   │
   │  │      MySQL       │   │ FAISS / Pinecone │   │    Gemini API     │   │
   │  │   (Relational    │   │ (Vector Search   │   │  (Embeddings &    │   │
   │  │    Metadata)     │   │    Index)        │   │   LLM Generation) │   │
   │  │                  │   │                  │   │                   │   │
   │  └──────────────────┘   └──────────────────┘   └───────────────────┘   │
   └────────────────────────────────────────────────────────────────────────┘
```

The system has three user-facing entry points:

1. **Streamlit UI** — Browser-based chat interface for uploading documents and asking questions
2. **REST API** — Direct HTTP access via curl or any API client
3. **File drop** — Place files in `./data` and they're automatically ingested

All three entry points write to the same MySQL database and vector store.

---

## Data Flow: Ingestion

When a document enters the system (via API upload or file drop), it follows this path:

```
┌──────────┐     ┌──────────┐     ┌────────────┐     ┌──────────┐     ┌──────────┐
│  Raw     │     │  Plain   │     │  Text      │     │  768-dim │     │  Stored  │
│  File    │────▶│  Text    │────▶│  Chunks    │────▶│  Vectors │────▶│  in DB   │
│          │     │          │     │  (~500 tok)│     │          │     │  + Index │
└──────────┘     └──────────┘     └────────────┘     └──────────┘     └──────────┘
  file_reader.py   extract_text     chunking.py       Gemini API      MySQL +
  (PDF/CSV/         from_file()     chunk_text()      embed_content   FAISS/Pinecone
   JSON/DOCX/TXT)
```

### Step by step:

1. **File reading** (`app/utils/file_reader.py`) — `extract_text_from_file()` detects the file extension and uses the appropriate library to extract plain text. PDF uses `pdfplumber`, DOCX uses `python-docx`, CSV uses the stdlib `csv` module, JSON is recursively flattened into key-value lines.

2. **Content hashing** — A SHA-256 hash of the raw text is computed. This fingerprint is stored in the `Document.content_hash` column so future re-uploads can be detected without re-processing.

3. **Chunking** (`app/utils/chunking.py`) — `chunk_text()` splits the text into ~500-token pieces with 50-token overlap using the `tiktoken` tokenizer (`cl100k_base`). The overlap ensures context isn't lost at chunk boundaries.

4. **Database storage** (`app/models/document.py`) — A `Document` row is created in MySQL with `title`, `source_path`, and `content_hash`. Then a `DocumentChunk` row is created for each chunk, with `chunk_text` and a denormalized `source_path`.

5. **Embedding** (`app/services/embedding_service.py` or `pinecone_service.py`) — All chunks are embedded in a single batched call to the Gemini API (`gemini-embedding-001`, 768 dimensions, `RETRIEVAL_DOCUMENT` task type).

6. **Vector indexing** — The embedding vectors are inserted into the vector store with metadata: `{document_id, chunk_id, source_path}`. For FAISS, this is an in-memory index saved to `faiss_index.bin`. For Pinecone, it's an API upsert to the cloud index.

---

## Data Flow: Querying

When a user asks a question, it flows through the agentic router:

```
┌───────────┐     ┌──────────────┐     ┌────────────────────────────────────┐
│  User     │     │   Intent     │     │          Handler                   │
│  Question │────▶│  Classifier  │────▶│                                    │
│           │     │  (Gemini)    │     │  Simple ──▶ Direct LLM answer      │
└───────────┘     └──────────────┘     │  Knowledge ──▶ RAG pipeline        │
                                       │  Multi-Step ──▶ Decompose → RAG    │
                                       │                  → Synthesize      │
                                       └────────────────────────────────────┘
```

### Intent classification (`app/services/agent_service.py`)

The agent sends the user's question to Gemini with a classification prompt. The LLM responds with exactly one word:

| Intent | When | What happens |
|---|---|---|
| **Simple** | Greetings, definitions, general knowledge | Gemini answers directly — no documents searched |
| **Knowledge** | Single focused question about the documents | Standard RAG: search → retrieve → generate |
| **Multi-Step** | Complex comparisons, multi-part questions | Decomposed into 2–4 sub-questions, each goes through RAG, then sub-answers are synthesized |

### RAG pipeline (`app/services/rag_service.py`)

For Knowledge and Multi-Step intents:

1. **Embed the query** — The user's question is embedded using `RETRIEVAL_QUERY` task type (optimized for searching, not storing).

2. **Vector search** — The query vector is compared against all indexed chunks. FAISS uses L2 distance; Pinecone uses cosine similarity. Top-K results (default 3) are returned.

3. **Fetch chunk text** — The chunk IDs from the vector search are used to look up the actual text from MySQL. This is why we store text in MySQL and vectors in FAISS/Pinecone separately.

4. **Build prompt** — A prompt is constructed with system instructions, the retrieved context chunks, and the user's question. The LLM is instructed to respond in JSON with `answer` and `sources` fields.

5. **Generate answer** — The prompt is sent to Gemini (`gemini-2.5-flash`). The response is parsed from JSON. If the LLM doesn't return valid JSON, the raw text is used as the answer.

---

## Data Flow: Live File Sync

The folder watcher creates a feedback loop between the filesystem and the database:

```
┌──────────────────────────────────────────────────┐
│               ./data folder                      │
│                                                  │
│   report.pdf   handbook.json   policy.docx       │
│       │              │              │            │
└───────┼──────────────┼──────────────┼────────────┘
        │              │              │
        │       watchdog Observer     │
        │              │              │
        ▼              ▼              ▼
┌──────────────────────────────────────────────────┐
│             SyncHandler events                   │
│                                                  │
│   on_created  → handle_new_file()                │
│   on_modified → handle_modified_file()           │
│   on_deleted  → handle_deleted_file()            │
└──────────────────────────────────────────────────┘
        │              │              │
        ▼              ▼              ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │  MySQL  │   │ Vector  │   │  Gemini │
   │         │   │  Store  │   │   API   │
   └─────────┘   └─────────┘   └─────────┘
```

### The three sync operations (`app/services/sync_service.py`)

**`handle_new_file(file_path)`** — Full ingestion: read → hash → chunk → save to MySQL → embed → insert into vector DB.

**`handle_deleted_file(file_path)`** — Cleanup: look up by `source_path` → remove vectors from vector DB → delete Document row from MySQL (chunks cascade-delete).

**`handle_modified_file(file_path)`** — Change detection + re-sync:
1. Read the file and compute its SHA-256 hash
2. Compare against the stored hash in `Document.content_hash`
3. If unchanged → skip (no API calls wasted)
4. If changed → call `handle_deleted_file()` then `handle_new_file()`

### Why delete-then-reinsert?

When a file is modified, we don't try to diff individual chunks. Instead, we delete all chunks from the old version and re-ingest from scratch. This is simpler and more reliable than trying to figure out which specific chunks changed. For most document sizes, the cost of re-embedding is negligible.

---

## Component Deep Dives

### FastAPI Backend

**File:** `main.py`

The entry point creates the FastAPI app, ensures database tables exist, loads the FAISS index from disk, and registers all API routes.

```python
Base.metadata.create_all(bind=engine)  # Create tables if they don't exist
load_index()                           # Load FAISS from disk (no-op for Pinecone)
app = FastAPI(title="Doc RAG API")
app.include_router(api_router)         # Register /documents, /chat, /query
```

**API routes are split into two files:**

- `app/api/documents.py` — CRUD for documents (`POST /documents`, `GET /documents`, `DELETE /documents/{id}`)
- `app/api/chat.py` — Query endpoints (`POST /chat`, `POST /query`)

---

### Agentic Query Router

**File:** `app/services/agent_service.py`

The router is the "brain" that decides how to handle each question. It's not a traditional router — it uses an LLM to classify intent.

```
User question → classify_intent() → "Simple" / "Knowledge" / "Multi-Step"
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
             handle_simple()      handle_knowledge()     handle_multi_step()
             Direct LLM call      Single RAG pass        Decompose → N × RAG
                                                         → Synthesize
```

For Multi-Step queries, the agent:
1. Asks Gemini to decompose the question into 2–4 sub-questions
2. Runs each sub-question through the RAG pipeline independently
3. Collects all sub-answers and their sources
4. Sends everything to Gemini one more time to synthesize a final answer

---

### RAG Pipeline

**File:** `app/services/rag_service.py`

Three functions, called in sequence:

| Function | Input | Output |
|---|---|---|
| `retrieve_chunks(query, top_k)` | User's question | List of chunk dicts with text, IDs, distances |
| `build_prompt(query, chunks)` | Question + retrieved chunks | A single string prompt for the LLM |
| `generate_answer(query, chunks)` | Question + retrieved chunks | `{"answer": "...", "sources": [...]}` |

The prompt instructs the LLM to:
- Answer based ONLY on the provided context
- Respond with valid JSON
- Include only the sources it actually used

---

### Vector Store Layer

**File:** `app/services/vector_store_service.py`

This is a thin switcher module. It reads the `VECTOR_STORE` environment variable and imports the matching backend:

```python
if VECTOR_STORE == "pinecone":
    from app.services.pinecone_service import ...
else:
    from app.services.embedding_service import ...
```

Both backends expose the same six functions:

| Function | Purpose |
|---|---|
| `get_embeddings(texts)` | Batch-embed document chunks (768-dim, `RETRIEVAL_DOCUMENT`) |
| `get_query_embedding(query)` | Embed a search query (768-dim, `RETRIEVAL_QUERY`) |
| `add_to_index(embeddings, doc_id, chunk_ids, source_path)` | Store vectors with metadata |
| `search_index(query, top_k)` | Find the K nearest chunks to a query |
| `remove_from_index(document_id, source_path)` | Delete vectors by document ID and/or filename |
| `save_index()` / `load_index()` | Persist to disk (FAISS) or no-op (Pinecone) |

**FAISS** (`app/services/embedding_service.py`) — Stores vectors in an in-memory `IndexFlatL2` index. Metadata (document_id, chunk_id, source_path) is kept in a parallel Python list. Both are serialized to `faiss_index.bin` and `faiss_metadata.npy`.

**Pinecone** (`app/services/pinecone_service.py`) — Vectors are stored in a managed cloud index. Metadata is stored natively as Pinecone metadata fields, enabling server-side filtering on queries and deletes.

---

### Database Layer

**File:** `app/database/connection.py`

Uses SQLAlchemy with a MySQL backend (via PyMySQL driver):

```python
engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
```

`pool_pre_ping=True` ensures stale database connections are detected and recycled automatically.

---

### File Reader

**File:** `app/utils/file_reader.py`

A single function `extract_text_from_file(file_path)` that uses an `if/elif` block to dispatch to the right parser:

| Extension | Library | Strategy |
|---|---|---|
| `.pdf` | pdfplumber | Page-by-page text extraction, joined with double newlines |
| `.csv` | csv (stdlib) | Each row becomes a comma-separated line; header included |
| `.json` | json (stdlib) | Recursively flattened into `dotted.key: value` lines |
| `.docx` | python-docx | Paragraph text extracted, blank paragraphs skipped |
| `.txt`, `.md` | built-in open() | Read as-is |

---

### Chunking Engine

**File:** `app/utils/chunking.py`

Uses `tiktoken` (the same tokenizer behind GPT models) to split text into fixed-size token windows:

- **Max tokens per chunk:** 500 (configurable)
- **Overlap tokens:** 50 (configurable)
- **Tokenizer:** `cl100k_base`

The overlap ensures that if a sentence spans two chunks, both chunks contain it. This prevents information loss at chunk boundaries.

---

### Sync Service

**File:** `app/services/sync_service.py`

Three procedural functions that bridge the file system and the database:

| Function | When to call | What it does |
|---|---|---|
| `handle_new_file(file_path)` | New file detected | Extract → hash → chunk → save to MySQL → embed → add to vector DB |
| `handle_deleted_file(file_path)` | File removed | Look up by source_path → remove vectors → delete from MySQL |
| `handle_modified_file(file_path)` | File content changed | Compare hash → if changed: delete old + ingest new |

These functions are called by the folder watcher but can also be called independently (e.g., from a script).

---

### Folder Watcher

**File:** `folder_watcher.py`

A standalone script using the `watchdog` library. It runs an `Observer` thread that polls the filesystem and dispatches events to a `SyncHandler`:

| Filesystem event | Handler method | Sync function |
|---|---|---|
| File created | `on_created` | `handle_new_file()` |
| File modified | `on_modified` | `handle_modified_file()` |
| File deleted | `on_deleted` | `handle_deleted_file()` |

The handler filters events by file extension (only `.pdf`, `.csv`, `.json`, `.docx`, `.txt`, `.md`) and ignores directory events.

A 1-second delay is added after `on_created` and `on_modified` events to ensure the file content is fully flushed to disk before reading it.

---

### Streamlit Frontend

**File:** `streamlit_app/app.py`

The browser UI provides:

- **Sidebar:** Document upload (JSON file or pasted text), document list with delete buttons, vector store indicator
- **Chat area:** Message input, chat history, streaming responses

For each response, the UI displays:
- **Intent badge** — Shows whether the query was classified as Simple, Knowledge, or Multi-Step
- **Sub-questions** — If Multi-Step, shows the decomposed sub-questions
- **Answer** — The generated response
- **Retrieved chunks** — Expandable section showing each chunk's text, similarity score, and source document
- **Sources** — Which chunks the LLM actually cited in its answer

The frontend communicates exclusively via the `POST /chat` endpoint.

---

## Database Schema

```
┌───────────────────────────────────┐       ┌───────────────────────────────────┐
│           documents               │       │        document_chunks            │
├───────────────────────────────────┤       ├───────────────────────────────────┤
│ id           INT (PK, auto)       │       │ chunk_id      INT (PK, auto)      │
│ title        VARCHAR(255)         │──────▶│ document_id   INT (FK → doc.id)   │
│ source_path  VARCHAR(1024) [idx]  │       │ chunk_text    TEXT                │
│ content_hash VARCHAR(64)          │       │ source_path   VARCHAR(1024) [idx] │
│ created_at   DATETIME             │       └───────────────────────────────────┘
│ updated_at   DATETIME             │
└───────────────────────────────────┘
```

**Why is `source_path` on both tables?**

This is deliberate denormalization. The vector store (FAISS or Pinecone) needs `source_path` in its metadata to support filtering by filename. Since vector store metadata is a flat key-value store (no JOINs), we propagate the filename onto every chunk row so it can be passed through to the vector metadata at ingestion time.

---

## Key Design Decisions

### No LangChain

The entire system is built with plain Python functions. This makes the code easier to read, debug, and modify. Every step is explicit — there are no hidden chains or callbacks.

### Procedural over Object-Oriented

Functions are used instead of classes wherever possible. The sync service is three functions, not a `FileSyncManager` class. The file reader is one function with an `if/elif` block, not a parser factory. This prioritizes readability.

### Separate text storage and vector storage

Document text lives in MySQL. Embedding vectors live in FAISS/Pinecone. This separation means:
- We can switch vector backends without touching the text storage
- We can rebuild the vector index from MySQL at any time
- MySQL handles relational queries (e.g., "all chunks from document #5") while the vector store handles similarity search

### Delete-then-reinsert for updates

When a file is modified, we don't diff individual chunks. We delete everything associated with that file and re-ingest from scratch. This avoids the complexity of chunk-level diffing while being fast enough for typical document sizes.

### Content hashing for change detection

A SHA-256 hash of the raw file content is stored at ingestion time. On re-sync, the hash is compared before doing any work. If the file hasn't changed, no API calls are made. This prevents unnecessary re-embedding when the watcher fires spurious modification events.

---

## How to Run

### Development (three terminals)

```bash
# Terminal 1 — FastAPI backend
uv run uvicorn main:app --reload

# Terminal 2 — Folder watcher
uv run python folder_watcher.py

# Terminal 3 — Streamlit frontend
uv run streamlit run streamlit_app/app.py
```

### Background watcher

```bash
# Start in background (survives terminal close)
nohup uv run python folder_watcher.py > watcher.log 2>&1 &

# Check logs
tail -f watcher.log

# Stop
kill $(pgrep -f folder_watcher.py)
```

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | MySQL connection string |
| `GEMINI_API_KEY` | Yes | — | Google Gemini API key |
| `VECTOR_STORE` | No | `faiss` | `faiss` or `pinecone` |
| `WATCH_FOLDER` | No | `./data` | Folder for the watcher to monitor |
| `PINECONE_API_KEY` | If Pinecone | — | Pinecone API key |
| `PINECONE_INDEX_NAME` | No | `doc-rag` | Pinecone index name |
| `PINECONE_CLOUD` | No | `aws` | Pinecone cloud provider |
| `PINECONE_REGION` | No | `us-east-1` | Pinecone region |
