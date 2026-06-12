# main.py
# Entry point — creates the FastAPI app, builds tables, loads FAISS, and includes routes.

from fastapi import FastAPI
from app.database.connection import engine, Base
from app.api import api_router
from app.services.vector_store_service import load_index

# Create all tables in MySQL
Base.metadata.create_all(bind=engine)

# Load any previously saved FAISS index from disk
load_index()

# Create the FastAPI application
app = FastAPI(title="Doc RAG API")

# Register routes (documents + chat endpoints)
app.include_router(api_router)
