import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.documents import (
    get_document,
    get_document_status,
    list_documents,
    delete_document,
    _user_can_access_document,
    _user_can_access_workspace,
)
from app.core.multitenancy import TenantContext
from app.models import Document


def _mock_document(doc_id="d1", workspace_id="w1", status="ready", user_id=None):
    doc = MagicMock(spec=Document)
    doc.id = doc_id
    doc.name = "doc.pdf"
    doc.file_type = "pdf"
    doc.file_size = 123
    doc.status = status
    doc.workspace_id = workspace_id
    doc.user_id = user_id
    doc.chunk_count = 5
    doc.error_message = None
    doc.created_at = None
    return doc


@pytest.mark.asyncio
async def test_get_document_allows_access():
    db = AsyncMock()
    doc = _mock_document(user_id=None)  # allow access when doc has no user_id and tenant workspace matches
    db.get.return_value = doc
    tenant = TenantContext(user_id="u1", workspace_id="w1")

    result = await get_document("d1", db=db, tenant=tenant)
    assert result.id == "d1"


@pytest.mark.asyncio
async def test_get_document_status():
    db = AsyncMock()
    doc = _mock_document(status="ready", user_id=None)
    db.get.return_value = doc
    tenant = TenantContext(user_id="u1", workspace_id="w1")

    result = await get_document_status("d1", db=db, tenant=tenant)
    assert result.status == "ready"


@pytest.mark.asyncio
async def test_list_documents_with_workspace_filter():
    db = AsyncMock()
    doc = _mock_document()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [doc]
    db.execute.return_value = result

    tenant = TenantContext(user_id="u1", workspace_id="w1")
    items = await list_documents(workspaceId="w1", db=db, tenant=tenant)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_delete_document():
    db = AsyncMock()
    doc = _mock_document(user_id=None)
    db.get.return_value = doc
    tenant = TenantContext(user_id="u1", workspace_id="w1")

    result = await delete_document("d1", db=db, tenant=tenant)
    assert result["status"] == "deleted"


@pytest.mark.asyncio
async def test_get_document_access_denied():
    db = AsyncMock()
    doc = _mock_document(workspace_id="w2")
    db.get.return_value = doc
    tenant = TenantContext(user_id="u1", workspace_id="w1")

    with pytest.raises(Exception):
        await get_document("d1", db=db, tenant=tenant)


@pytest.mark.asyncio
async def test_get_document_not_found():
    db = AsyncMock()
    db.get.return_value = None
    tenant = TenantContext(user_id="u1", workspace_id="w1")
    with pytest.raises(Exception):
        await get_document("d1", db=db, tenant=tenant)


@pytest.mark.asyncio
async def test_list_documents_anonymous():
    from app.services import cache
    db = AsyncMock()
    doc = _mock_document(workspace_id=None)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [doc]
    db.execute = AsyncMock(return_value=result)
    tenant = TenantContext(user_id=None, workspace_id=None)
    with patch.object(cache.cache_service, "get", new_callable=AsyncMock, return_value=None):
        with patch.object(cache.cache_service, "set", new_callable=AsyncMock):
            items = await list_documents(workspaceId=None, db=db, tenant=tenant)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_list_documents_tenant_default():
    db = AsyncMock()
    doc = _mock_document(workspace_id="w1")
    result = MagicMock()
    result.scalars.return_value.all.return_value = [doc]
    db.execute.return_value = result
    tenant = TenantContext(user_id="u1", workspace_id="w1")
    items = await list_documents(workspaceId=None, db=db, tenant=tenant)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_delete_document_not_found():
    db = AsyncMock()
    db.get.return_value = None
    tenant = TenantContext(user_id="u1", workspace_id="w1")
    with pytest.raises(Exception):
        await delete_document("d1", db=db, tenant=tenant)


@pytest.mark.asyncio
async def test_user_can_access_document_owned_workspace():
    db = AsyncMock()
    workspace = MagicMock()
    workspace.user_id = "u1"
    db.get.return_value = workspace
    doc = _mock_document(workspace_id="w2", user_id="u1")
    tenant = TenantContext(user_id="u1", workspace_id="w2")
    allowed = await _user_can_access_document(db, tenant, doc)
    assert allowed is True


@pytest.mark.asyncio
async def test_user_can_access_workspace_owned():
    db = AsyncMock()
    workspace = MagicMock()
    workspace.user_id = "u1"
    db.get.return_value = workspace
    tenant = TenantContext(user_id="u1", workspace_id="w2")
    allowed = await _user_can_access_workspace(db, tenant, "w3")
    assert allowed is True


@pytest.mark.asyncio
async def test_user_can_access_document_no_user():
    db = AsyncMock()
    doc = _mock_document(workspace_id="w1")
    tenant = TenantContext(user_id=None, workspace_id=None)
    allowed = await _user_can_access_document(db, tenant, doc)
    assert allowed is False


@pytest.mark.asyncio
async def test_user_can_access_workspace_no_user():
    db = AsyncMock()
    tenant = TenantContext(user_id=None, workspace_id=None)
    allowed = await _user_can_access_workspace(db, tenant, "w1")
    assert allowed is False


@pytest.mark.asyncio
async def test_get_document_status_access_denied():
    db = AsyncMock()
    doc = _mock_document(workspace_id="w2")
    db.get.return_value = doc
    tenant = TenantContext(user_id="u1", workspace_id="w1")
    with pytest.raises(Exception):
        await get_document_status("d1", db=db, tenant=tenant)


@pytest.mark.asyncio
async def test_list_documents_workspace_access_denied():
    db = AsyncMock()
    tenant = TenantContext(user_id="u1", workspace_id="w1")
    with pytest.raises(Exception):
        await list_documents(workspaceId="w2", db=db, tenant=tenant)


@pytest.mark.asyncio
async def test_delete_document_access_denied():
    db = AsyncMock()
    doc = _mock_document(workspace_id="w2")
    db.get.return_value = doc
    tenant = TenantContext(user_id="u1", workspace_id="w1")
    with pytest.raises(Exception):
        await delete_document("d1", db=db, tenant=tenant)
