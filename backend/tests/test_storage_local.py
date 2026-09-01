"""Local disk storage: upload, download, delete without S3."""

from io import BytesIO
from pathlib import Path

import pytest

from app.services.storage import StorageService


@pytest.fixture
def local_dir(tmp_path: Path) -> Path:
    return tmp_path / "documents"


@pytest.fixture
def local_storage(local_dir: Path) -> StorageService:
    return StorageService(backend="local", local_dir=str(local_dir))


@pytest.mark.asyncio
async def test_local_upload_writes_bytes_and_returns_key(local_storage: StorageService, local_dir: Path):
    key = await local_storage.upload_document(
        file=BytesIO(b"hello pdf"),
        filename="report.pdf",
        content_type="application/pdf",
        document_id="doc-1",
    )
    assert "doc-1" in key
    assert "report.pdf" in key
    stored = local_dir / "doc-1" / "report.pdf"
    assert stored.read_bytes() == b"hello pdf"


@pytest.mark.asyncio
async def test_local_download_returns_uploaded_bytes(local_storage: StorageService):
    key = await local_storage.upload_document(
        file=BytesIO(b"abc"),
        filename="notes.txt",
        content_type="text/plain",
        document_id="doc-2",
    )
    data = await local_storage.download_document(key)
    assert data == b"abc"


@pytest.mark.asyncio
async def test_local_delete_removes_file(local_storage: StorageService, local_dir: Path):
    key = await local_storage.upload_document(
        file=BytesIO(b"gone"),
        filename="gone.txt",
        content_type="text/plain",
        document_id="doc-3",
    )
    assert await local_storage.delete_document(key) is True
    assert not (local_dir / "doc-3" / "gone.txt").exists()
