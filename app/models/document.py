# app/models/document.py
# Defines the database tables (SQLAlchemy models).

from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.connection import Base


# SQLAlchemy Models (these become MySQL tables)

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # file-tracking columns for live sync
    # The original filename or path of the uploaded file.
    source_path: Mapped[str | None] = mapped_column(
<<<<<<< HEAD
        String(1024), nullable=True, index=True)
=======
        String(512), nullable=True, index=True)
>>>>>>> 81c1c29 (fixed streamlit frontend)

    # SHA-256 hash of the raw file content at ingestion time.
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now())

    # track when the document was last re-indexed
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True)

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    chunk_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str | None] = mapped_column(
<<<<<<< HEAD
        String(1024), nullable=True, index=True)
=======
        String(512), nullable=True, index=True)
>>>>>>> 81c1c29 (fixed streamlit frontend)

    document: Mapped["Document"] = relationship(back_populates="chunks")
