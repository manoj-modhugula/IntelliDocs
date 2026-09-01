"""Tests for workspaces router."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestWorkspaceModels:
    """Tests for workspace models."""

    def test_workspace_create_model(self):
        """Test WorkspaceCreate model."""
        from app.routers.workspaces import WorkspaceCreate
        ws = WorkspaceCreate(name="Test Workspace")
        assert ws.name == "Test Workspace"

    def test_workspace_create_with_description(self):
        """Test WorkspaceCreate with description."""
        from app.routers.workspaces import WorkspaceCreate
        ws = WorkspaceCreate(name="Test", description="A test workspace")
        assert ws.description == "A test workspace"

    def test_workspace_response_model(self):
        """Test WorkspaceResponse model exists."""
        from app.routers.workspaces import WorkspaceResponse
        assert WorkspaceResponse is not None


class TestWorkspaceEndpoints:
    """Tests for workspace endpoints."""

    def test_workspaces_router_configured(self):
        """Test workspaces router is configured."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/workspaces" in r for r in routes)
