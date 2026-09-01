"""Tests for API routers."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
from app.main import app


class TestHealthRouter:
    """Tests for health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, async_client):
        """Test health endpoint returns ok."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] in ["ok", "healthy"]


class TestChatRouter:
    """Tests for chat endpoints."""

    @pytest.mark.asyncio
    async def test_chat_requires_message(self, async_client):
        """Test that chat requires a message."""
        response = await async_client.post(
            "/chat/",
            json={"message": ""}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_chat_accepts_valid_request(self, async_client):
        """Test chat with valid request."""
        with patch("app.routers.chat.rag_service") as mock_rag:
            mock_rag.answer = AsyncMock(return_value={
                "answer": "Test answer",
                "citations": [],
                "strategy": "HYBRID",
            })
            
            response = await async_client.post(
                "/chat/",
                json={"message": "What is the document about?"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data

    @pytest.mark.asyncio
    async def test_chat_stream_endpoint_exists(self, async_client):
        """Test that stream endpoint is accessible."""
        with patch("app.routers.chat.rag_service") as mock_rag:
            async def mock_stream(*args, **kwargs):
                yield {"type": "token", "content": "test"}
            
            mock_rag.answer_stream = mock_stream
            
            response = await async_client.post(
                "/chat/stream",
                json={"message": "test"}
            )
            
            # Should return streaming response
            assert response.status_code == 200


class TestDocumentsRouter:
    """Tests for documents endpoints."""

    def test_documents_router_configured(self):
        """Test documents router is configured."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/documents" in r for r in routes)

    @pytest.mark.asyncio
    async def test_upload_requires_file(self, async_client):
        """Test that upload requires a file."""
        response = await async_client.post("/documents/upload")
        # Should fail without file
        assert response.status_code in [400, 422, 500]


class TestWorkspacesRouter:
    """Tests for workspaces endpoints."""

    def test_workspaces_endpoint_exists(self):
        """Test that workspaces router is configured."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/workspaces" in r for r in routes)

    def test_workspace_create_model(self):
        """Test workspace create schema."""
        from app.routers.workspaces import WorkspaceCreate
        ws = WorkspaceCreate(name="Test", description="Desc")
        assert ws.name == "Test"


class TestPrometheusRouter:
    @pytest.mark.asyncio
    async def test_prometheus_metrics(self, async_client):
        response = await async_client.get("/prometheus/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
