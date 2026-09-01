"""Tests for multi-tenancy module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.multitenancy import TenantContext, WorkspaceScopedQuery


class TestTenantContext:
    """Tests for TenantContext."""
    
    def test_create_anonymous_context(self):
        """Test creating anonymous tenant context."""
        ctx = TenantContext()
        
        assert ctx.user_id is None
        assert ctx.workspace_id is None
        assert ctx.is_admin is False
    
    def test_create_user_context(self):
        """Test creating user tenant context."""
        ctx = TenantContext(
            user_id="user-123",
            workspace_id="ws-456",
            is_admin=False,
        )
        
        assert ctx.user_id == "user-123"
        assert ctx.workspace_id == "ws-456"
        assert ctx.is_admin is False
    
    def test_create_admin_context(self):
        """Test creating admin tenant context."""
        ctx = TenantContext(
            user_id="admin-1",
            workspace_id="ws-1",
            is_admin=True,
        )
        
        assert ctx.is_admin is True
    
    def test_can_access_workspace_admin(self):
        """Test admin can access any workspace."""
        ctx = TenantContext(
            user_id="admin-1",
            workspace_id="ws-1",
            is_admin=True,
        )
        
        assert ctx.can_access_workspace("ws-1") is True
        assert ctx.can_access_workspace("ws-other") is True
        assert ctx.can_access_workspace("any-workspace") is True
    
    def test_can_access_workspace_own(self):
        """Test user can access their own workspace."""
        ctx = TenantContext(
            user_id="user-1",
            workspace_id="ws-1",
            is_admin=False,
        )
        
        assert ctx.can_access_workspace("ws-1") is True
    
    def test_cannot_access_other_workspace(self):
        """Test user cannot access other workspace."""
        ctx = TenantContext(
            user_id="user-1",
            workspace_id="ws-1",
            is_admin=False,
        )
        
        assert ctx.can_access_workspace("ws-other") is False
    
    def test_no_workspace_restriction(self):
        """Test user with no workspace cannot access workspace-scoped resources."""
        ctx = TenantContext(
            user_id="user-1",
            workspace_id=None,
            is_admin=False,
        )
        # Security: users without assigned workspace cannot access any workspace
        assert ctx.can_access_workspace("ws-any") is False
    
    def test_can_access_document_admin(self):
        """Test admin can access any document."""
        ctx = TenantContext(is_admin=True)
        
        assert ctx.can_access_document("ws-1") is True
        assert ctx.can_access_document("ws-2") is True
        assert ctx.can_access_document(None) is True
    
    def test_can_access_document_own_workspace(self):
        """Test user can access documents in their workspace."""
        ctx = TenantContext(
            user_id="user-1",
            workspace_id="ws-1",
            is_admin=False,
        )
        assert ctx.can_access_document("ws-1") is True
        # Document with no workspace: only accessible to users with no workspace
        assert ctx.can_access_document(None) is False
    
    def test_cannot_access_document_other_workspace(self):
        """Test user cannot access documents in other workspace."""
        ctx = TenantContext(
            user_id="user-1",
            workspace_id="ws-1",
            is_admin=False,
        )
        
        assert ctx.can_access_document("ws-2") is False


class TestWorkspaceScopedQuery:
    """Tests for WorkspaceScopedQuery helper."""
    
    def test_get_workspace_filter_admin(self):
        """Test admin has no workspace filter."""
        ctx = TenantContext(is_admin=True, workspace_id="ws-1")
        query_helper = WorkspaceScopedQuery(ctx)
        
        assert query_helper.get_workspace_filter() is None
    
    def test_get_workspace_filter_user(self):
        """Test user gets their workspace filter."""
        ctx = TenantContext(
            user_id="user-1",
            workspace_id="ws-123",
            is_admin=False,
        )
        query_helper = WorkspaceScopedQuery(ctx)
        
        assert query_helper.get_workspace_filter() == "ws-123"
    
    def test_get_workspace_filter_no_workspace(self):
        """Test user with no workspace has no filter."""
        ctx = TenantContext(user_id="user-1", is_admin=False)
        query_helper = WorkspaceScopedQuery(ctx)
        
        assert query_helper.get_workspace_filter() is None
    
    def test_build_document_filter_with_workspace(self):
        """Test building document filter."""
        ctx = TenantContext(workspace_id="ws-1", is_admin=False)
        query_helper = WorkspaceScopedQuery(ctx)
        
        filter_sql = query_helper.build_document_filter()
        
        assert "workspace_id" in filter_sql
    
    def test_build_document_filter_no_workspace(self):
        """Test building document filter with no workspace."""
        ctx = TenantContext(is_admin=True)
        query_helper = WorkspaceScopedQuery(ctx)
        
        filter_sql = query_helper.build_document_filter()
        
        assert filter_sql == "1=1"  # No filter
    
    def test_get_filter_params(self):
        """Test getting filter parameters."""
        ctx = TenantContext(workspace_id="ws-456", is_admin=False)
        query_helper = WorkspaceScopedQuery(ctx)
        
        params = query_helper.get_filter_params()
        
        assert params == {"workspace_id": "ws-456"}
    
    def test_anonymous_can_access_document_no_workspace(self):
        """Test anonymous user can access shared documents (no workspace)."""
        ctx = TenantContext(workspace_id=None, is_admin=False)
        assert ctx.can_access_document(None) is True

    def test_get_filter_params_no_filter(self):
        """Test getting empty filter parameters."""
        ctx = TenantContext(is_admin=True)
        query_helper = WorkspaceScopedQuery(ctx)
        
        params = query_helper.get_filter_params()
        
        assert params == {}
