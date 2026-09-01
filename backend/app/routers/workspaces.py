"""
Workspace management endpoints.
Privacy: Users can only list/access/update/delete workspaces they own.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import delete, select, func, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_auth, UserResponse
from app.models import Workspace, Document, Chunk, User
from app.services.cache import cache_service

router = APIRouter()
WORKSPACES_CACHE_TTL = 45  # seconds - balance freshness vs speed


def _user_owns_workspace(workspace: Workspace, user_id: Optional[str]) -> bool:
    """True if user owns this workspace."""
    if not user_id:
        return False
    return workspace.user_id == user_id


class WorkspaceCreate(BaseModel):
    """Request body for creating a workspace."""
    name: str
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Workspace name cannot be empty")
        if len(v) > 100:
            raise ValueError("Workspace name too long (max 100 characters)")
        return v


class WorkspaceResponse(BaseModel):
    """Response body for workspace endpoints."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: Optional[str]
    documentCount: int = 0
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


@router.post("/", response_model=WorkspaceResponse)
async def create_workspace(
    request: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    user: UserResponse = Depends(require_auth),
):
    """Create a new workspace. Requires authentication. Workspace is owned by the user."""
    workspace = Workspace(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        user_id=user.id,
    )
    
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    await cache_service.delete(f"workspaces:user:{user.id}")
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        documentCount=0,
        createdAt=workspace.created_at.isoformat() if workspace.created_at else None,
        updatedAt=workspace.updated_at.isoformat() if workspace.updated_at else None,
    )


DEFAULT_WORKSPACE_NAME = "My workspace"


@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    user: Optional[UserResponse] = Depends(get_current_user),
):
    """List workspaces owned by the current user. If user has none, create 'My workspace' and set as default."""
    if not user:
        return []
    query = (
        select(
            Workspace,
            func.count(Document.id).label("doc_count")
        )
        .outerjoin(
            Document,
            (Workspace.id == Document.workspace_id)
            & or_(Document.user_id == user.id, Document.user_id.is_(None))
        )
        .group_by(Workspace.id)
    )
    query = query.where(Workspace.user_id == user.id)
    query = query.order_by(Workspace.created_at.desc())
    result = await db.execute(query)
    rows = result.all()
    # Ensure every user has "My workspace" (default folder); create if missing
    has_my_workspace = any(w.name == DEFAULT_WORKSPACE_NAME for w, _ in rows)
    if not has_my_workspace:
        workspace = Workspace(
            id=str(uuid.uuid4()),
            name=DEFAULT_WORKSPACE_NAME,
            description=None,
            user_id=user.id,
        )
        db.add(workspace)
        user_row = await db.get(User, user.id)
        if user_row and user_row.default_workspace_id is None:
            user_row.default_workspace_id = workspace.id
        await db.commit()
        await db.refresh(workspace)
        # Prepend "My workspace" so it appears first; doc_count 0
        rows = [(workspace, 0)] + list(rows)
    elif not rows:
        # No workspaces at all (shouldn't happen after above, but safety)
        workspace = Workspace(
            id=str(uuid.uuid4()),
            name=DEFAULT_WORKSPACE_NAME,
            description=None,
            user_id=user.id,
        )
        db.add(workspace)
        user_row = await db.get(User, user.id)
        if user_row:
            user_row.default_workspace_id = workspace.id
        await db.commit()
        await db.refresh(workspace)
        return [
            WorkspaceResponse(
                id=workspace.id,
                name=workspace.name,
                description=workspace.description,
                documentCount=0,
                createdAt=workspace.created_at.isoformat() if workspace.created_at else None,
                updatedAt=workspace.updated_at.isoformat() if workspace.updated_at else None,
            )
        ]
    return [
        WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            description=workspace.description,
            documentCount=doc_count,
            createdAt=workspace.created_at.isoformat() if workspace.created_at else None,
            updatedAt=workspace.updated_at.isoformat() if workspace.updated_at else None,
        )
        for workspace, doc_count in rows
    ]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    user: Optional[UserResponse] = Depends(get_current_user),
):
    """Get a workspace by ID. Privacy: only if user owns it."""
    workspace = await db.get(Workspace, workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if not user or not _user_owns_workspace(workspace, user.id):
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    
    # Get document count (filtered by user ownership for consistency with list_workspaces)
    count_query = select(func.count(Document.id)).where(
        Document.workspace_id == workspace_id,
        or_(Document.user_id == user.id, Document.user_id.is_(None))
    )
    result = await db.execute(count_query)
    doc_count = result.scalar() or 0
    
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        documentCount=doc_count,
        createdAt=workspace.created_at.isoformat() if workspace.created_at else None,
        updatedAt=workspace.updated_at.isoformat() if workspace.updated_at else None,
    )


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    request: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    user: Optional[UserResponse] = Depends(get_current_user),
):
    """Update a workspace. Privacy: only if user owns it."""
    workspace = await db.get(Workspace, workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if not user or not _user_owns_workspace(workspace, user.id):
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    
    workspace.name = request.name
    workspace.description = request.description
    await db.commit()
    await db.refresh(workspace)
    if workspace.user_id:
        await cache_service.delete(f"workspaces:user:{workspace.user_id}")
    
    # Get document count for this workspace (filtered by user ownership)
    count_query = select(func.count(Document.id)).where(
        Document.workspace_id == workspace_id,
        or_(Document.user_id == user.id, Document.user_id.is_(None))
    )
    result = await db.execute(count_query)
    doc_count = result.scalar() or 0
    
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        documentCount=doc_count,
        createdAt=workspace.created_at.isoformat() if workspace.created_at else None,
        updatedAt=workspace.updated_at.isoformat() if workspace.updated_at else None,
    )


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    user: Optional[UserResponse] = Depends(get_current_user),
):
    """Delete a workspace. Privacy: only if user owns it."""
    workspace = await db.get(Workspace, workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if not user or not _user_owns_workspace(workspace, user.id):
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    # Cannot delete the user's default workspace ("My workspace")
    if user.workspace_id == workspace_id or workspace.name == DEFAULT_WORKSPACE_NAME:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete your default workspace. Set another workspace as default in Settings first.",
        )

    user_id = workspace.user_id
    # Permanently delete all documents in this workspace (and their chunks) so they are never seen again
    await db.execute(
        delete(Chunk).where(
            Chunk.document_id.in_(select(Document.id).where(Document.workspace_id == workspace_id))
        )
    )
    await db.execute(delete(Document).where(Document.workspace_id == workspace_id))
    # If this workspace is user's default, clear it
    await db.execute(
        update(User)
        .where(User.id == user_id, User.default_workspace_id == workspace_id)
        .values(default_workspace_id=None)
    )
    await db.delete(workspace)
    await db.commit()
    if user_id:
        await cache_service.delete(f"workspaces:user:{user_id}")
        await cache_service.delete(f"documents:{user_id}:ws:{workspace_id}")
        await cache_service.delete(f"documents:{user_id}:ws:none")
    return {"status": "deleted", "id": workspace_id}
