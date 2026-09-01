import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ingestion import IngestionService
from app.models import Document, DocumentStatus


@pytest.mark.asyncio
async def test_process_document_text():
    ingestion = IngestionService()
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    # _fetch_existing_embeddings calls db.execute(...).fetchall()
    exec_result = MagicMock()
    exec_result.fetchall.return_value = []
    mock_db.execute = AsyncMock(return_value=exec_result)

    doc = MagicMock(spec=Document)
    doc.id = "doc1"
    doc.status = DocumentStatus.PENDING.value
    doc.workspace_id = "w1"
    mock_db.get.return_value = doc

    with patch("app.services.ingestion.embedding_service.embed_texts", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [[0.0] * 1024]
        with patch("app.services.ingestion.settings") as mock_settings:
            mock_settings.ENABLE_CHUNK_PRUNING = False
            mock_settings.ENABLE_CHUNK_DEDUP = False
            mock_settings.ENABLE_SELECTIVE_EMBEDDING = False
            count = await ingestion.process_document(
                db=mock_db,
                document_id="doc1",
                file_bytes=b"hello world",
                file_type="text/plain",
            )
        assert count >= 1
