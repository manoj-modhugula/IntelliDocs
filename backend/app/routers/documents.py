"""
Document management endpoints with multi-tenant isolation.
"""

import uuid
import logging
from io import BytesIO
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, UserResponse
from app.core.config import auth_required
from app.core.multitenancy import TenantContext, get_tenant_context
from app.core.rate_limit import upload_limiter
from app.models import Document, DocumentStatus, Workspace, User
from app.services.ingestion import ingestion_service
from app.services.cache import cache_service
from app.services.storage import storage_service

logger = logging.getLogger(__name__)
router = APIRouter()


async def _user_can_access_document(db: AsyncSession, tenant: TenantContext, document: Document) -> bool:
    if tenant.user_id and document.user_id and document.user_id != tenant.user_id:
        return False
    if tenant.can_access_document(document.workspace_id):
        return True
    # Unassigned docs (workspace_id=null): allow if doc has no owner or belongs to this user
    if not document.workspace_id and tenant.user_id:
        if document.user_id is None or document.user_id == tenant.user_id:
            return True
    if not document.workspace_id or not tenant.user_id:
        return False
    workspace = await db.get(Workspace, document.workspace_id)
    return workspace is not None and workspace.user_id == tenant.user_id


async def _user_can_access_workspace(db: AsyncSession, tenant: TenantContext, workspace_id: str) -> bool:
    if tenant.can_access_workspace(workspace_id):
        return True
    if not tenant.user_id:
        return False
    workspace = await db.get(Workspace, workspace_id)
    return workspace is not None and workspace.user_id == tenant.user_id


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    type: str
    size: int
    status: str
    workspace_id: Optional[str] = None
    chunkCount: Optional[int] = None
    errorMessage: Optional[str] = None
    created_at: Optional[str] = None


