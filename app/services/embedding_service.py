# app/services/embedding_service.py
# Generates embeddings via the Gemini API and stores them in a local FAISS index.

import os
import numpy as np
import faiss
from google.genai import types
from dotenv import load_dotenv
from app.services.gemini_service import gemini_client

load_dotenv()

# EMBEDDING CONFIG

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768

# SET UP THE FAISS INDEX

faiss_index = faiss.IndexFlatL2(EMBEDDING_DIM)

# We also keep a plain Python list that maps each FAISS row number
# back to the (document_id, chunk_id) pair so we know which database
# chunk a search result belongs to.
# Example: chunk_metadata[0] = {"document_id": 1, "chunk_id": 3}
chunk_metadata: list[dict] = []

# Path where we'll save / load the index to disk
FAISS_INDEX_PATH = "faiss_index.bin"
FAISS_META_PATH = "faiss_metadata.npy"


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

    # response.embeddings is a list of EmbeddingObject
    return [emb.values for emb in response.embeddings]


def get_query_embedding(query: str) -> list[float]:
    response = gemini_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(
            # task_type="RETRIEVAL_QUERY" so the model optimises the vector for *searching*, not storing.
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBEDDING_DIM,
        ),
    )
    return response.embeddings[0].values


# ADD VECTORS TO THE FAISS INDEX

def add_to_index(embeddings: list[list[float]], document_id: int, chunk_ids: list[int]):

    # Convert to a numpy array of shape (n_chunks, 768), dtype float32
    vectors = np.array(embeddings, dtype=np.float32)

    # Add the vectors to the FAISS index
    faiss_index.add(vectors)

    # Record the metadata for each vector we just added
    for cid in chunk_ids:
        chunk_metadata.append({"document_id": document_id, "chunk_id": cid})


# SEARCH THE INDEX

def search_index(query: str, top_k: int = 5) -> list[dict]:

    # Embed the user's query
    query_vec = np.array([get_query_embedding(query)], dtype=np.float32)

    # FAISS search returns two arrays: L2 distance and row index
    distances, indices = faiss_index.search(query_vec, top_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        # idx == -1 means FAISS had fewer than top_k vectors to return
        if idx == -1:
            continue
        meta = chunk_metadata[idx]
        results.append({
            "document_id": meta["document_id"],
            "chunk_id": meta["chunk_id"],
            "distance": float(dist),
        })

    return results


# REMOVE VECTORS FOR A DELETED DOCUMENT

def remove_from_index(document_id: int):
    global faiss_index, chunk_metadata

    if not chunk_metadata:
        return

    # Reconstruct all current vectors from the index
    all_vectors = faiss_index.reconstruct_n(0, faiss_index.ntotal)

    # Find which rows to keep (everything except the deleted document)
    keep_mask = [m["document_id"] != document_id for m in chunk_metadata]

    new_vectors = all_vectors[keep_mask]
    new_metadata = []
    for m, keep in zip(chunk_metadata, keep_mask):
        if keep:
            new_metadata.append(m)

    # Create a fresh index and re-add the remaining vectors
    faiss_index = faiss.IndexFlatL2(EMBEDDING_DIM)
    if len(new_vectors) > 0:
        faiss_index.add(new_vectors)

    chunk_metadata = new_metadata


# PERSIST / LOAD INDEX TO DISK

def save_index():
    faiss.write_index(faiss_index, FAISS_INDEX_PATH)
    np.save(FAISS_META_PATH, chunk_metadata)


def load_index():
    global faiss_index, chunk_metadata

    if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(FAISS_META_PATH):
        faiss_index = faiss.read_index(FAISS_INDEX_PATH)
        chunk_metadata = np.load(FAISS_META_PATH, allow_pickle=True).tolist()
