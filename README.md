# Doc RAG

A document question-answering system that lets you upload documents — or drop files into a folder — and ask questions about them. It uses retrieval-augmented generation (RAG) to ground answers in your actual data instead of making things up.

The backend is built with FastAPI, the frontend with Streamlit, embeddings and generation are handled by Google Gemini, and vector search runs on either FAISS (locally) or Pinecone (in the cloud). A file watcher powered by `watchdog` keeps the vector database automatically synced with a local folder.

Everything is written in plain, procedural Python. No LangChain, no heavy frameworks.

> **New to the project?** Read [`ARCHITECTURE.md`](ARCHITECTURE.md) for a deep dive into how every component works and how data flows through the system.

---

## Features

- **Agentic query routing** — An LLM classifies each question as Simple, Knowledge, or Multi-Step before deciding how to answer it. Simple questions get a direct response. Knowledge questions trigger a single RAG lookup. Multi-step questions are decomposed into sub-questions, each answered independently, then synthesized into a final response.

- **Document ingestion** — Upload documents through the UI, the API, or simply drop files into the `./data` folder. The system splits text into overlapping token-based chunks, generates embeddings via Gemini, and indexes them for retrieval.

- **Live file syncing** — A `watchdog`-based folder watcher monitors `./data` for new, modified, or deleted files. Changes are automatically reflected in both MySQL and the vector store — no manual re-upload needed.

- **Multi-format support** — Reads `.pdf`, `.csv`, `.json`, `.docx`, `.txt`, and `.md` files out of the box.

- **Change detection** — SHA-256 content hashing prevents unnecessary re-embedding when a file hasn't actually changed.

- **Swappable vector store** — Switch between local FAISS and cloud-hosted Pinecone by changing one environment variable. The rest of the code stays the same.

- **Chat interface** — A Streamlit frontend with intent badges, expandable retrieved chunks, similarity scores, and cited sources.

---

## Project Structure

```
doc-rag/
├── main.py                           # FastAPI entry point, creates tables, loads index
├── folder_watcher.py                 # Watchdog script — monitors ./data for file changes
│
├── app/
│   ├── api/
│   │   ├── documents.py              # POST/GET/DELETE /documents endpoints
│   │   └── chat.py                   # POST /query and POST /chat endpoints
│   ├── services/
│   │   ├── gemini_service.py         # Shared Gemini client initialization
│   │   ├── embedding_service.py      # FAISS index + Gemini embeddings
│   │   ├── pinecone_service.py       # Pinecone alternative to FAISS
│   │   ├── vector_store_service.py   # Reads VECTOR_STORE from .env, imports the right backend
│   │   ├── rag_service.py            # RAG pipeline: retrieve chunks, build prompt, generate answer
│   │   ├── agent_service.py          # Intent classification and query routing
│   │   └── sync_service.py           # handle_new/modified/deleted_file for live sync
│   ├── models/
│   │   └── document.py               # SQLAlchemy models (Document, DocumentChunk)
│   ├── schemas/
│   │   ├── document.py               # Pydantic schemas for document endpoints
│   │   ├── query.py                  # Pydantic schemas for /query endpoint
│   │   └── chat.py                   # Pydantic schemas for /chat endpoint
│   ├── database/
│   │   └── connection.py             # SQLAlchemy engine, session factory, base class
│   └── utils/
│       ├── chunking.py               # Token-based text splitting with overlap
│       └── file_reader.py            # Multi-format text extraction (PDF, CSV, JSON, DOCX, TXT)
│
├── streamlit_app/
│   └── app.py                        # Streamlit chat UI
<<<<<<< HEAD
├── scripts/
│   └── file_sync_demo.py             # Demo script showing the sync lifecycle
├── data/                             # Drop files here — the watcher auto-ingests them
├── tests/                            # Tests
=======
│
├── data/                             # Drop files here — the watcher auto-ingests them
│
>>>>>>> 81c1c29 (fixed streamlit frontend)
└── .env                              # API keys and config (not committed)
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- MySQL
- A Google Gemini API key ([get one here](https://aistudio.google.com/apikey))
<<<<<<< HEAD
=======
- **(Optional)** A Pinecone API key and Index Name, if you plan to use Pinecone instead of the local FAISS vector store.
>>>>>>> 81c1c29 (fixed streamlit frontend)

### 1. Install dependencies

```bash
brew install uv mysql
<<<<<<< HEAD
brew services start mysql
```

### 2. Create the database

=======
```

