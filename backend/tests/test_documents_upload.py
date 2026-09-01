import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import UploadFile
from io import BytesIO
from fastapi.background import BackgroundTasks

from app.routers.documents import upload_document, get_document_status
from app.core.multitenancy import TenantContext
from app.models import Document


@pytest.mark.asyncio
async def test_upload_document_success():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    user = MagicMock()
    user.id = "u1"
    user.workspace_id = "w1"

    tenant = TenantContext(user_id="u1", workspace_id="w1")
    background_tasks = BackgroundTasks()

    file = UploadFile(filename="test.txt", file=BytesIO(b"hello"))

    with patch("app.routers.documents.upload_limiter.check_rate_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.return_value = (True, {})
        with patch("app.routers.documents.process_document_task") as mock_task:
            result = await upload_document(
                request=MagicMock(),
                background_tasks=background_tasks,
                file=file,
                documentId=None,
                workspaceId=None,
                db=db,
                user=user,
                tenant=tenant,
            )
    assert result.name == "test.txt"


@pytest.mark.asyncio
async def test_get_document_status_not_found():
    db = AsyncMock()
    db.get.return_value = None
    tenant = TenantContext(user_id="u1", workspace_id="w1")
    with pytest.raises(Exception):
        await get_document_status("missing", db=db, tenant=tenant)


@pytest.mark.asyncio
async def test_upload_document_rate_limited():
    db = AsyncMock()
    user = MagicMock()
    user.id = "u1"
    tenant = TenantContext(user_id="u1", workspace_id="w1")
    background_tasks = BackgroundTasks()
    file = UploadFile(filename="test.txt", file=BytesIO(b"hello"))

    with patch("app.routers.documents.upload_limiter.check_rate_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.return_value = (False, {"x": "y"})
        with pytest.raises(Exception):
            await upload_document(
                request=MagicMock(),
                background_tasks=background_tasks,
                file=file,
                documentId=None,
                workspaceId=None,
                db=db,
                user=user,
                tenant=tenant,
            )


@pytest.mark.asyncio
async def test_upload_document_too_large():
    db = AsyncMock()
    user = MagicMock()
    user.id = "u1"
    tenant = TenantContext(user_id="u1", workspace_id="w1")
    background_tasks = BackgroundTasks()
    file = UploadFile(filename="big.txt", file=BytesIO(b"x" * (51 * 1024 * 1024)))

    with patch("app.routers.documents.upload_limiter.check_rate_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.return_value = (True, {})
        with pytest.raises(Exception):
            await upload_document(
                request=MagicMock(),
                background_tasks=background_tasks,
                file=file,
                documentId=None,
                workspaceId=None,
                db=db,
                user=user,
                tenant=tenant,
            )


@pytest.mark.asyncio
async def test_upload_document_missing_filename():
    db = AsyncMock()
    user = MagicMock()
    user.id = "u1"
    tenant = TenantContext(user_id="u1", workspace_id="w1")
    background_tasks = BackgroundTasks()
    file = UploadFile(filename="", file=BytesIO(b"hello"))

    with patch("app.routers.documents.upload_limiter.check_rate_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.return_value = (True, {})
        with pytest.raises(Exception):
            await upload_document(
                request=MagicMock(),
                background_tasks=background_tasks,
                file=file,
                documentId=None,
                workspaceId=None,
                db=db,
                user=user,
                tenant=tenant,
            )


@pytest.mark.asyncio
async def test_upload_document_workspace_not_found():
    db = AsyncMock()
    db.get.return_value = None
    user = MagicMock()
    user.id = "u1"
    tenant = TenantContext(user_id="u1", workspace_id="w1")
    background_tasks = BackgroundTasks()
    file = UploadFile(filename="test.txt", file=BytesIO(b"hello"))

    with patch("app.routers.documents.upload_limiter.check_rate_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.return_value = (True, {})
        with pytest.raises(Exception):
            await upload_document(
                request=MagicMock(),
                background_tasks=background_tasks,
                file=file,
                documentId=None,
                workspaceId="w2",
                db=db,
                user=user,
                tenant=tenant,
            )


@pytest.mark.asyncio
async def test_upload_document_workspace_access_denied():
    db = AsyncMock()
    workspace = MagicMock()
    workspace.user_id = "other"
    db.get.return_value = workspace
    user = MagicMock()
    user.id = "u1"
    tenant = TenantContext(user_id="u1", workspace_id="w1")
    background_tasks = BackgroundTasks()
    file = UploadFile(filename="test.txt", file=BytesIO(b"hello"))

    with patch("app.routers.documents.upload_limiter.check_rate_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.return_value = (True, {})
        with pytest.raises(Exception):
            await upload_document(
                request=MagicMock(),
                background_tasks=background_tasks,
                file=file,
                documentId=None,
                workspaceId="w2",
                db=db,
                user=user,
                tenant=tenant,
            )


@pytest.mark.asyncio
async def test_upload_document_uses_tenant_workspace():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    tenant = TenantContext(user_id="u1", workspace_id="w1")
    background_tasks = BackgroundTasks()
    file = UploadFile(filename="test.txt", file=BytesIO(b"hello"))

    with patch("app.routers.documents.upload_limiter.check_rate_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.return_value = (True, {})
        with patch("app.routers.documents.process_document_task"):
            result = await upload_document(
                request=MagicMock(),
                background_tasks=background_tasks,
                file=file,
                documentId=None,
                workspaceId=None,
                db=db,
                user=None,
                tenant=tenant,
            )
    assert result.workspace_id == "w1"
