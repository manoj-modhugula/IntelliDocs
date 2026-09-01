import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.documents import process_document_task
from app.models import Document, DocumentStatus


@pytest.mark.asyncio
async def test_process_document_task_success():
    mock_db = AsyncMock()
    mock_db.get.return_value = MagicMock(spec=Document)

    class DummySession:
        async def __aenter__(self):
            return mock_db
        async def __aexit__(self, exc_type, exc, tb):
            return False

    with patch("app.core.database.async_session", return_value=DummySession()):
        with patch("app.routers.documents.ingestion_service.process_document", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = 1
            await process_document_task("d1", b"data", "text/plain")


@pytest.mark.asyncio
async def test_process_document_task_timeout():
    mock_db = AsyncMock()
    doc = MagicMock(spec=Document)
    doc.status = DocumentStatus.PROCESSING.value
    mock_db.get.return_value = doc
    mock_db.commit = AsyncMock()

    class DummySession:
        async def __aenter__(self):
            return mock_db
        async def __aexit__(self, exc_type, exc, tb):
            return False

    with patch("app.core.database.async_session", return_value=DummySession()):
        with patch("asyncio.wait_for", side_effect=TimeoutError):
            await process_document_task("d1", b"data", "text/plain")
            assert doc.status == DocumentStatus.ERROR.value


@pytest.mark.asyncio
async def test_process_document_task_exception_sets_error():
    mock_db = AsyncMock()
    doc = MagicMock(spec=Document)
    doc.status = DocumentStatus.PROCESSING.value
    mock_db.get.return_value = doc
    mock_db.commit = AsyncMock()

    class DummySession:
        async def __aenter__(self):
            return mock_db
        async def __aexit__(self, exc_type, exc, tb):
            return False

    with patch("app.core.database.async_session", return_value=DummySession()):
        with patch("app.routers.documents.ingestion_service.process_document", new_callable=AsyncMock) as mock_proc:
            mock_proc.side_effect = Exception("boom")
            await process_document_task("d1", b"data", "text/plain")
            assert doc.status == DocumentStatus.ERROR.value


@pytest.mark.asyncio
async def test_process_document_task_timeout_commit_error():
    mock_db = AsyncMock()
    doc = MagicMock(spec=Document)
    mock_db.get.return_value = doc
    mock_db.commit = AsyncMock(side_effect=Exception("commit fail"))

    class DummySession:
        async def __aenter__(self):
            return mock_db
        async def __aexit__(self, exc_type, exc, tb):
            return False

    with patch("app.core.database.async_session", return_value=DummySession()):
        with patch("asyncio.wait_for", side_effect=TimeoutError):
            await process_document_task("d1", b"data", "text/plain")


@pytest.mark.asyncio
async def test_process_document_task_exception_inner_error():
    mock_db = AsyncMock()
    mock_db.get.side_effect = Exception("db fail")

    class DummySession:
        async def __aenter__(self):
            return mock_db
        async def __aexit__(self, exc_type, exc, tb):
            return False

    with patch("app.core.database.async_session", return_value=DummySession()):
        with patch("app.routers.documents.ingestion_service.process_document", new_callable=AsyncMock) as mock_proc:
            mock_proc.side_effect = Exception("boom")
            await process_document_task("d1", b"data", "text/plain")