### 2. Start MySQL and create the database

First, ensure your MySQL service is running. If you are using Homebrew on macOS:
```bash
brew services start mysql
```

Then, create the database:
>>>>>>> 81c1c29 (fixed streamlit frontend)
```bash
mysql -u root -p -e "CREATE DATABASE doc_rag;"
```

### 3. Set up your environment

Create a `.env` file in the project root:

```env
<<<<<<< HEAD
VECTOR_STORE=faiss
DATABASE_URL=mysql+pymysql://root:yourpassword@localhost:3306/doc_rag
GEMINI_API_KEY=your-gemini-api-key
=======
# Vector Store config (faiss or pinecone)
VECTOR_STORE=faiss

# Database connection
DATABASE_URL=mysql+pymysql://root:yourpassword@localhost:3306/doc_rag

# Gemini API
GEMINI_API_KEY=your-gemini-api-key

# Pinecone config (only required if VECTOR_STORE=pinecone)
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_NAME=doc-rag-index
PINECONE_CLOUD=desired-cloud-provider-name
PINECONE_REGION=desired-region-name
>>>>>>> 81c1c29 (fixed streamlit frontend)
```

### 4. Start the backend

```bash
uv run uvicorn main:app --reload
```

### 5. Start the folder watcher (optional)

In a second terminal:

```bash
uv run python folder_watcher.py
```

This watches `./data` for file changes. Drop a `.pdf`, `.csv`, `.json`, `.docx`, or `.txt` file in and it will be automatically ingested.

### 6. Start the frontend

In a third terminal:

```bash
uv run streamlit run streamlit_app/app.py
```

Open http://localhost:8501 in your browser.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/documents` | Upload a document (auto-chunks and embeds it) |
| GET | `/documents` | List all uploaded documents |
| DELETE | `/documents/{id}` | Delete a document and its vectors |
| POST | `/chat` | Chat endpoint with agentic routing (used by the Streamlit UI) |
| POST | `/query` | Simpler query endpoint (returns answer + context) |

### Upload a document

```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Company Policy",
    "content": "Our refund policy allows returns within 30 days...",
    "source_path": "company_policy.txt"
  }'
```

### Ask a question

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the refund policy?"}'
```

---

## Live File Syncing

The folder watcher monitors `./data` and automatically:

| Event | What happens |
|---|---|
| File created | Text extracted → chunked → embedded → saved to MySQL + vector DB |
| File modified | Content hash compared → if changed, old version deleted, new version ingested |
| File deleted | Chunks removed from MySQL (cascade) + vectors removed from vector DB |

Supported file types: `.pdf`, `.csv`, `.json`, `.docx`, `.txt`, `.md`

```bash
# Example: drop a file in and it's instantly searchable
cp ~/Documents/quarterly_report.pdf ./data/

# Remove it and the vectors are cleaned up automatically
rm ./data/quarterly_report.pdf
```

---

## Switching Vector Stores

Change the `VECTOR_STORE` variable in `.env`:

```env
# Local (default):
VECTOR_STORE=faiss

# Cloud:
VECTOR_STORE=pinecone
```

If using Pinecone, also add:

```env
PINECONE_API_KEY=your-key
PINECONE_INDEX_NAME=doc-rag
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
```

Restart the server after changing the vector store.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | FastAPI + Uvicorn |
| Database | MySQL + SQLAlchemy |
| Vector Search | FAISS (local) / Pinecone (cloud) |
| Embeddings | Google Gemini `gemini-embedding-001` (768-dim) |
| LLM | Google Gemini `gemini-2.5-flash` |
| File Parsing | pdfplumber, python-docx, csv, json (stdlib) |
| Tokenizer | tiktoken (`cl100k_base`) |
| File Watching | watchdog |
| Package Manager | uv |
