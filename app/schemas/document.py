# app/schemas/document.py
# Pydantic schemas for document-related requests and responses.

from datetime import datetime
from pydantic import BaseModel

# Shape of the POST /documents request body.


class DocumentCreate(BaseModel):
    title: str
    content: str

# Shape of a chunk when the client sends it in the POST body.


class ChunkCreate(BaseModel):
    chunk_text: str

# Shape of a document in the API response.


class DocumentResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    chunks: list[ChunkResponse] = []

    model_config = {"from_attributes": True}

# Shape of a chunk in the API response.


class ChunkResponse(BaseModel):
    chunk_id: int
    document_id: int
    chunk_text: str

    # lets Pydantic read SQLAlchemy objects
    model_config = {"from_attributes": True}
