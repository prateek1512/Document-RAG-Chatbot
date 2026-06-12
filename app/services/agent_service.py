# app/services/agent_service.py
# A lightweight agentic router that classifies user queries by intent
# and routes them to the right handler.

import json
import time
from app.services.gemini_service import gemini_client
from app.services.rag_service import rag_query


# MAIN ENTRY POINT: ROUTE THE QUERY

def route_query(query: str) -> dict:
    intent = classify_intent(query)

    if intent == "Simple":
        # No retrieval needed — answer from general knowledge
        result = handle_simple(query)

    elif intent == "Knowledge":
        # Standard RAG — single search + LLM answer
        result = handle_knowledge(query)

    else:
        # Complex query — decompose, retrieve, synthesise
        result = handle_multi_step(query)

    # Attach the detected intent so the caller knows which path was taken
    result["intent"] = intent

    return result


# CLASSIFY THE INTENT

def classify_intent(query: str) -> str:
    classification_prompt = (
        "You are a query classifier. Given the user's question below, "
        "classify it into exactly ONE of these categories:\n\n"

        "1. Simple — The question can be answered from general knowledge "
        "without needing to search any documents. Examples: greetings, "
        "definitions of common terms, basic factual questions.\n\n"

        "2. Knowledge — The question requires searching a document "
        "knowledge base to find the answer. It is a single, focused "
        "question. Examples: 'What is our refund policy?', "
        "'Summarize chapter 3.'\n\n"

        "3. Multi-Step — The question is complex and requires breaking "
        "it into multiple sub-questions or comparing information from "
        "different parts of the knowledge base. Examples: 'Compare X "
        "and Y from the documents', 'List all mentions of Z across "
        "all documents and summarize the trends.'\n\n"

        "Respond with EXACTLY one word: Simple, Knowledge, or Multi-Step.\n"
        "Do not include any other text.\n\n"

        f"User question: {query}"
    )

    # Call Gemini to classify
    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=classification_prompt,
    )

    # Strip whitespace, handle case variations
    intent = response.text.strip()
    intent_lower = intent.lower().replace("-", "").replace("_", "")

    if "simple" in intent_lower:
        return "Simple"
    elif "knowledge" in intent_lower:
        return "Knowledge"
    elif "multi" in intent_lower or "step" in intent_lower:
        return "Multi-Step"
    else:
        return "Knowledge"


# HANDLER: SIMPLE

def handle_simple(query: str) -> dict:
    prompt = (
        "You are a helpful assistant. Answer the following question "
        "using your general knowledge.\n\n"
        "Respond with a JSON object in this format:\n"
        '{"answer": "your answer here", "sources": []}\n\n'
        "Do not include any text outside the JSON object.\n\n"
        f"Question: {query}"
    )

    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    raw_text = response.text.strip()

    # Strip markdown fences if the LLM wrapped the JSON
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1])

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        result = {"answer": raw_text, "sources": []}

    # No retrieval was done, so context is empty
    result["context"] = []
    return result


# HANDLER: KNOWLEDGE

def handle_knowledge(query: str) -> dict:
    return rag_query(query)

# HANDLER: MULTI-STEP (decompose → retrieve → combine)


def handle_multi_step(query: str) -> dict:
    """
    For complex queries, we:
      1. Ask Gemini to break the query into 2-4 simpler sub-questions
      2. Run the standard RAG pipeline on each sub-question
      3. Collect all the partial answers
      4. Ask Gemini to synthesise them into one final answer

    This is a simple "fan-out / fan-in" pattern — no recursion,
    no state machine, just a loop and a final merge.
    """

    # A) Decompose the complex query into sub-questions
    decompose_prompt = (
        "You are a question decomposer. Break the following complex "
        "question into 2 to 4 simpler, self-contained sub-questions "
        "that can each be answered independently by searching a "
        "document knowledge base.\n\n"
        "Respond with a JSON array of strings. Nothing else.\n"
        'Example: ["What is X?", "What is Y?", "How do X and Y compare?"]\n\n'
        f"Complex question: {query}"
    )

    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=decompose_prompt,
    )

    raw_text = response.text.strip()

    # Strip markdown fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1])

    try:
        sub_questions = json.loads(raw_text)
    except json.JSONDecodeError:
        # If parsing fails, fall back to treating the whole query as one question
        sub_questions = [query]

    # B) Run RAG on each sub-question
    sub_answers = []
    all_context = []

    for i, sub_q in enumerate(sub_questions, start=1):
        # Prevent bursting API rate limits for free tier keys
        time.sleep(2)

        # Reuse the same rag_query() we built earlier
        sub_result = rag_query(sub_q)

        sub_answers.append({
            "sub_question": sub_q,
            "sub_answer": sub_result.get("answer", ""),
            "sources": sub_result.get("sources", []),
        })

        # Collect context from all sub-queries for transparency
        all_context.extend(sub_result.get("context", []))

    # C) Synthesise sub-answers into a final answer
    # We send all sub-answers to Gemini and ask it to merge them.
    synthesis_parts = []
    for sa in sub_answers:
        synthesis_parts.append(
            f"Sub-question: {sa['sub_question']}\n"
            f"Sub-answer: {sa['sub_answer']}\n"
        )

    synthesis_prompt = (
        "You are a helpful assistant. The user asked a complex question "
        "that was broken into sub-questions. Below are the sub-answers.\n\n"
        "Synthesise them into one clear, comprehensive final answer.\n\n"
        "Respond with a JSON object:\n"
        '{"answer": "your synthesised answer", "sources": [...]}\n'
        "Include all unique sources from the sub-answers.\n"
        "Do not include any text outside the JSON object.\n\n"
        f"Original question: {query}\n\n"
        + "\n".join(synthesis_parts)
    )

    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=synthesis_prompt,
    )

    raw_text = response.text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1])

    try:
        final_result = json.loads(raw_text)
    except json.JSONDecodeError:
        final_result = {"answer": raw_text, "sources": []}

    # Deduplicate context (same chunk_id might appear from multiple sub-queries)
    seen_chunks = set()
    unique_context = []
    for ctx in all_context:
        if ctx["chunk_id"] not in seen_chunks:
            seen_chunks.add(ctx["chunk_id"])
            unique_context.append(ctx)

    final_result["context"] = unique_context
    return final_result
