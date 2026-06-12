# app/api/documents.py
# API endpoints for managing documents.

from fastapi import APIRouter, HTTPException
from app.models.document import Document, DocumentChunk
from sqlalchemy.orm import joinedload
from app.schemas.document import DocumentCreate, DocumentResponse
from app.database.connection import Session
from app.utils.chunking import chunk_text
from app.services.vector_store_service import get_embeddings, add_to_index, remove_from_index, save_index

# Create a router
router = APIRouter()

# POST /documents
# Accepts raw text, chunks it, embeds the chunks, and stores everything.


@router.post("/documents", response_model=DocumentResponse)
def create_document(body: DocumentCreate):
    # 1. Open a database session
    db = Session()
    try:
        # 2. Split the raw text into ~500-token chunks with 50-token overlap
        text_chunks = chunk_text(
            body.content, max_tokens=500, overlap_tokens=50)

        # 3. Create the Document row in MySQL
        new_doc = Document(title=body.title)
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)  # now new_doc.id is available

        # 4. Create a DocumentChunk row for each text chunk
        chunk_objects = []
        for text in text_chunks:
            chunk_obj = DocumentChunk(document_id=new_doc.id, chunk_text=text)
            db.add(chunk_obj)
            chunk_objects.append(chunk_obj)

        db.commit()

        # 5. Refresh each chunk so that chunk_id is populated
        for chunk_obj in chunk_objects:
            db.refresh(chunk_obj)

        # 6. Generate embeddings for all chunks in one API call to Gemini
        embeddings = get_embeddings(text_chunks)

        # 7. Insert the embedding vectors into the FAISS index
        chunk_ids = [c.chunk_id for c in chunk_objects]
        add_to_index(embeddings, document_id=new_doc.id, chunk_ids=chunk_ids)

        # 8. Persist the updated FAISS index to disk
        save_index()

        # 9. Reload the document with its chunks for the response
        db.refresh(new_doc)
        _ = new_doc.chunks  # Load chunks before session closes
        return new_doc

    finally:
        db.close()


# GET /documents
# Returns every document with its chunks.

@router.get("/documents", response_model=list[DocumentResponse])
def list_documents():

    db = Session()

    try:
        # Query all documents from the table
        documents = db.query(Document).options(
            joinedload(Document.chunks)).all()
        return documents

    finally:
        db.close()


# DELETE /documents/{document_id}
# Deletes a document, its chunks from MySQL, and its vectors from FAISS.

@router.delete("/documents/{document_id}")
def delete_document(document_id: int):

    db = Session()

    try:
        # 1. Look up the document by ID
        doc = db.query(Document).filter(Document.id == document_id).first()

        # 2. If it doesn't exist, return a 404 error
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # 3. Delete it from MySQL (chunks removed automatically by cascade)
        db.delete(doc)
        db.commit()

        # 4. Remove its vectors from the FAISS index
        remove_from_index(document_id)
        save_index()

        return {"message": f"Document {document_id} deleted"}

    finally:
        db.close()
