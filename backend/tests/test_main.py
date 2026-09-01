"""Tests for main application module."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


class TestAppConfiguration:
    """Tests for app configuration."""

    def test_app_has_title(self):
        """Test app has title configured."""
        from app.main import app
        assert app.title == "IntelliDocs API"

    def test_app_has_version(self):
        """Test app has version configured."""
        from app.main import app
        assert app.version == "1.0.0"

    def test_app_has_docs_url(self):
        """Test app has docs endpoint."""
        from app.main import app
        assert app.docs_url == "/docs"

    def test_app_has_redoc_url(self):
        """Test app has redoc endpoint."""
        from app.main import app
        assert app.redoc_url == "/redoc"


class TestRouterInclusion:
    """Tests for router inclusion."""

    def test_health_router_included(self):
        """Test health router is included."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert "/health" in routes

    def test_chat_router_included(self):
        """Test chat router is included."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/chat" in r for r in routes)

    def test_documents_router_included(self):
        """Test documents router is included."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/documents" in r for r in routes)

    def test_workspaces_router_included(self):
        """Test workspaces router is included."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/workspaces" in r for r in routes)

    def test_prometheus_router_included(self):
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/prometheus" in r for r in routes)


class TestBodyLimits:
    def test_json_limit_is_10mb_and_uploads_are_50mb(self):
        from app.main import _MAX_JSON_BYTES, _MAX_UPLOAD_BYTES

        assert _MAX_JSON_BYTES == 10 * 1024 * 1024
        assert _MAX_UPLOAD_BYTES == 50 * 1024 * 1024


class TestCORSMiddleware:
    """Tests for CORS middleware."""

    def test_cors_is_configured(self):
        """Test CORS middleware is added."""
        from app.main import app
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes
