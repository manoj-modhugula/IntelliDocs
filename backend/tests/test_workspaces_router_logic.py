import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.auth import UserResponse
from app.routers.workspaces import (
    create_workspace,
    list_workspaces,
    get_workspace,
    update_workspace,
    delete_workspace,
    WorkspaceCreate,
)
from app.models import Workspace


def _mock_user(user_id="u1"):
    return UserResponse(
        id=user_id,
        email="test@test.com",
        name="Test User",
        workspace_id=None,
        is_active=True,
    )


def _mock_workspace(ws_id="w1", user_id="u1"):
    ws = MagicMock(spec=Workspace)
    ws.id = ws_id
    ws.name = "Workspace"
    ws.description = "Desc"
    ws.user_id = user_id
    ws.created_at = None
    ws.updated_at = None
    return ws


@pytest.mark.asyncio
async def test_create_workspace():
    db = AsyncMock()
    db.refresh = AsyncMock()
    db.commit = AsyncMock()

    user = _mock_user()
    req = WorkspaceCreate(name="Test", description="Desc")
    result = await create_workspace(req, db=db, user=user)
    assert result.name == "Test"


@pytest.mark.asyncio
async def test_list_workspaces():
    db = AsyncMock()
    ws = _mock_workspace()
    result = MagicMock()
    result.all.return_value = [(ws, 3)]
    db.execute.return_value = result
    db.get = AsyncMock(return_value=None)  # user_row for default_workspace_id
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    user = _mock_user()
    items = await list_workspaces(db=db, user=user)
    # "My workspace" is always created if missing, so we get at least 2 (My workspace + existing)
    assert len(items) >= 1
    assert items[0].name == "My workspace"


@pytest.mark.asyncio
async def test_get_workspace():
    db = AsyncMock()
    ws = _mock_workspace()
    db.get.return_value = ws
    result = MagicMock()
    result.scalar.return_value = 2
    db.execute.return_value = result

    user = _mock_user()
    item = await get_workspace("w1", db=db, user=user)
    assert item.id == "w1"


@pytest.mark.asyncio
async def test_update_workspace():
    db = AsyncMock()
    ws = _mock_workspace()
    db.get.return_value = ws
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    # update_workspace calls db.execute(count_query) and result.scalar(); must return int
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    db.execute = AsyncMock(return_value=count_result)

    user = _mock_user()
    req = WorkspaceCreate(name="New", description="New desc")
    item = await update_workspace("w1", req, db=db, user=user)
    assert item.name == "New"


@pytest.mark.asyncio
async def test_delete_workspace():
    db = AsyncMock()
    ws = _mock_workspace()
    db.get.return_value = ws
    db.commit = AsyncMock()

    user = _mock_user()
    result = await delete_workspace("w1", db=db, user=user)
    assert result["status"] == "deleted"
