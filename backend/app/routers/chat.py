"""
Chat endpoints for RAG-powered Q&A.
Includes rate limiting to prevent API abuse.
"""

import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings, auth_required
from app.core.rate_limit import chat_limiter
from app.core.multitenancy import TenantContext, get_tenant_context
from app.models import Workspace, Skill
from app.services.rag import rag_service

router = APIRouter()
logger = logging.getLogger(__name__)


async def _user_can_access_workspace_for_chat(db: AsyncSession, tenant: TenantContext, workspace_id: str) -> bool:
    if tenant.can_access_workspace(workspace_id):
        return True
    if not tenant.user_id:
        return False
    workspace = await db.get(Workspace, workspace_id)
    return workspace is not None and workspace.user_id == tenant.user_id


# Skills: slash-triggered tags that inject LLM instructions (name -> instruction for the model).
# Only built-in skill with an action: /short. /dark and /light are theme shortcuts (client-only).
CHAT_SKILLS: dict[str, str] = {
    "short": "Give a straightforward, short answer without any extra or huge explanation. Be concise and direct.",
}

class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str
    conversationId: Optional[str] = None
    workspaceId: Optional[str] = None
    documentIds: Optional[list[str]] = None  # Restrict search to these document IDs (per-document scope)
    contextChunkId: Optional[str] = None  # Force-include this chunk (e.g. "Ask about this passage")
    skill: Optional[str] = None  # Slash skill name (e.g. "short") -> injects CHAT_SKILLS instruction
    strategy: Optional[str] = None  # Override for eval: SEMANTIC, KEYWORD, HYBRID
    naive: Optional[bool] = False  # Naive RAG (no reranker/HyDE/multi-query) for benchmark


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""
    answer: str
    citations: list
    strategy: str
    from_cache: Optional[bool] = False


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if auth_required() and not tenant.user_id:
        raise HTTPException(status_code=401, detail="Authentication required for chat")
    # Rate limiting
    allowed, headers = await chat_limiter.check_rate_limit(
        http_request, user_id=tenant.user_id
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers=headers)
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(request.message) > 50000:
        raise HTTPException(status_code=400, detail="Message too long (max 50,000 characters)")
    # Optional workspace filter: if provided, user must have access (default or owned). If omitted, RAG searches all user docs.
    workspace_id = request.workspaceId
    if workspace_id and not await _user_can_access_workspace_for_chat(db, tenant, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this workspace")

    skill_instruction = CHAT_SKILLS.get(request.skill) if request.skill else None
    if skill_instruction is None and request.skill and tenant.user_id:
        result_skill = await db.execute(
            select(Skill).where(Skill.name == request.skill, Skill.user_id == tenant.user_id)
        )
        skill_row = result_skill.scalar_one_or_none()
        if skill_row:
            skill_instruction = skill_row.action
    result = await rag_service.answer(
        db,
        request.message,
        workspace_id=workspace_id,
        user_id=tenant.user_id,
        document_ids=request.documentIds if request.documentIds else None,
        context_chunk_id=request.contextChunkId,
        skill_instruction=skill_instruction,
        strategy_override=request.strategy,
        naive_mode=request.naive or False,
    )
    
    return ChatResponse(
        answer=result["answer"],
        citations=result["citations"],
        strategy=result["strategy"],
        from_cache=result.get("from_cache", False),
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """Streaming chat endpoint using Server-Sent Events."""
    if auth_required() and not tenant.user_id:
        raise HTTPException(status_code=401, detail="Authentication required for chat")
    allowed, headers = await chat_limiter.check_rate_limit(
        http_request, user_id=tenant.user_id
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers=headers)
    workspace_id = request.workspaceId
    if workspace_id and not await _user_can_access_workspace_for_chat(db, tenant, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(request.message) > 50000:
        raise HTTPException(status_code=400, detail="Message too long (max 50,000 characters)")

    if request.documentIds:
        logger.info("Chat stream document scope: restricting to document_ids=%s", request.documentIds)

    skill_instruction = CHAT_SKILLS.get(request.skill) if request.skill else None
    if skill_instruction is None and request.skill and tenant.user_id:
        result_skill = await db.execute(
            select(Skill).where(Skill.name == request.skill, Skill.user_id == tenant.user_id)
        )
        skill_row = result_skill.scalar_one_or_none()
        if skill_row:
            skill_instruction = skill_row.action
    async def generate():
        try:
            async for chunk in rag_service.answer_stream(
                db,
                request.message,
                workspace_id=workspace_id,
                user_id=tenant.user_id,
                document_ids=request.documentIds if request.documentIds else None,
                context_chunk_id=request.contextChunkId,
                skill_instruction=skill_instruction,
                strategy_override=request.strategy,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as exc:
            logger.error("Unhandled error in chat stream generator: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': 'An unexpected error occurred. Please try again.'})}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
