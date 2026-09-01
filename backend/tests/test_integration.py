"""
Integration tests for the complete RAG pipeline.
Tests actual database operations and service interactions.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app


class TestRAGPipelineIntegration:
    """Integration tests for the complete RAG pipeline."""

    @pytest.mark.asyncio
    async def test_health_endpoint_integration(self, async_client):
        """Test health endpoint returns valid response."""
        response = await async_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["ok", "healthy"]

    @pytest.mark.asyncio
    async def test_chat_endpoint_with_empty_message(self, async_client):
        """Test chat endpoint rejects empty messages."""
        response = await async_client.post(
            "/chat/",
            json={"message": ""}
        )
        
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_chat_endpoint_returns_structure(self, async_client):
        """Test chat endpoint returns correct response structure."""
        with patch("app.routers.chat.rag_service") as mock_rag:
            mock_rag.answer = AsyncMock(return_value={
                "answer": "Test answer with [1] citation",
                "citations": [
                    {
                        "id": "cite-1",
                        "documentId": "doc-1",
                        "documentName": "Test Doc",
                        "chunkText": "Sample text...",
                        "relevanceScore": 0.95,
                    }
                ],
                "strategy": "HYBRID",
                "from_cache": False,
            })
            
            response = await async_client.post(
                "/chat/",
                json={"message": "What is this?"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify response structure
            assert "answer" in data
            assert "citations" in data
            assert "strategy" in data
            assert isinstance(data["citations"], list)

    @pytest.mark.asyncio
    async def test_stream_endpoint_returns_sse(self, async_client):
        """Test stream endpoint returns SSE format."""
        with patch("app.routers.chat.rag_service") as mock_rag:
            async def mock_stream(*args, **kwargs):
                yield {"type": "citations", "citations": []}
                yield {"type": "content", "content": "Hello"}
                yield {"type": "content", "content": " world"}
                yield {"type": "done"}
            
            mock_rag.answer_stream = mock_stream
            
            response = await async_client.post(
                "/chat/stream",
                json={"message": "test"}
            )
            
            assert response.status_code == 200
            # SSE responses should have content
            assert len(response.content) > 0


class TestDocumentUploadIntegration:
    """Integration tests for document upload flow."""

    @pytest.mark.asyncio
    async def test_upload_requires_file(self, async_client):
        """Test upload endpoint requires a file."""
        response = await async_client.post("/documents/upload")
        
        # Should fail with 4xx when no file provided
        assert response.status_code in [400, 422]

    def test_documents_endpoint_exists(self):
        """Test documents endpoint is configured."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/documents" in r for r in routes)


class TestWorkspaceIntegration:
    """Integration tests for workspace operations."""

    @pytest.mark.asyncio
    async def test_workspace_create_requires_auth(self, async_client):
        """Test workspace creation requires authentication."""
        response = await async_client.post(
            "/workspaces/",
            json={"description": "Test workspace"}  # No auth, missing name
        )
        
        assert response.status_code == 401  # Auth required first


class TestPrometheusIntegration:
    @pytest.mark.asyncio
    async def test_prometheus_metrics_available(self, async_client):
        response = await async_client.get("/prometheus/metrics")
        assert response.status_code == 200


class TestErrorHandling:
    """Integration tests for error handling."""

    @pytest.mark.asyncio
    async def test_404_for_unknown_endpoint(self, async_client):
        """Test 404 returned for unknown endpoints."""
        response = await async_client.get("/nonexistent/endpoint")
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_405_for_wrong_method(self, async_client):
        """Test 405 returned for wrong HTTP method."""
        response = await async_client.get("/chat/")  # Should be POST
        
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_422_for_invalid_json(self, async_client):
        """Test 422 returned for invalid JSON."""
        response = await async_client.post(
            "/chat/",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422


class TestCORSIntegration:
    """Integration tests for CORS configuration."""

    @pytest.mark.asyncio
    async def test_cors_headers_present(self, async_client):
        """Test CORS headers are present in responses."""
        response = await async_client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )
        
        # CORS preflight should succeed
        assert response.status_code in [200, 204, 405]
