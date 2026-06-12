# app/models/__init__.py
# Re-exports the SQLAlchemy ORM models so other modules can do:
# from app.models import Document, DocumentChunk

from app.models.document import Document, DocumentChunk
