# app/models/document.py
# Defines the database tables (SQLAlchemy models).

from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.connection import Base


# SQLAlchemy Models (these become MySQL tables)

# Represents one uploaded document.
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now())
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

# One text chunk belonging to a document.


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    chunk_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    document: Mapped["Document"] = relationship(back_populates="chunks")
