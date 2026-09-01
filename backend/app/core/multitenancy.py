"""
Multi-tenancy isolation module.
Provides workspace-level data isolation with proper security checks.
"""

import logging
from typing import Optional, List
from fastapi import HTTPException, status, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserResponse, get_current_user
from app.core.database import get_db

logger = logging.getLogger(__name__)


class TenantContext:
    
    def __init__(
        self,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        is_admin: bool = False,
    ):
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.is_admin = is_admin
    
    def can_access_workspace(self, target_workspace_id: str) -> bool:
        if self.is_admin:
            return True
        # User with no workspace cannot access any workspace-scoped resource
        if self.workspace_id is None:
            return False
        return self.workspace_id == target_workspace_id
    
    def can_access_document(self, document_workspace_id: Optional[str]) -> bool:
        if self.is_admin:
            return True
        # Document with no workspace: only accessible to users with no workspace (anonymous/demo)
        if document_workspace_id is None:
            return self.workspace_id is None
        # User with no workspace cannot access workspace-scoped documents
        if self.workspace_id is None:
            return False
        return self.workspace_id == document_workspace_id


async def get_tenant_context(
    user: Optional[UserResponse] = Depends(get_current_user),
) -> TenantContext:
    if user is None:
        return TenantContext()
    
    return TenantContext(
        user_id=user.id,
        workspace_id=user.workspace_id,
        is_admin=False,
    )


async def verify_workspace_access(
    workspace_id: str,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> str:
    if not tenant.can_access_workspace(workspace_id):
        logger.warning(
            f"Access denied: user {tenant.user_id} tried to access workspace {workspace_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this workspace is denied",
        )
    
    # Verify workspace exists
    result = await db.execute(
        text("SELECT id FROM workspaces WHERE id = :id"),
        {"id": workspace_id}
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    
    return workspace_id


async def verify_document_access(
    document_id: str,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> str:
    # Get document's workspace
    result = await db.execute(
        text("SELECT workspace_id FROM documents WHERE id = :id"),
        {"id": document_id}
    )
    row = result.one_or_none()
    
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    document_workspace_id = row[0]
    
    if not tenant.can_access_document(document_workspace_id):
        logger.warning(
            f"Access denied: user {tenant.user_id} tried to access document {document_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this document is denied",
        )
    
    return document_id


class WorkspaceScopedQuery:
    """
    Helper for building workspace-scoped database queries.
    Ensures all queries include proper workspace filtering.
    """
    
    def __init__(self, tenant: TenantContext):
        self.tenant = tenant
    
    def get_workspace_filter(self) -> Optional[str]:
        if self.tenant.is_admin:
            return None
        return self.tenant.workspace_id
    
    def build_document_filter(self, table_alias: str = "d") -> str:
        workspace_id = self.get_workspace_filter()
        if workspace_id is None:
            return "1=1"  # No filter
        return f"{table_alias}.workspace_id = :workspace_id"
    
    def get_filter_params(self) -> dict:
        workspace_id = self.get_workspace_filter()
        if workspace_id is None:
            return {}
        return {"workspace_id": workspace_id}


async def list_accessible_workspaces(
    tenant: TenantContext,
    db: AsyncSession,
) -> List[str]:
    if tenant.is_admin:
        result = await db.execute(text("SELECT id FROM workspaces"))
        return [row[0] for row in result.fetchall()]
    
    if tenant.workspace_id:
        return [tenant.workspace_id]
    
    # User with no workspace - might have access to all or none
    # Default: return empty (no access without explicit workspace)
    return []


async def ensure_workspace_exists(
    workspace_id: str,
    db: AsyncSession,
) -> bool:
    result = await db.execute(
        text("SELECT id FROM workspaces WHERE id = :id"),
        {"id": workspace_id}
    )
    
    if result.scalar_one_or_none():
        return True
    
    # Workspace doesn't exist
    return False
