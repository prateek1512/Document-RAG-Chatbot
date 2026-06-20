# app/services/sync_service.py
# Three procedural functions that keep the vector database perfectly
# aligned with a local folder of files.

import hashlib
import os

from app.database.connection import Session
from app.models.document import Document, DocumentChunk
from app.utils.file_reader import extract_text_from_file
from app.utils.chunking import chunk_text
from app.services.vector_store_service import (
    get_embeddings,
    add_to_index,
    remove_from_index,
    save_index,
)

# HANDLE A NEW FILE


def handle_new_file(file_path: str) -> int:

    # 1. Extract the raw text from the file
    raw_text = extract_text_from_file(file_path)
    print(f"Read {len(raw_text)} characters from '{file_path}'")

    # 2. Compute a SHA-256 hash of the content
    content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    # Filename (not the full path) as the document title
    filename = os.path.basename(file_path)

    # 3. Split the text into chunks
    text_chunks = chunk_text(raw_text, max_tokens=500, overlap_tokens=50)
    print(f"Split into {len(text_chunks)} chunks")

    # 4. Save to MySQL
    db = Session()
    try:
        # Create the Document row
        new_doc = Document(
            title=filename,
            # source_path is used to find the doc later when file is modified or deleted.
            source_path=file_path,
            content_hash=content_hash,
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)  # new_doc.id is now available

        # Create a DocumentChunk row.
        chunk_objects = []
        for text in text_chunks:
            chunk_obj = DocumentChunk(
                document_id=new_doc.id,
                chunk_text=text,
                # source_path is denormalised onto every chunk so the
                # vector store can filter by filename without a SQL JOIN.
                source_path=file_path,
            )
            db.add(chunk_obj)
            chunk_objects.append(chunk_obj)

        db.commit()

        # Refresh to get the auto-generated chunk_ids
        for chunk_obj in chunk_objects:
            db.refresh(chunk_obj)

        # 5. Generate embeddings via Gemini
        embeddings = get_embeddings(text_chunks)
        print(f"Generated {len(embeddings)} embeddings")

        # 6. Insert vectors into the vector DB
        chunk_ids = [c.chunk_id for c in chunk_objects]
        add_to_index(
            embeddings,
            document_id=new_doc.id,
            chunk_ids=chunk_ids,
            source_path=file_path,
        )

        # 7. Persist the index to disk
        save_index()

        print(f"Ingested '{filename}' as document id={new_doc.id}\n")
        return new_doc.id

    finally:
        db.close()


# HANDLE A DELETED FILE


def handle_deleted_file(file_path: str) -> None:
    db = Session()
    try:
        # 1. Find the document in MySQL by source_path
        doc = db.query(Document).filter(
            Document.source_path == file_path).first()

        if not doc:
            print(f"'{file_path}' not found in database — nothing to delete.")
            return

        document_id = doc.id
        filename = doc.title

        # 2. Delete vectors from the vector DB
        # For FAISS: scans chunk_metadata, rebuilds the index
        #            without vectors matching this source_path.
        # For Pinecone: single API call with metadata filter
        #               {"source_path": {"$eq": file_path}}
        remove_from_index(document_id=document_id, source_path=file_path)
        print(f"Removed vectors for '{filename}' from vector store")

        # 3. Delete from MySQL
        # The Document row is deleted, and all its DocumentChunk rows are automatically removed
        # by the cascade delete defined on the Document model.
        db.delete(doc)
        db.commit()
        print(f"Removed document id={document_id} ('{filename}') from MySQL")

        # 4. Persist the updated vector index
        save_index()

        print(f"'{filename}' fully cleaned up\n")

    finally:
        db.close()


# HANDLE A MODIFIED FILE


def handle_modified_file(file_path: str) -> int | None:

    # Optimisation: skip if the content hasn't actually changed.
    # Read the current file content and compare its hash against what's stored in the database.
    raw_text = extract_text_from_file(file_path)
    new_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    db = Session()
    try:
        existing = db.query(Document).filter(
            Document.source_path == file_path).first()

        if existing and existing.content_hash == new_hash:
            print(f"'{file_path}' content unchanged (hash match) — skipping.\n")
            return None
    finally:
        db.close()

    # 1. Wipe the old version
    print(f"'{os.path.basename(file_path)}' has changed — re-syncing...")
    handle_deleted_file(file_path)

    # 2. Ingest the fresh version
    new_doc_id = handle_new_file(file_path)

    return new_doc_id
