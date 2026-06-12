# app/services/vector_store_service.py
# Automatic vector store switcher.

import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Read which backend to use — default to "faiss" if not set
VECTOR_STORE = os.getenv("VECTOR_STORE", "faiss").strip().lower()

if VECTOR_STORE == "pinecone":
    # Import everything from the Pinecone module
    from app.services.pinecone_service import (
        get_embeddings,
        get_query_embedding,
        add_to_index,
        search_index,
        remove_from_index,
        save_index,
        load_index,
    )
    print(f" Vector store: Pinecone")
else:
    # Import everything from the FAISS module (default)
    from app.services.embedding_service import (
        get_embeddings,
        get_query_embedding,
        add_to_index,
        search_index,
        remove_from_index,
        save_index,
        load_index,
    )
    print(f" Vector store: FAISS (local)")
