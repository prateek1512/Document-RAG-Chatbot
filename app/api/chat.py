# app/api/chat.py
# The /query and /chat API endpoints.

from fastapi import APIRouter
from app.schemas.query import QueryRequest, QueryResponse, SourceInfo
from app.schemas.chat import ChatRequest, ChatResponse, RetrievedChunkInfo
from app.services.agent_service import classify_intent, route_query
from app.services.rag_service import retrieve_chunks, generate_answer
from app.services.gemini_service import gemini_client
import json

# Create a router
router = APIRouter()


# POST /query
# The agentic RAG endpoint.

@router.post("/query", response_model=QueryResponse)
def query_documents(body: QueryRequest):
    result = route_query(body.question)
    return result


# POST /chat
# Return answer + sources + similarity scores as JSON.

def _l2_distance_to_similarity(distance: float) -> float:
    return round(1.0 / (1.0 + distance), 4)


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return text


def _parse_llm_json(raw_text: str) -> dict:
    cleaned = _strip_json_fences(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"answer": cleaned, "sources": []}


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    user_message = body.message

    intent = classify_intent(user_message)

    # These will be populated by whichever branch executes
    answer = ""
    sources = []
    retrieved_chunks = []
    sub_questions = []

    if intent == "Simple":
        prompt = (
            "You are a helpful assistant. Answer the following question "
            "using your general knowledge.\n\n"
            "Respond with a JSON object:\n"
            '{"answer": "your answer here", "sources": []}\n\n'
            "Do not include any text outside the JSON object.\n\n"
            f"Question: {user_message}"
        )

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        parsed = _parse_llm_json(response.text)
        answer = parsed.get("answer", response.text)

    elif intent == "Knowledge":

        chunks = retrieve_chunks(user_message, top_k=3)

        if not chunks:
            answer = "No relevant documents found. Please upload documents first."
        else:
            for c in chunks:
                retrieved_chunks.append(RetrievedChunkInfo(
                    chunk_id=c["chunk_id"],
                    document_id=c["document_id"],
                    document_title=c["document_title"],
                    chunk_text=c["chunk_text"],
                    similarity_score=_l2_distance_to_similarity(c["distance"]),
                ))

            llm_result = generate_answer(user_message, chunks)
            answer = llm_result.get("answer", "")
            sources = llm_result.get("sources", [])

    else:  # intent == "Multi-Step"

        decompose_prompt = (
            "You are a question decomposer. Break the following complex "
            "question into 2 to 4 simpler, self-contained sub-questions "
            "that can each be answered independently by searching a "
            "document knowledge base.\n\n"
            "Respond with a JSON array of strings. Nothing else.\n"
            'Example: ["What is X?", "What is Y?", "How do X and Y compare?"]\n\n'
            f"Complex question: {user_message}"
        )

        decompose_response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=decompose_prompt,
        )

        cleaned = _strip_json_fences(decompose_response.text)
        try:
            sub_questions = json.loads(cleaned)
        except json.JSONDecodeError:
            # If decomposition failed, treat the whole query as one question
            sub_questions = [user_message]

        # We collect ALL retrieved chunks across all sub-questions into one flat list.
        seen_chunk_ids = set()
        all_chunks_raw = []  # raw dicts from retrieve_chunks()

        for sub_q in sub_questions:
            sub_chunks = retrieve_chunks(sub_q, top_k=3)

            for c in sub_chunks:
                # Skip duplicates
                if c["chunk_id"] not in seen_chunk_ids:
                    seen_chunk_ids.add(c["chunk_id"])
                    all_chunks_raw.append(c)

                    retrieved_chunks.append(RetrievedChunkInfo(
                        chunk_id=c["chunk_id"],
                        document_id=c["document_id"],
                        document_title=c["document_title"],
                        chunk_text=c["chunk_text"],
                        similarity_score=_l2_distance_to_similarity(
                            c["distance"]),
                    ))

        if not all_chunks_raw:
            answer = "No relevant documents found. Please upload documents first."
        else:
            llm_result = generate_answer(user_message, all_chunks_raw)
            answer = llm_result.get("answer", "")
            sources = llm_result.get("sources", [])

    # BUILD AND RETURN THE RESPONSE

    # Normalise sources to SourceInfo objects
    normalised_sources = []
    for s in sources:
        if isinstance(s, dict):
            normalised_sources.append(SourceInfo(
                document_title=s.get("document_title", "Unknown"),
                chunk_id=s.get("chunk_id", 0),
            ))
        else:
            normalised_sources.append(s)

    return ChatResponse(
        answer=answer,
        intent=intent,
        sources=normalised_sources,
        retrieved_chunks=retrieved_chunks,
        sub_questions=sub_questions,
    )
