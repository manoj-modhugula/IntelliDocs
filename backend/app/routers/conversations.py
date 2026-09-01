"""
Conversation CRUD endpoints for persistent chat history.
"""

import json
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.multitenancy import TenantContext, get_tenant_context
from app.models import Conversation, ConversationMessage
from app.models import Workspace

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Schemas ------------------------------------------------------------------

class CitationSchema(BaseModel):
    id: str
    chunkId: Optional[str] = None
    documentId: str
    documentName: str
    pageNumber: Optional[int] = None
    chunkText: str
    relevanceScore: float


class MessageSchema(BaseModel):
    id: str
    role: str
    content: str
    citations: Optional[list[CitationSchema]] = None
    followUpSuggestions: Optional[list[str]] = None
    parentId: Optional[str] = None
    createdAt: datetime


class ConversationSchema(BaseModel):
    id: str
    title: str
    messages: list[MessageSchema]
    isPinned: bool = False
    pinnedMessageIds: list[str] = []
    createdAt: datetime
    updatedAt: datetime
    workspaceId: Optional[str] = None


class CreateConversationRequest(BaseModel):
    workspaceId: Optional[str] = None
    title: Optional[str] = "New Chat"


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    isPinned: Optional[bool] = None
    pinnedMessageIds: Optional[list[str]] = None


class AddMessageRequest(BaseModel):
    role: str
    content: str
    citations: Optional[list[CitationSchema]] = None
    followUpSuggestions: Optional[list[str]] = None
    parentId: Optional[str] = None


# --- Helpers ------------------------------------------------------------------

def _serialize_conversation(conv: Conversation, messages: list[ConversationMessage]) -> ConversationSchema:
    pinned_ids: list[str] = []
    if conv.pinned_message_ids:
        try:
            pinned_ids = json.loads(conv.pinned_message_ids)
        except json.JSONDecodeError:
            pinned_ids = []

    return ConversationSchema(
        id=conv.id,
        title=conv.title,
        isPinned=conv.is_pinned,
        pinnedMessageIds=pinned_ids,
        createdAt=conv.created_at,
        updatedAt=conv.updated_at,
        workspaceId=conv.workspace_id,
        messages=[
            MessageSchema(
                id=m.id,
                role=m.role,
                content=m.content,
                citations=[CitationSchema(**c) for c in json.loads(m.citations)] if m.citations else None,
                followUpSuggestions=json.loads(m.follow_up_suggestions) if m.follow_up_suggestions else None,
                parentId=m.parent_id,
                createdAt=m.created_at,
            )
            for m in messages
        ],
    )


# --- Endpoints ---------------------------------------------------------------─

@router.get("/", response_model=list[ConversationSchema])
async def list_conversations(
    workspaceId: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """List all conversations for the current user, optionally filtered by workspace."""
    if not tenant.user_id:
        return []

    query = (
        select(Conversation)
        .where(Conversation.user_id == tenant.user_id)
        .options(selectinload(Conversation.messages))
        .order_by(desc(Conversation.updated_at))
        .limit(50)
    )

    if workspaceId:
        query = query.where(Conversation.workspace_id == workspaceId)

    result = await db.execute(query)
    conversations = result.scalars().all()

    return [_serialize_conversation(conv, conv.messages) for conv in conversations]


@router.get("/{conversation_id}", response_model=ConversationSchema)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """Get a single conversation with all its messages."""
    if not tenant.user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    query = (
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == tenant.user_id)
        .options(selectinload(Conversation.messages))
    )
    result = await db.execute(query)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return _serialize_conversation(conv, conv.messages)


@router.post("/", response_model=ConversationSchema)
async def create_conversation(
    request: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """Create a new conversation."""
    if not tenant.user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Verify workspace access
    if request.workspaceId:
        workspace = await db.get(Workspace, request.workspaceId)
        if not workspace or workspace.user_id != tenant.user_id:
            raise HTTPException(status_code=403, detail="Access denied to workspace")

    import uuid
    conv = Conversation(
        id=str(uuid.uuid4()),
        title=request.title or "New Chat",
        workspace_id=request.workspaceId,
        user_id=tenant.user_id,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    return _serialize_conversation(conv, [])


@router.patch("/{conversation_id}", response_model=ConversationSchema)
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """Update conversation metadata (title, pinned state)."""
    if not tenant.user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    query = (
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == tenant.user_id)
        .options(selectinload(Conversation.messages))
    )
    result = await db.execute(query)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if request.title is not None:
        conv.title = request.title
    if request.isPinned is not None:
        conv.is_pinned = request.isPinned
    if request.pinnedMessageIds is not None:
        conv.pinned_message_ids = json.dumps(request.pinnedMessageIds)

    await db.commit()
    await db.refresh(conv)

    return _serialize_conversation(conv, conv.messages)


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """Delete a conversation and all its messages."""
    if not tenant.user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await db.execute(
        delete(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == tenant.user_id
        )
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"deleted": True}


@router.post("/{conversation_id}/messages", response_model=MessageSchema)
async def add_message(
    conversation_id: str,
    request: AddMessageRequest,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """Add a message to an existing conversation."""
    if not tenant.user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Verify ownership
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != tenant.user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    import uuid
    msg = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role=request.role,
        content=request.content,
        citations=json.dumps([c.model_dump() for c in request.citations]) if request.citations else None,
        follow_up_suggestions=json.dumps(request.followUpSuggestions) if request.followUpSuggestions else None,
        parent_id=request.parentId,
    )
    db.add(msg)

    if request.role == "user" and conv.title in ("New Chat", "", None):
        conv.title = request.content[:40] + ("..." if len(request.content) > 40 else "")

    await db.commit()
    await db.refresh(msg)

    return MessageSchema(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        citations=[CitationSchema(**c) for c in json.loads(msg.citations)] if msg.citations else None,
        followUpSuggestions=json.loads(msg.follow_up_suggestions) if msg.follow_up_suggestions else None,
        parentId=msg.parent_id,
        createdAt=msg.created_at,
    )


@router.delete("/{conversation_id}/messages/{message_id}")
async def delete_message(
    conversation_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """Delete a specific message from a conversation."""
    if not tenant.user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Verify ownership
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != tenant.user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        delete(ConversationMessage).where(
            ConversationMessage.id == message_id,
            ConversationMessage.conversation_id == conversation_id,
        )
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Message not found")

    return {"deleted": True}
