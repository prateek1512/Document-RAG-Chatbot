# app/api/__init__.py
# Combines all API routers into one.

from fastapi import APIRouter
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router

# Parent router that includes both sub-routers
api_router = APIRouter()
api_router.include_router(documents_router)
api_router.include_router(chat_router)
