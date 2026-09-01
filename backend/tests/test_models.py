"""Tests for database models."""

import pytest
from datetime import datetime
from app.models import Document, Chunk, DocumentStatus


class TestDocumentModel:
    """Tests for Document model."""

    def test_document_status_enum(self):
        """Test DocumentStatus enum values."""
        assert DocumentStatus.PENDING.value == "pending"
        assert DocumentStatus.PROCESSING.value == "processing"
        assert DocumentStatus.READY.value == "ready"
        assert DocumentStatus.ERROR.value == "error"

    def test_document_has_required_fields(self):
        """Test Document model has required fields."""
        # Check class attributes exist
        assert hasattr(Document, "id")
        assert hasattr(Document, "name")
        assert hasattr(Document, "file_type")
        assert hasattr(Document, "status")

    def test_document_has_optional_fields(self):
        """Test Document model has optional fields."""
        assert hasattr(Document, "s3_key")
        assert hasattr(Document, "workspace_id")
        assert hasattr(Document, "user_id")
        assert hasattr(Document, "error_message")

    def test_document_has_timestamps(self):
        """Test Document model has timestamp fields."""
        assert hasattr(Document, "created_at")
        assert hasattr(Document, "updated_at")

    def test_document_has_relationship(self):
        """Test Document has chunks relationship."""
        assert hasattr(Document, "chunks")


class TestChunkModel:
    """Tests for Chunk model."""

    def test_chunk_has_required_fields(self):
        """Test Chunk model has required fields."""
        assert hasattr(Chunk, "id")
        assert hasattr(Chunk, "document_id")
        assert hasattr(Chunk, "content")
        assert hasattr(Chunk, "chunk_index")

    def test_chunk_has_embedding_field(self):
        """Test Chunk has embedding vector field."""
        assert hasattr(Chunk, "embedding")

    def test_chunk_has_optional_fields(self):
        """Test Chunk has optional metadata fields."""
        assert hasattr(Chunk, "page_number")
        assert hasattr(Chunk, "token_count")

    def test_chunk_has_document_relationship(self):
        """Test Chunk has document relationship."""
        assert hasattr(Chunk, "document")
