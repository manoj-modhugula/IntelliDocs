"""JWT authentication with PostgreSQL-backed users."""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__type="id",
    argon2__rounds=2,
    argon2__memory_cost=65536,
    argon2__parallelism=4
)

# JWT configuration - use config; warn in production if default
SECRET_KEY = settings.JWT_SECRET_KEY
if os.getenv("ENVIRONMENT") == "production" and ("change-in-production" in SECRET_KEY or len(SECRET_KEY) < 32):
    import warnings
    warnings.warn("JWT_SECRET_KEY should be set to a secure random value in production", UserWarning)
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_EXPIRE_MINUTES

# Security scheme
security = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    user_id: str
    email: Optional[str] = None
    workspace_id: Optional[str] = None
    exp: Optional[datetime] = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    workspace_id: Optional[str] = None
    is_active: bool = True


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = _utcnow()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(f"Created token for user: {data.get('user_id')}")
    
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        user_id: str = payload.get("user_id")
        if user_id is None:
            return None
        
        return TokenData(
            user_id=user_id,
            email=payload.get("email"),
            workspace_id=payload.get("workspace_id"),
            exp=payload.get("exp"),
        )
        
    except JWTError as e:
        logger.warning(f"Token decode failed: {e}")
        return None


async def get_user_by_email(db: AsyncSession, email: str):
    from app.models.user import User
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str):
    from app.models.user import User
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str, name: Optional[str] = None):
    from app.models.user import User
    from app.core.utils import utc_now_naive

    now = utc_now_naive()
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=hash_password(password),
        name=name,
        is_active=True,
        is_verified=False,
        created_at=now,
        updated_at=now,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


async def update_last_login(db: AsyncSession, user_id: str):
    from app.models.user import User
    from app.core.utils import utc_now_naive
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.last_login_at = utc_now_naive()
        await db.commit()


async def update_user_default_workspace(db: AsyncSession, user_id: str, workspace_id: Optional[str]):
    from app.models.user import User
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None
    user.default_workspace_id = workspace_id
    await db.commit()
    await db.refresh(user)
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[UserResponse]:
    if credentials is None:
        return None
    
    token_data = decode_token(credentials.credentials)
    if token_data is None:
        return None
    
    # Fetch user from database to verify they still exist and are active
    user = await get_user_by_id(db, token_data.user_id)
    if user is None or not user.is_active:
        return None
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        workspace_id=user.default_workspace_id,
        is_active=user.is_active,
    )


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = decode_token(credentials.credentials)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify user exists in database
    user = await get_user_by_id(db, token_data.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        workspace_id=user.default_workspace_id,
        is_active=user.is_active,
    )
