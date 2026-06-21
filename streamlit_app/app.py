# streamlit_app/app.py
# Streamlit frontend for the Doc RAG application.

import streamlit as st
import requests
import os
from dotenv import load_dotenv
import json

API_BASE = "http://localhost:8000"

# PAGE SETUP

st.set_page_config(
    page_title="Doc RAG Chat",
)

# SESSION STATE — keeps chat history across reruns

if "messages" not in st.session_state:
    st.session_state.messages = []

load_dotenv(override=True)
ACTIVE_VECTOR_STORE = os.getenv("VECTOR_STORE", "faiss").strip().lower()
ACTIVE_VECTOR_STORE_LABEL = "Pinecone" if ACTIVE_VECTOR_STORE == "pinecone" else "FAISS"


# SIDEBAR

with st.sidebar:
    st.header("Doc RAG")
    st.caption("Upload documents and chat with your knowledge base.")

    st.divider()

    # Vector store (read from .env)
    st.subheader("Vector Store")
    st.info(f"Active: **{ACTIVE_VECTOR_STORE_LABEL}**")
    st.caption("Change VECTOR_STORE in .env and restart to switch.")

    st.divider()

    # Document upload
    st.subheader("Upload Document")

    uploaded_file = st.file_uploader(
<<<<<<< HEAD
        "Upload a JSON document",
        type=["json"],
    )
    json_submit = st.button("Upload JSON File", use_container_width=True)

    # Optional manual input
    with st.expander("Or paste text manually"):
        manual_title = st.text_input("Document title")
        manual_content = st.text_area("Document content", height=150)
        manual_submit = st.button("Upload text", use_container_width=True)

    # Handle JSON file upload
    if json_submit and uploaded_file is not None:
        try:
            doc_data = json.load(uploaded_file)
            title = doc_data.get("title", uploaded_file.name)
            content = doc_data.get("content", "")

            if not content:
                st.error(
                    "JSON must have a 'content' field with the document text.")
            else:
                with st.spinner("Uploading & chunking..."):
                    resp = requests.post(
                        f"{API_BASE}/documents",
                        json={"title": title, "content": content},
                        timeout=60,
                    )

                if resp.status_code == 200:
                    result = resp.json()
                    n_chunks = len(result.get("chunks", []))
                    st.success(
                        f"Uploaded **{title}** — {n_chunks} chunks created")
                else:
                    st.error(f"Upload failed: {resp.text}")

        except json.JSONDecodeError:
            st.error("Invalid JSON file.")

    # Handle manual text upload
    if manual_submit and manual_title and manual_content:
        with st.spinner("Uploading & chunking..."):
            resp = requests.post(
                f"{API_BASE}/documents",
                json={"title": manual_title, "content": manual_content},
                timeout=60,
            )

        if resp.status_code == 200:
            result = resp.json()
            n_chunks = len(result.get("chunks", []))
            st.success(
                f"Uploaded **{manual_title}** — {n_chunks} chunks created")
        else:
            st.error(f"Upload failed: {resp.text}")
=======
        "Upload a document",
        type=["json", "pdf", "csv", "docx", "txt", "md"],
    )
    file_submit = st.button("Upload File", use_container_width=True)



    # Handle file upload
    if file_submit and uploaded_file is not None:
        import tempfile
        import os
        from app.utils.file_reader import extract_text_from_file

        with st.spinner("Extracting text & uploading..."):
            # Save uploaded file to a temporary file
            # so extract_text_from_file can read it from disk
            ext = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            try:
                # Extract text using our robust file reader
                content = extract_text_from_file(tmp_path)
                title = uploaded_file.name

                if not content.strip():
                    st.error("No text could be extracted from this file.")
                else:
                    resp = requests.post(
                        f"{API_BASE}/documents",
                        json={
                            "title": title,
                            "content": content,
                            "source_path": uploaded_file.name
                        },
                        timeout=60,
                    )

                    if resp.status_code == 200:
                        result = resp.json()
                        n_chunks = len(result.get("chunks", []))
                        st.success(
                            f"Uploaded **{title}** — {n_chunks} chunks created")
                    else:
                        st.error(f"Upload failed: {resp.text}")

            except Exception as e:
                st.error(f"Failed to read file: {str(e)}")
            finally:
                os.remove(tmp_path)


