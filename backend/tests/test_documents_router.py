"""Tests for documents router."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import UploadFile
from io import BytesIO


class TestDocumentModels:
    """Tests for document request/response models."""

    def test_document_response_model(self):
        """Test DocumentResponse model exists."""
        from app.routers.documents import DocumentResponse
        assert DocumentResponse is not None

    def test_document_response_has_fields(self):
        """Test DocumentResponse has required fields."""
        from app.routers.documents import DocumentResponse
        fields = DocumentResponse.model_fields.keys()
        assert "id" in fields
        assert "name" in fields

    def test_document_response_instantiation(self):
        """Test DocumentResponse can be instantiated."""
        from app.routers.documents import DocumentResponse
        doc = DocumentResponse(
            id="doc-1",
            name="test.pdf",
            type="application/pdf",
            size=1024,
            status="ready",
        )
        assert doc.id == "doc-1"


class TestDocumentEndpoints:
    """Tests for document endpoints."""

    def test_upload_endpoint_exists(self):
        """Test upload endpoint is registered."""
        from app.routers.documents import router
        paths = [r.path for r in router.routes]
        assert "/upload" in paths

    def test_list_endpoint_exists(self):
        """Test list endpoint is registered."""
        from app.routers.documents import router
        paths = [r.path for r in router.routes]
        assert "/" in paths

    def test_delete_endpoint_exists(self):
        """Test delete endpoint is registered."""
        from app.routers.documents import router
        methods = set()
        for r in router.routes:
            if hasattr(r, 'methods'):
                methods.update(r.methods)
        assert "DELETE" in methods


class TestDocumentStatus:
    """Tests for document status handling."""

    def test_document_status_values(self):
        """Test document status enum values."""
        from app.models import DocumentStatus
        assert DocumentStatus.PENDING.value == "pending"
        assert DocumentStatus.PROCESSING.value == "processing"
        assert DocumentStatus.READY.value == "ready"
        assert DocumentStatus.ERROR.value == "error"

    def test_status_response_model(self):
        """Test DocumentStatusResponse model."""
        from app.routers.documents import DocumentStatusResponse
        status = DocumentStatusResponse(
            status="ready",
            chunkCount=5,
        )
        assert status.status == "ready"
        assert status.chunkCount == 5
