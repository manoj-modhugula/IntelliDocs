"""Full tests for main application module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestAppConfiguration:
    """Tests for app configuration."""
    
    def test_app_title(self):
        """Test app has correct title."""
        from app.main import app
        assert app.title == "IntelliDocs API"
    
    def test_app_version(self):
        """Test app has version."""
        from app.main import app
        assert app.version is not None
    
    def test_app_description(self):
        """Test app has description."""
        from app.main import app
        assert app.description is not None


class TestRouterInclusion:
    """Tests for router inclusion."""
    
    def test_health_router_included(self):
        """Test health router is included."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/health" in r for r in routes)
    
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
    
    def test_auth_router_included(self):
        """Test auth router is included."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/auth" in r for r in routes)
    
    def test_prometheus_metrics_included(self):
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/prometheus" in r for r in routes)
    
    def test_prometheus_router_included(self):
        """Test prometheus router is included."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/prometheus" in r for r in routes)


class TestCORSMiddleware:
    """Tests for CORS middleware."""
    
    def test_cors_enabled(self):
        """Test CORS middleware is enabled."""
        from app.main import app
        
        # Check if CORSMiddleware is in the middleware stack
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes


class TestExceptionHandler:
    """Tests for exception handler."""
    
    def test_exception_handler_registered(self):
        """Test exception handler is registered."""
        from app.main import app
        
        # Exception handlers are registered
        assert len(app.exception_handlers) > 0


class TestOpenAPI:
    """Tests for OpenAPI documentation."""
    
    def test_openapi_schema_exists(self):
        """Test OpenAPI schema is generated."""
        from app.main import app
        
        schema = app.openapi()
        
        assert schema is not None
        assert "openapi" in schema
        assert "info" in schema
    
    def test_openapi_paths_exist(self):
        """Test OpenAPI schema has paths."""
        from app.main import app
        
        schema = app.openapi()
        
        assert "paths" in schema
        assert len(schema["paths"]) > 0