>>>>>>> 81c1c29 (fixed streamlit frontend)

    st.divider()

    # Document list
    st.subheader("Documents")
    try:
        docs_resp = requests.get(f"{API_BASE}/documents", timeout=10)
        if docs_resp.status_code == 200:
            documents = docs_resp.json()
            if documents:
                for doc in documents:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        n = len(doc.get("chunks", []))
                        st.markdown(f"**{doc['title']}**  \n`{n} chunks`")
                    with col2:
                        if st.button("Delete", key=f"del_{doc['id']}", help="Delete document"):
                            requests.delete(
                                f"{API_BASE}/documents/{doc['id']}", timeout=10)
                            st.rerun()
            else:
                st.info("No documents yet. Upload one above.")
        else:
            st.warning("Could not load documents.")
    except requests.ConnectionError:
        st.error("Cannot connect to the API. Is the backend running?")

    st.divider()

    # Clear chat
    if st.button("Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# MAIN CHAT AREA

st.title("Doc RAG Chat")
st.caption(
    f"Vector store: **{ACTIVE_VECTOR_STORE_LABEL}** · Ask questions about your uploaded documents.")

# Display previous messages from session state
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

# Chat input
user_input = st.chat_input("Ask a question about your documents...")

if user_input:
    # Show the user's message
    with st.chat_message("user"):
        st.markdown(user_input)

    # Save it to history
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Call the /chat endpoint
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                chat_resp = requests.post(
                    f"{API_BASE}/chat",
                    json={"message": user_input},
                    timeout=120,
                )

                if chat_resp.status_code == 200:
                    data = chat_resp.json()

                    # Show the intent classification
                    intent = data.get("intent", "Unknown")
                    st.info(f"**Intent Recognized:** {intent}")

                    # Show sub-questions if Multi-Step
                    sub_questions = data.get("sub_questions", [])
                    if sub_questions:
                        with st.expander("Sub-questions generated", expanded=False):
                            for i, sq in enumerate(sub_questions, 1):
                                st.markdown(f"{i}. {sq}")

                    # Show the answer
                    answer = data.get("answer", "No answer received.")
                    st.markdown(answer)

                    # Show retrieved chunks with similarity scores
                    chunks = data.get("retrieved_chunks", [])
                    if chunks:
                        with st.expander(f"Retrieved Chunks ({len(chunks)})", expanded=False):
                            for chunk in chunks:
                                score = chunk.get("similarity_score", 0)
                                score_pct = f"{score * 100:.1f}%"

                                st.markdown(
                                    f"**Document:** {chunk.get('document_title', 'Unknown')} (Match: {score_pct})")
                                st.caption(
                                    f"Chunk #{chunk.get('chunk_id')} · Doc #{chunk.get('document_id')}")

                                chunk_text = chunk.get('chunk_text', '')
                                if len(chunk_text) > 500:
                                    st.write(chunk_text[:500] + "...")
                                else:
                                    st.write(chunk_text)

                                st.divider()

                    # Show sources
                    sources = data.get("sources", [])
                    if sources:
                        with st.expander("Sources cited by the LLM", expanded=False):
                            for s in sources:
                                st.markdown(
                                    f"- **{s.get('document_title', 'Unknown')}** "
                                    f"(chunk #{s.get('chunk_id')})"
                                )

                    # Build a clean version for chat history
                    history_content = f"**Intent:** {intent}\n\n{answer}"
                    st.session_state.messages.append(
                        {"role": "assistant", "content": history_content}
                    )

                else:
                    error_msg = f"API error ({chat_resp.status_code}): {chat_resp.text}"
                    st.error(error_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )

            except requests.ConnectionError:
                err = "Cannot connect to the backend. Make sure it's running: `uvicorn main:app --reload`"
                st.error(err)
                st.session_state.messages.append(
                    {"role": "assistant", "content": err})

            except requests.Timeout:
                err = "Request timed out. The query may be too complex or the backend is overloaded."
                st.error(err)
                st.session_state.messages.append(
                    {"role": "assistant", "content": err})
