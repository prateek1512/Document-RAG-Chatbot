# Doc RAG

A document question-answering system that lets you upload text documents and ask questions about them. It uses retrieval-augmented generation (RAG) to ground answers in your actual data instead of making things up.

The backend is built with FastAPI, the frontend with Streamlit, embeddings and generation are handled by Google Gemini, and vector search runs on either FAISS (locally) or Pinecone (in the cloud).

Everything is written in plain, procedural Python. No LangChain, no heavy frameworks.

---

## Features

- **Agentic query routing** -- An LLM classifies each question as Simple, Knowledge, or Multi-Step before deciding how to answer it. Simple questions get a direct response. Knowledge questions trigger a single RAG lookup. Multi-step questions are decomposed into sub-questions, each answered independently, then synthesized into a final response.

- **Document ingestion** -- Upload documents through the UI or API. The system splits text into overlapping token-based chunks, generates embeddings via Gemini, and indexes them for retrieval.

- **Swappable vector store** -- Switch between local FAISS and cloud-hosted Pinecone by changing one environment variable. The rest of the code stays the same.

- **Chat interface** -- A Streamlit frontend with intent badges, expandable retrieved chunks, similarity scores, and cited sources.

---

## Architecture

```
                    +----------------+
                    |   Streamlit    |
                    |   Frontend     |
                    +-------+--------+
                            | HTTP
                    +-------v--------+
                    |    FastAPI     |
                    |    Backend     |
                    +--+-----+----+-+
                       |     |    |
              +--------+     |    +--------+
              v              v             v
        +-----------+  +-----------+  +-----------+
        |   MySQL   |  |  FAISS /  |  |  Google   |
        |  (text)   |  | Pinecone  |  |  Gemini   |
        |           |  | (vectors) |  |   (LLM)   |
        +-----------+  +-----------+  +-----------+
```

---

## Components

| Component | What it does |
|---|---|
| MySQL | Stores document text, chunk text, and metadata (titles, timestamps, foreign keys) |
| FAISS / Pinecone | Stores 768-dimensional embedding vectors and runs similarity search against user queries |
| Gemini Embedding API | Converts text chunks and queries into embedding vectors (`gemini-embedding-001`) |
| Gemini LLM | Classifies query intent and generates answers from retrieved context (`gemini-2.5-flash`) |
| FastAPI | Serves the REST API that the frontend (and any external client) talks to |
| Streamlit | Provides the browser-based chat UI for uploading documents and asking questions |

---

## Project Structure

```
doc-rag/
├── main.py                           # FastAPI entry point, creates tables, loads index
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
│   │   └── agent_service.py          # Intent classification and query routing
│   ├── models/
│   │   └── document.py               # SQLAlchemy models (Document, DocumentChunk)
│   ├── schemas/
│   │   ├── document.py               # Pydantic schemas for document endpoints
│   │   ├── query.py                  # Pydantic schemas for /query endpoint
│   │   └── chat.py                   # Pydantic schemas for /chat endpoint
│   ├── database/
│   │   └── connection.py             # SQLAlchemy engine, session factory, base class
│   └── utils/
│       └── chunking.py               # Token-based text splitting with overlap
├── streamlit_app/
│   └── app.py                        # Streamlit chat UI
├── data/                             # Sample data files
├── tests/                            # Tests
└── .env                              # API keys and config (not committed)
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- MySQL
- A Google Gemini API key ([get one here](https://aistudio.google.com/apikey))

### 1. Install dependencies

```bash
brew install uv mysql
brew services start mysql
```

### 2. Create the database

```bash
mysql -u root -p -e "CREATE DATABASE doc_rag;"
```

### 3. Set up your environment

Create a `.env` file in the project root:

```env
VECTOR_STORE=faiss
DATABASE_URL=mysql+pymysql://root:yourpassword@localhost:3306/doc_rag
GEMINI_API_KEY=your-gemini-api-key
```

### 4. Start the backend

```bash
uv run uvicorn main:app --reload
```

### 5. Start the frontend

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
    "content": "Our refund policy allows returns within 30 days..."
  }'
```

### Ask a question

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the refund policy?"}'
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
| Tokenizer | tiktoken (`cl100k_base`) |
| Package Manager | uv |
