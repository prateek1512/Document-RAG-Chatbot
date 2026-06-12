# app/schemas/query.py
# Pydantic schemas for the RAG /query endpoint.

from pydantic import BaseModel

# Shape of the POST /query request body.


class QueryRequest(BaseModel):
    question: str

# One source reference in the LLM's response.


class SourceInfo(BaseModel):
    document_title: str
    chunk_id: int

# One retrieved chunk returned for transparency / debugging.


class ContextInfo(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    distance: float
    chunk_text: str

# Shape of the POST /query response body.


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceInfo] = []
    context: list[ContextInfo] = []
    intent: str = ""  # Simple, Knowledge, or Multi-Step
