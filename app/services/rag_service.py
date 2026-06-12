# app/services/rag_service.py
# The core RAG (Retrieval-Augmented Generation) pipeline.

import json
from app.services.vector_store_service import search_index
from app.services.gemini_service import gemini_client
from app.models.document import DocumentChunk, Document
from app.database.connection import Session


# MAIN ENTRY POINT: THE FULL RAG PIPELINE
# End-to-end RAG pipeline. This is what the /query route calls.
def rag_query(query: str) -> dict:
    # A) Retrieve relevant chunks
    retrieved_chunks = retrieve_chunks(query, top_k=3)

    # B) Handle the case where no documents have been ingested yet
    if not retrieved_chunks:
        return {
            "answer": "No relevant documents found. Please upload documents first.",
            "sources": [],
            "context": [],
        }

    # C) Generate the answer using the LLM
    llm_response = generate_answer(query, retrieved_chunks)

    # D) Attach the retrieved context for transparency
    # (so the caller can see exactly which chunks were used)
    llm_response["context"] = [
        {
            "chunk_id": c["chunk_id"],
            "document_id": c["document_id"],
            "document_title": c["document_title"],
            "distance": c["distance"],
            "chunk_text": c["chunk_text"][:200] + "..."
        }
        for c in retrieved_chunks
    ]

    return llm_response


# RETRIEVE RELEVANT CHUNKS

def retrieve_chunks(query: str, top_k: int = 3) -> list[dict]:

    # A) Ask FAISS for the closest chunk vectors to the query.
    faiss_results = search_index(query, top_k=top_k)

    # If FAISS is empty or nothing matched, return early
    if not faiss_results:
        return []

    # B) Now fetch the actual chunk text from the database.
    #    FAISS only stores vectors, we need MySQL for the readable text.
    db = Session()

    try:
        retrieved = []

        for result in faiss_results:
            chunk_id = result["chunk_id"]
            document_id = result["document_id"]

            # Query the document_chunks table for this specific chunk
            chunk_row = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.chunk_id == chunk_id)
                .first()
            )

            # Query the documents table for the title (used as the source name)
            doc_row = (
                db.query(Document)
                .filter(Document.id == document_id)
                .first()
            )

            if chunk_row and doc_row:
                retrieved.append({
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "chunk_text": chunk_row.chunk_text,
                    "document_title": doc_row.title,
                    "distance": result["distance"],
                })

        return retrieved

    finally:
        db.close()


# BUILD THE PROMPT

def build_prompt(query: str, retrieved_chunks: list[dict]) -> str:
    # A) System instruction
    system_instruction = (
        "You are a helpful assistant that answers questions based ONLY on "
        "the provided context. If the context does not contain enough "
        "information to answer, say so honestly.\n\n"
        "You MUST respond with a valid JSON object in this exact format:\n"
        "{\n"
        '  "answer": "Your detailed answer here",\n'
        '  "sources": [\n'
        '    {"document_title": "...", "chunk_id": ...},\n'
        "    ...\n"
        "  ]\n"
        "}\n\n"
        "Include in 'sources' only the chunks you actually used to form "
        "the answer. Do not include any text outside the JSON object."
    )

    # B) Context — the retrieved chunks
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks, start=1):
        context_parts.append(
            f"--- Context Chunk {i} ---\n"
            f"Document: {chunk['document_title']}\n"
            f"Chunk ID: {chunk['chunk_id']}\n"
            f"Text:\n{chunk['chunk_text']}\n"
        )

    context_block = "\n".join(context_parts)

    # C) Combine everything into one prompt string
    full_prompt = (
        f"{system_instruction}\n"
        f"=== CONTEXT ===\n{context_block}\n"
        f"=== QUESTION ===\n{query}\n"
    )

    return full_prompt


# CALL THE GEMINI LLM

def generate_answer(query: str, retrieved_chunks: list[dict]) -> dict:
    """
    Send the prompt to Gemini and parse the JSON response.

    We use gemini-2.5-flash because it's fast, cheap, and good enough
    for RAG answers. The model is instructed to return JSON, so we
    parse the response text directly.

    Returns a dict like:
      {
        "answer": "The capital of France is Paris.",
        "sources": [{"document_title": "Geography", "chunk_id": 3}]
      }
    """

    # Build the full prompt from query + retrieved context
    prompt = build_prompt(query, retrieved_chunks)

    # Call the Gemini LLM.
    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    # The LLM's text response — should be a JSON string
    raw_text = response.text.strip()

    # Sometimes the LLM wraps JSON in ```json ... ``` markdown fences.
    # Strip those if present so json.loads() works.
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1])

    # Parse the JSON string into a Python dict
    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        # If the LLM didn't return valid JSON, wrap the raw text as the answer
        result = {
            "answer": raw_text,
            "sources": [],
        }

    return result
