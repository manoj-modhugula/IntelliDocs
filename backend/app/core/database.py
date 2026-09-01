"""
Database configuration and connection management.
Uses SQLAlchemy with asyncpg for async PostgreSQL connections.
"""

import os
import re
import ssl
from urllib.parse import parse_qs, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.core.config import settings


def get_clean_database_url(url: str) -> str:
    """
    Clean database URL for asyncpg compatibility.
    Removes sslmode and channel_binding query parameters.
    """
    # Remove specific query params that asyncpg doesn't support
    url = re.sub(r'[?&]sslmode=[^&]*', '', url)
    url = re.sub(r'[?&]channel_binding=[^&]*', '', url)
    # Clean up leftover ? or &
    url = re.sub(r'\?&', '?', url)
    url = re.sub(r'\?$', '', url)
    return url


# Convert postgres:// to postgresql+asyncpg:// and strip query params (asyncpg rejects sslmode= etc.)
_raw_url = settings.DATABASE_URL or ""
_raw_parsed = urlparse(_raw_url)
_raw_query = parse_qs(_raw_parsed.query)
_sslmode = (_raw_query.get("sslmode", [""])[0] or "").lower()
_use_ssl = _sslmode in {"require", "verify-full", "verify-ca"}
if _raw_url.startswith("postgres://"):
    database_url = _raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgresql://"):
    database_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    database_url = _raw_url
# Strip query string so asyncpg never receives sslmode or other unsupported params
if database_url:
    parsed = urlparse(database_url)
    database_url = urlunparse(parsed._replace(query="", fragment="")).rstrip("?") or database_url

# Create async engine with SSL settings for asyncpg (only if sslmode requires it)
connect_args = {}
if _use_ssl:
    ssl_context = ssl.create_default_context()
    insecure_ssl = settings.DB_SSL_INSECURE or os.getenv("ENVIRONMENT") != "production"
    if insecure_ssl:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    connect_args = {"ssl": ssl_context}

engine = create_async_engine(
    database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    connect_args=connect_args,
)

# Session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


async def init_db():
    """Initialize database - create tables and extensions."""
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        
        # Create tables
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency for getting database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
