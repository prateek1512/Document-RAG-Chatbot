# app/schemas/chat.py
# Pydantic schemas for the unified /chat endpoint.

from pydantic import BaseModel
from app.schemas.query import SourceInfo

# Shape of the POST /chat request body.


class ChatRequest(BaseModel):
    message: str  # the user's message / question

# One chunk that was retrieved from the knowledge base, with its similarity score.


class RetrievedChunkInfo(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    chunk_text: str
    similarity_score: float  # 0.0 to 1.0 — higher means more relevant

# Shape of the POST /chat response body.


class ChatResponse(BaseModel):
    answer: str                                      # the final generated answer
    intent: str                                      # Simple / Knowledge / Multi-Step
    # which chunks the LLM cited
    sources: list[SourceInfo] = []
    # all chunks that were retrieved
    retrieved_chunks: list[RetrievedChunkInfo] = []
    # only populated for Multi-Step
    sub_questions: list[str] = []
