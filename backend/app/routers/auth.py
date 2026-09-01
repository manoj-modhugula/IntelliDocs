"""
Authentication router with PostgreSQL persistence.
"""

import uuid
import time
from typing import Optional, Dict
from collections import defaultdict
from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import (
    create_access_token,
    verify_password,
    require_auth,
    get_user_by_email,
    create_user,
    update_last_login,
    update_user_default_workspace,
    UserResponse,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.models import Workspace

router = APIRouter()

# Strict rate limiting for auth endpoints (brute-force protection)
# Login: 5 attempts per minute per IP/email
# Register: 3 attempts per minute per IP
_auth_rate_limits: Dict[str, list] = defaultdict(list)
_auth_rate_lock: Dict[str, float] = {}  # Simple lock for cleanup

async def _check_auth_rate_limit(key: str, max_attempts: int, window_seconds: int = 60) -> bool:
    """Check rate limit for auth endpoints with exponential backoff."""
    now = time.time()
    window_start = now - window_seconds
    
    # Clean old entries
    _auth_rate_limits[key] = [ts for ts in _auth_rate_limits[key] if ts > window_start]
    
    if len(_auth_rate_limits[key]) >= max_attempts:
        return False
    
    _auth_rate_limits[key].append(now)
    return True

async def _get_rate_limit_key(request: Request, email: Optional[str] = None) -> str:
    """Generate rate limit key from IP and email."""
    ip = request.client.host if request.client else "unknown"
    if email:
        return f"auth:{ip}:{email.lower()}"
    return f"auth:{ip}"


class LoginRequest(BaseModel):
    """Login request body."""
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Registration request body."""
    email: EmailStr
    password: str
    name: Optional[str] = None


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    user: Optional[UserResponse] = None


class UpdateMeRequest(BaseModel):
    """Update current user (e.g. default workspace)."""
    workspace_id: Optional[str] = None


@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user.
    
    Creates a new user account in PostgreSQL and returns an access token.
    
    Rate limited: 3 attempts per minute per IP.
    """
    # Strict rate limiting (brute-force/spam protection)
    rate_key = await _get_rate_limit_key(http_request)
    if not await _check_auth_rate_limit(rate_key, max_attempts=3, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please wait a moment.",
            headers={"Retry-After": "60"},
        )
    
    # Check if email already exists
    existing_user = await get_user_by_email(db, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user in database
    user = await create_user(
        db,
        email=request.email,
        password=request.password,
        name=request.name,
    )

    # Create default workspace for the user (same name as workspaces router so list_workspaces won't create a duplicate)
    default_workspace = Workspace(
        id=str(uuid.uuid4()),
        name="My workspace",
        description=None,
        user_id=user.id,
    )
    db.add(default_workspace)
    await db.flush()
    user.default_workspace_id = default_workspace.id
    await db.commit()
    await db.refresh(user)

    # Generate token
    access_token = create_access_token(
        data={
            "user_id": user.id,
            "email": user.email,
            "workspace_id": user.default_workspace_id,
        }
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            workspace_id=user.default_workspace_id,
            is_active=user.is_active,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email and password.
    
    Validates credentials against PostgreSQL and returns an access token.
    
    Rate limited: 5 attempts per minute per IP, 3 per email.
    """
    # Strict rate limiting (brute-force protection)
    ip_key = await _get_rate_limit_key(http_request)
    email_key = await _get_rate_limit_key(http_request, request.email)
    
    if not await _check_auth_rate_limit(ip_key, max_attempts=5, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait a moment.",
            headers={"Retry-After": "60"},
        )
    
    if not await _check_auth_rate_limit(email_key, max_attempts=3, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts for this email. Please wait or reset your password.",
            headers={"Retry-After": "60"},
        )
    
    user = await get_user_by_email(db, request.email)
    
    if not user or not verify_password(request.password, user.password_hash):
        # Log failed attempt (for monitoring)
        import logging
        logging.getLogger(__name__).warning(f"Failed login attempt for: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    
    # Update last login
    await update_last_login(db, user.id)
    
    # Generate token
    access_token = create_access_token(
        data={
            "user_id": user.id,
            "email": user.email,
            "workspace_id": user.default_workspace_id,
        }
    )
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            workspace_id=user.default_workspace_id,
            is_active=user.is_active,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: UserResponse = Depends(require_auth)):
    """
    Get current user information.
    
    Requires authentication. Validates user exists in database.
    """
    return user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    request: UpdateMeRequest,
    db: AsyncSession = Depends(get_db),
    user: UserResponse = Depends(require_auth),
):
    """
    Update current user (e.g. default workspace).
    """
    if request.workspace_id is not None:
        # Verify the user owns this workspace before setting it as default
        workspace = await db.get(Workspace, request.workspace_id)
        if not workspace or workspace.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this workspace",
            )
        updated = await update_user_default_workspace(db, user.id, request.workspace_id)
        if updated:
            return UserResponse(
                id=updated.id,
                email=updated.email,
                name=updated.name,
                workspace_id=updated.default_workspace_id,
                is_active=updated.is_active,
            )
    return user


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(user: UserResponse = Depends(require_auth)):
    """
    Refresh the access token.
    
    Returns a new token with extended expiration.
    """
    access_token = create_access_token(
        data={
            "user_id": user.id,
            "email": user.email,
            "workspace_id": user.workspace_id,
        }
    )
    
    return TokenResponse(
        access_token=access_token,
        user=user,
    )