class DocumentStatusResponse(BaseModel):
    status: str
    chunkCount: Optional[int] = None
    error: Optional[str] = None


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    documentId: Optional[str] = Form(None),
    workspaceId: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: Optional[UserResponse] = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if auth_required() and not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    allowed, headers = await upload_limiter.check_rate_limit(
        request, user_id=user.id if user else None
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Upload rate limit exceeded", headers=headers)

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content_type = file.content_type or "application/octet-stream"

    # Validate file type
    allowed_types = {
        "application/pdf", "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain", "text/markdown",
    }
    allowed_extensions = {".pdf", ".doc", ".docx", ".txt", ".md"}
    ext = ("." + file.filename.rsplit(".", 1)[-1].lower()) if "." in file.filename else ""
    if content_type not in allowed_types and ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: PDF, DOC, DOCX, TXT, MD")

    # Read file content
    file_bytes = await file.read()
    file_size = len(file_bytes)
    
    # Check size (50MB limit)
    if file_size > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")
    
    # Determine workspace: never leave logged-in user's doc unassigned
    effective_workspace = workspaceId
    if not effective_workspace and user:
        effective_workspace = user.workspace_id
    if not effective_workspace and tenant.workspace_id:
        effective_workspace = tenant.workspace_id
    if not effective_workspace and user:
        user_row = await db.get(User, user.id)
        if user_row and user_row.default_workspace_id:
            effective_workspace = user_row.default_workspace_id
        else:
            r = await db.execute(select(Workspace).where(Workspace.user_id == user.id).limit(1))
            first_ws = r.scalar_one_or_none()
            if first_ws:
                effective_workspace = first_ws.id
                if user_row and not user_row.default_workspace_id:
                    user_row.default_workspace_id = first_ws.id
                    await db.commit()
            else:
                from app.routers.workspaces import DEFAULT_WORKSPACE_NAME
                new_ws = Workspace(
                    id=str(uuid.uuid4()),
                    name=DEFAULT_WORKSPACE_NAME,
                    description=None,
                    user_id=user.id,
                )
                db.add(new_ws)
                await db.flush()
                effective_workspace = new_ws.id
                if user_row:
                    user_row.default_workspace_id = new_ws.id
                await db.commit()
    
    # Verify user can access this workspace (default workspace, or workspace they own, or legacy unowned)
    if effective_workspace:
        if not tenant.can_access_workspace(effective_workspace):
            workspace = await db.get(Workspace, effective_workspace)
            if not workspace:
                raise HTTPException(status_code=404, detail="Workspace not found")
            # Allow if workspace is owned by this user, or has no owner (legacy)
            if workspace.user_id is not None and workspace.user_id != tenant.user_id:
                raise HTTPException(status_code=403, detail="Access denied to this workspace")
    
    # Create document record
    doc_id = documentId or str(uuid.uuid4())
    try:
        stored_key = await storage_service.upload_document(
            file=BytesIO(file_bytes),
            filename=file.filename,
            content_type=content_type,
            document_id=doc_id,
        )
    except Exception as e:
        logger.error("Failed to store original file for %s: %s", doc_id, e)
        raise HTTPException(status_code=500, detail="Failed to store document file")

    document = Document(
        id=doc_id,
        name=file.filename,
        file_type=content_type,
        file_size=file_size,
        s3_key=stored_key,
        status=DocumentStatus.PENDING.value,
        workspace_id=effective_workspace,
        user_id=user.id if user else None,
    )
    
    db.add(document)
    await db.commit()
    await db.refresh(document)
    if user:
        await cache_service.delete(f"workspaces:user:{user.id}")
    logger.info(f"Document {doc_id} uploaded by user {user.id if user else 'anonymous'}")
    
    # Process document in background
    background_tasks.add_task(
        process_document_task,
        doc_id,
        file_bytes,
        content_type,
    )
    
    return DocumentResponse(
        id=document.id,
        name=document.name,
        type=document.file_type,
        size=document.file_size,
        status=document.status,
        workspace_id=document.workspace_id,
        created_at=document.created_at.isoformat() if document.created_at else None,
    )


# Max time for document processing (embedding can be slow without mock)
PROCESS_DOCUMENT_TIMEOUT_SECONDS = 300  # 5 minutes


async def process_document_task(document_id: str, file_bytes: bytes, file_type: str):
    """Background task to process uploaded document."""
    import asyncio
    from app.core.database import async_session
    
    async with async_session() as db:
        try:
            await asyncio.wait_for(
                ingestion_service.process_document(
                    db,
                    document_id,
                    file_bytes,
                    file_type,
                ),
                timeout=PROCESS_DOCUMENT_TIMEOUT_SECONDS,
            )
            logger.info(f"Document {document_id} processed successfully")
        except asyncio.TimeoutError:
            logger.error(f"Document {document_id} processing timed out after {PROCESS_DOCUMENT_TIMEOUT_SECONDS}s")
            try:
                document = await db.get(Document, document_id)
                if document:
                    document.status = DocumentStatus.ERROR.value
                    document.error_message = (
                        "Processing timed out. Check backend logs and AWS Bedrock/embedding availability."
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"Failed to set document {document_id} to error: {e}")
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")
            # Ensure document is never left stuck in PROCESSING (e.g. AWS/embedding failure)
            try:
                document = await db.get(Document, document_id)
                if document and document.status == DocumentStatus.PROCESSING.value:
                    document.status = DocumentStatus.ERROR.value
                    document.error_message = (str(e) or "Processing failed")[:500]
                    await db.commit()
            except Exception as inner:
                logger.error(f"Failed to set document {document_id} to error: {inner}")


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    document = await db.get(Document, document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check access (default workspace or workspace owned by user)
    if not await _user_can_access_document(db, tenant, document):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return DocumentResponse(
        id=document.id,
        name=document.name,
        type=document.file_type,
        size=document.file_size,
        status=document.status,
        workspace_id=document.workspace_id,
        chunkCount=document.chunk_count,
        errorMessage=document.error_message,
        created_at=document.created_at.isoformat() if document.created_at else None,
    )


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not await _user_can_access_document(db, tenant, document):
        raise HTTPException(status_code=403, detail="Access denied")
    if not document.s3_key:
        raise HTTPException(status_code=404, detail="Original file is not available")
    try:
        data = await storage_service.download_document(document.s3_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Original file is not available")
    except Exception as e:
        logger.error("Failed to read file for document %s: %s", document_id, e)
        raise HTTPException(status_code=500, detail="Failed to read document file")

    media_type = document.file_type or "application/octet-stream"
    filename = document.name or "document"
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    document = await db.get(Document, document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check access (default workspace or workspace owned by user) so status poll works when upload is to a non-default workspace
    if not await _user_can_access_document(db, tenant, document):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return DocumentStatusResponse(
        status=document.status,
        chunkCount=document.chunk_count if document.status == "ready" else None,
        error=document.error_message if document.status == "error" else None,
    )


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    workspaceId: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if workspaceId and not await _user_can_access_workspace(db, tenant, workspaceId):
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    query = select(Document).order_by(Document.created_at.desc())
    if tenant.user_id:
        # Allow legacy docs with null user_id in owned workspaces
        query = query.where(or_(Document.user_id == tenant.user_id, Document.user_id.is_(None)))
    if workspaceId:
        query = query.where(Document.workspace_id == workspaceId)
    else:
        # No workspace filter: show docs from all workspaces user owns + unassigned (so "Default workspace" shows all my docs)
        if tenant.user_id:
            user_workspaces = select(Workspace.id).where(Workspace.user_id == tenant.user_id)
            query = query.where(
                or_(
                    Document.workspace_id.is_(None),
                    Document.workspace_id.in_(user_workspaces),
                )
            )
        else:
            query = query.where(Document.workspace_id.is_(None))
    result = await db.execute(query)
    documents = result.scalars().all()
    return [
        DocumentResponse(
            id=doc.id,
            name=doc.name,
            type=doc.file_type,
            size=doc.file_size,
            status=doc.status,
            workspace_id=doc.workspace_id,
            chunkCount=doc.chunk_count,
            errorMessage=doc.error_message,
            created_at=doc.created_at.isoformat() if doc.created_at else None,
        )
        for doc in documents
    ]


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    document = await db.get(Document, document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check access (default workspace or workspace owned by user)
    if not await _user_can_access_document(db, tenant, document):
        raise HTTPException(status_code=403, detail="Access denied")
    
    stored_key = document.s3_key
    await db.delete(document)
    await db.commit()
    if stored_key:
        try:
            await storage_service.delete_document(stored_key)
        except Exception as e:
            logger.warning("Failed to delete stored file %s: %s", stored_key, e)
    if tenant.user_id:
        await cache_service.delete(f"workspaces:user:{tenant.user_id}")
    logger.info(f"Document {document_id} deleted")
    
    return {"status": "deleted", "id": document_id}
