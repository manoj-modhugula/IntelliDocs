"""
Document and Chunk models for the database.
"""

from datetime import datetime

from app.core.utils import utc_now_naive
from enum import Enum
from typing import Optional, List
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class Document(Base):
    """Document model - represents an uploaded document."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=DocumentStatus.PENDING.value)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)

    # Versioning: version number and link to previous version
    version: Mapped[int] = mapped_column(Integer, default=1)
    previous_document_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("documents.id"), nullable=True
    )

    workspace_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("workspaces.id"), nullable=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )

    chunks: Mapped[List["Chunk"]] = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_document_workspace", "workspace_id"),
        Index("idx_document_status", "status"),
        Index("idx_document_user", "user_id"),
        Index("idx_document_user_workspace", "user_id", "workspace_id"),
        Index("idx_document_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
    )


class Chunk(Base):
    """Chunk model - represents a text chunk with embedding."""
    
    __tablename__ = "chunks"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False)
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # text | table | figure
    chunk_type: Mapped[str] = mapped_column(String(16), default="text")
    bbox_x0: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_y0: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_x1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_y1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    image_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Vector embedding (1024 dimensions for Titan)
    embedding: Mapped[List[float]] = mapped_column(Vector(1024), nullable=True)
    # CLIP visual embedding (512-d, figures and table screenshots)
    clip_embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(512), nullable=True)

    # Content hash for dedupe/reuse
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Metadata
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    workspace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    
    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    
    # Indexes
    __table_args__ = (
        Index("idx_chunk_document", "document_id"),
        Index("idx_chunk_workspace", "workspace_id"),
        Index("idx_chunk_embedding", "embedding", postgresql_using="ivfflat", postgresql_with={"lists": 100}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("idx_chunk_clip_embedding", "clip_embedding", postgresql_using="ivfflat", postgresql_with={"lists": 100}, postgresql_ops={"clip_embedding": "vector_cosine_ops"}),
        Index("idx_chunk_content_trgm", "content", postgresql_using="gin", postgresql_ops={"content": "gin_trgm_ops"}),
        Index("idx_chunk_content_hash", "content_hash"),
        Index("idx_chunk_type", "chunk_type"),
    )


class Workspace(Base):
    """Workspace model - represents a document workspace."""
    
    __tablename__ = "workspaces"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )
    
    # Relationships
    documents: Mapped[List["Document"]] = relationship("Document", backref="workspace")

    # Index for fast list by owner
    __table_args__ = (Index("idx_workspace_user", "user_id"),)
