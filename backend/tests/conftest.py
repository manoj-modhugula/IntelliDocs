"""
Pytest configuration and fixtures.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.core.database import get_db


# Test database URL (in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_client():
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_db():
    """Create mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    with patch("app.services.embedding.embedding_service") as mock:
        mock.embed_text = AsyncMock(return_value=[0.1] * 1024)
        yield mock


@pytest.fixture
def mock_llm_service():
    """Mock LLM service."""
    with patch("app.services.llm.llm_service") as mock:
        mock.generate = AsyncMock(return_value="This is a test response.")
        mock.generate_stream = AsyncMock(return_value=iter(["Test", " response"]))
        mock.route_query = AsyncMock(return_value="HYBRID")
        yield mock


@pytest.fixture
def mock_cache_service():
    """Mock cache service."""
    with patch("app.services.cache.cache_service") as mock:
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.get_semantic_cache = AsyncMock(return_value=None)
        mock.set_semantic_cache = AsyncMock(return_value=True)
        yield mock


@pytest.fixture
def sample_document():
    """Sample document data for testing."""
    return {
        "id": "test-doc-1",
        "name": "test.pdf",
        "type": "application/pdf",
        "size": 1024,
        "status": "ready",
    }


@pytest.fixture
def sample_chunk():
    """Sample chunk data for testing."""
    return {
        "id": "chunk-1",
        "document_id": "test-doc-1",
        "content": "This is a test chunk with some content for testing.",
        "page_number": 1,
        "chunk_index": 0,
    }


@pytest.fixture
def sample_workspace():
    """Sample workspace data for testing."""
    return {
        "id": "workspace-1",
        "name": "Test Workspace",
        "description": "A test workspace",
    }


@pytest.fixture
def mock_auth_headers():
    """Mock authentication headers for testing."""
    return {
        "Authorization": "Bearer test-token",
        "Content-Type": "application/json",
    }
