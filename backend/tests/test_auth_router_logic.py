import pytest
from unittest.mock import AsyncMock, MagicMock

from app.routers.auth import register, login, update_me, refresh_token, RegisterRequest, LoginRequest, UpdateMeRequest


@pytest.mark.asyncio
async def test_register_success(monkeypatch):
    db = AsyncMock()
    user = MagicMock()
    user.id = "u1"
    user.email = "a@b.com"
    user.name = "A"
    user.default_workspace_id = "w1"
    user.is_active = True

    monkeypatch.setattr("app.routers.auth.get_user_by_email", AsyncMock(return_value=None))
    monkeypatch.setattr("app.routers.auth.create_user", AsyncMock(return_value=user))

    http_request = MagicMock()
    http_request.client = MagicMock(host="127.0.0.1")
    result = await register(
        RegisterRequest(email="a@b.com", password="password123"),
        http_request,
        db=db,
    )
    assert result.user.email == "a@b.com"


@pytest.mark.asyncio
async def test_login_invalid_password(monkeypatch):
    db = AsyncMock()
    user = MagicMock()
    user.password_hash = "hashed"
    user.is_active = True
    monkeypatch.setattr("app.routers.auth.get_user_by_email", AsyncMock(return_value=user))
    monkeypatch.setattr("app.routers.auth.verify_password", lambda a, b: False)
    with pytest.raises(Exception):
        await login(LoginRequest(email="a@b.com", password="bad"), db=db)


@pytest.mark.asyncio
async def test_register_existing_user(monkeypatch):
    db = AsyncMock()
    existing = MagicMock()
    monkeypatch.setattr("app.routers.auth.get_user_by_email", AsyncMock(return_value=existing))
    with pytest.raises(Exception):
        http_request = MagicMock()
        http_request.client = MagicMock(host="127.0.0.1")
        await register(
            RegisterRequest(email="a@b.com", password="password123"),
            http_request,
            db=db,
        )


@pytest.mark.asyncio
async def test_login_success(monkeypatch):
    db = AsyncMock()
    user = MagicMock()
    user.id = "u1"
    user.email = "a@b.com"
    user.password_hash = "hashed"
    user.default_workspace_id = "w1"
    user.name = "A"
    user.is_active = True
    monkeypatch.setattr("app.routers.auth.get_user_by_email", AsyncMock(return_value=user))
    monkeypatch.setattr("app.routers.auth.verify_password", lambda a, b: True)
    monkeypatch.setattr("app.routers.auth.update_last_login", AsyncMock())
    result = await login(LoginRequest(email="a@b.com", password="p"), db=db)
    assert result.user.email == "a@b.com"


@pytest.mark.asyncio
async def test_update_me_workspace(monkeypatch):
    db = AsyncMock()
    user = MagicMock()
    user.id = "u1"
    user.email = "a@b.com"
    user.name = "A"
    user.workspace_id = "w1"
    user.is_active = True

    updated = MagicMock()
    updated.id = "u1"
    updated.email = "a@b.com"
    updated.name = "A"
    updated.default_workspace_id = "w2"
    updated.is_active = True

    monkeypatch.setattr("app.routers.auth.update_user_default_workspace", AsyncMock(return_value=updated))
    result = await update_me(UpdateMeRequest(workspace_id="w2"), db=db, user=user)
    assert result.workspace_id == "w2"


@pytest.mark.asyncio
async def test_refresh_token():
    from app.core.auth import UserResponse
    user = UserResponse(
        id="u1",
        email="a@b.com",
        name=None,
        workspace_id="w1",
        is_active=True,
    )
    result = await refresh_token(user=user)
    assert result.access_token
