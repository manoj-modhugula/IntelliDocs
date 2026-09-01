"""Full tests for workspaces router."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestWorkspaceEndpoints:
    """Tests for workspace endpoints."""
    
    def test_list_workspaces_route_exists(self):
        """Test list workspaces route is registered."""
        from app.routers.workspaces import router
        paths = [r.path for r in router.routes]
        assert "/" in paths or "" in paths
    
    def test_create_workspace_route_exists(self):
        """Test create workspace route is registered."""
        from app.routers.workspaces import router
        methods = set()
        for r in router.routes:
            if hasattr(r, 'methods'):
                methods.update(r.methods)
        assert "POST" in methods
    
    def test_create_workspace_requires_auth(self):
        """Test create workspace requires authentication."""
        response = client.post(
            "/workspaces/",
            json={"description": "No name"}
        )
        assert response.status_code == 401
    
    def test_get_workspace_route_exists(self):
        """Test get workspace route is registered."""
        from app.routers.workspaces import router
        paths = [r.path for r in router.routes]
        assert any("{" in p for p in paths)  # Dynamic route
    
    def test_update_workspace_route_exists(self):
        """Test update workspace route is registered."""
        from app.routers.workspaces import router
        methods = set()
        for r in router.routes:
            if hasattr(r, 'methods'):
                methods.update(r.methods)
        assert "PUT" in methods
    
    def test_delete_workspace_route_exists(self):
        """Test delete workspace route is registered."""
        from app.routers.workspaces import router
        methods = set()
        for r in router.routes:
            if hasattr(r, 'methods'):
                methods.update(r.methods)
        assert "DELETE" in methods


class TestWorkspaceModels:
    """Tests for workspace models."""
    
    def test_workspace_model(self):
        """Test Workspace model."""
        from app.models import Workspace
        
        ws = Workspace(
            id="ws-1",
            name="Test",
            description="A test workspace",
        )
        
        assert ws.id == "ws-1"
        assert ws.name == "Test"
    
    def test_workspace_from_router(self):
        """Test workspace response structure."""
        from app.routers.workspaces import WorkspaceResponse
        
        ws = WorkspaceResponse(
            id="ws-1",
            name="Test",
            description="Description",
        )
        
        assert ws.id == "ws-1"
