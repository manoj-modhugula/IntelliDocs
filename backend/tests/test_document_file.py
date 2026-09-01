"""Original file is kept on upload and served/deleted with the document."""

from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.core.multitenancy import TenantContext
from app.routers.documents import delete_document, get_document_file, upload_document
from app.services.storage import StorageService


@pytest.fixture
def local_storage(tmp_path: Path) -> StorageService:
    return StorageService(backend="local", local_dir=str(tmp_path))


def _user():
    user = MagicMock()
    user.id = "u1"
    user.workspace_id = "w1"
    return user


def _db_with_document(document):
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=document)
    db.delete = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_upload_stores_original_bytes(local_storage: StorageService, tmp_path: Path):
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    file = UploadFile(filename="memo.txt", file=BytesIO(b"keep me"))

    with patch("app.routers.documents.upload_limiter.check_rate_limit", new_callable=AsyncMock) as mock_rl, \
         patch("app.routers.documents.process_document_task"), \
         patch("app.routers.documents.storage_service", local_storage):
        mock_rl.return_value = (True, {})
        result = await upload_document(
            request=MagicMock(),
            background_tasks=BackgroundTasks(),
            file=file,
            documentId="doc-keep",
            workspaceId="w1",
            db=db,
            user=_user(),
            tenant=TenantContext(user_id="u1", workspace_id="w1"),
        )

    added = db.add.call_args[0][0]
    assert added.s3_key
    assert (tmp_path / added.s3_key).read_bytes() == b"keep me"
    assert result.id == "doc-keep"


@pytest.mark.asyncio
async def test_get_document_file_returns_stored_bytes(local_storage: StorageService):
    key = await local_storage.upload_document(
        file=BytesIO(b"pdf-bytes"),
        filename="a.pdf",
        content_type="application/pdf",
        document_id="doc-file",
    )
    document = MagicMock()
    document.id = "doc-file"
    document.name = "a.pdf"
    document.file_type = "application/pdf"
    document.s3_key = key
    document.user_id = "u1"
    document.workspace_id = "w1"

    with patch("app.routers.documents.storage_service", local_storage), \
         patch("app.routers.documents._user_can_access_document", new_callable=AsyncMock) as access:
        access.return_value = True
        response = await get_document_file(
            "doc-file",
            db=_db_with_document(document),
            tenant=TenantContext(user_id="u1", workspace_id="w1"),
        )

    assert response.body == b"pdf-bytes"
    assert "application/pdf" in response.media_type


@pytest.mark.asyncio
async def test_get_document_file_denies_other_user():
    document = MagicMock()
    document.id = "doc-x"
    document.s3_key = "doc-x/a.pdf"
    db = _db_with_document(document)
    with patch("app.routers.documents._user_can_access_document", new_callable=AsyncMock) as access:
        access.return_value = False
        with pytest.raises(HTTPException) as exc:
            await get_document_file(
                "doc-x",
                db=db,
                tenant=TenantContext(user_id="other", workspace_id="w2"),
            )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_document_removes_stored_file(local_storage: StorageService):
    key = await local_storage.upload_document(
        file=BytesIO(b"bye"),
        filename="bye.txt",
        content_type="text/plain",
        document_id="doc-del",
    )
    document = MagicMock()
    document.id = "doc-del"
    document.s3_key = key
    document.user_id = "u1"
    document.workspace_id = "w1"

    with patch("app.routers.documents.storage_service", local_storage), \
         patch("app.routers.documents._user_can_access_document", new_callable=AsyncMock) as access, \
         patch("app.routers.documents.cache_service") as cache:
        access.return_value = True
        cache.delete = AsyncMock()
        await delete_document(
            "doc-del",
            db=_db_with_document(document),
            tenant=TenantContext(user_id="u1", workspace_id="w1"),
        )

    with pytest.raises(FileNotFoundError):
        await local_storage.download_document(key)
