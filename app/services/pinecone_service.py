# app/services/pinecone_service.py
# Uses Pinecone (a managed cloud vector database) instead of a local FAISS index.

import os
from pinecone import Pinecone, ServerlessSpec
from google.genai import types
from dotenv import load_dotenv
from app.services.gemini_service import gemini_client

load_dotenv()


# EMBEDDING CONFIG

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768


# SET UP THE PINECONE CLIENT + INDEX

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "doc-rag")

# Initialise the Pinecone client
pc = Pinecone(api_key=PINECONE_API_KEY)

# Create the index if it doesn't already exist.
existing_indexes = [idx.name for idx in pc.list_indexes()]

if PINECONE_INDEX_NAME not in existing_indexes:
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=EMBEDDING_DIM,
        metric="cosine",
        spec=ServerlessSpec(  # ServerlessSpec means Pinecone manages the infrastructure for us.
            cloud=os.getenv("PINECONE_CLOUD", "aws"),
            region=os.getenv("PINECONE_REGION", "us-east-1"),
        ),
    )

# Get a handle to the index — all update/insert/query calls go through this
index = pc.Index(PINECONE_INDEX_NAME)


# GENERATE EMBEDDINGS

def get_embeddings(texts: list[str]) -> list[list[float]]:

    response = gemini_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBEDDING_DIM,
        ),
    )
    return [emb.values for emb in response.embeddings]


def get_query_embedding(query: str) -> list[float]:

    response = gemini_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBEDDING_DIM,
        ),
    )
    return response.embeddings[0].values


# ADD VECTORS TO THE PINECONE INDEX

def add_to_index(
    embeddings: list[list[float]],
    document_id: int,
    chunk_ids: list[int],
    source_path: str | None = None,
):

    # Build the list of vectors in Pinecone's format:
    # Each item is a dict with id, values (the vector), and metadata.
    vectors_to_upsert = []

    for embedding, chunk_id in zip(embeddings, chunk_ids):
        vector_id = f"doc_{document_id}_chunk_{chunk_id}"

        # source_path is stored as Pinecone metadata.
        # This lets us do filter={"source_path": {"$eq": "report.pdf"}} to find or delete all vectors from a specific file.
        vectors_to_upsert.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "document_id": document_id,
                "chunk_id": chunk_id,
                "source_path": source_path or "",
            },
        })

    # Upsert in batches of 100
    batch_size = 100
    for i in range(0, len(vectors_to_upsert), batch_size):
        batch = vectors_to_upsert[i: i + batch_size]
        index.upsert(vectors=batch)


# SEARCH THE INDEX

def search_index(query: str, top_k: int = 5) -> list[dict]:

    # Embed the user's query
    query_vec = get_query_embedding(query)

    # Search Pinecone
    results = index.query(
        vector=query_vec,
        top_k=top_k,
        include_metadata=True,
    )

    # Convert Pinecone matches to the same dict format as the FAISS version
    output = []
    for match in results.matches:
        output.append({
            "document_id": int(match.metadata["document_id"]),
            "chunk_id": int(match.metadata["chunk_id"]),
            "source_path": match.metadata.get("source_path"),  # NEW
            # convert score → distance
            "distance": round(1.0 - match.score, 6),
        })

    return output


# REMOVE VECTORS FOR A DELETED DOCUMENT

def remove_from_index(document_id: int = None, source_path: str = None):

    # Build the filter dict based on which arguments were provided
    conditions = {}
    if document_id is not None:
        conditions["document_id"] = {"$eq": document_id}
    if source_path is not None:
        conditions["source_path"] = {"$eq": source_path}

    if not conditions:
        return  # nothing to delete

    # If multiple conditions, combine with $and
    if len(conditions) > 1:
        pinecone_filter = {"$and": [{k: v} for k, v in conditions.items()]}
    else:
        pinecone_filter = conditions

    index.delete(filter=pinecone_filter)


# PERSIST / LOAD INDEX

def save_index():
    """No-op — Pinecone persists data automatically."""
    pass


def load_index():
    """No-op — Pinecone index is always live in the cloud."""
    pass
