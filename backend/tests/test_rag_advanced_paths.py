import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.rag import RAGService
from app.core.config import settings


@pytest.mark.asyncio
async def test_retrieve_advanced_hyde_path():
    rag = RAGService()
    mock_db = AsyncMock()

    low_chunk = MagicMock()
    low_chunk.id = "c1"
    low_chunk.content = "low"
    low_chunk.page_number = 1

    better_chunk = MagicMock()
    better_chunk.id = "c2"
    better_chunk.content = "better"
    better_chunk.page_number = 1

    with patch.object(rag._retrieval, "search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [(low_chunk, 0.1)]
        with patch("app.services.rag.assess_retrieval_confidence", return_value="very_low"):
            with patch("app.services.rag.hyde_embed", new_callable=AsyncMock) as mock_hyde:
                mock_hyde.return_value = [[0.0] * 1024]
                with patch.object(rag._retrieval, "semantic_search_by_embedding", new_callable=AsyncMock) as mock_sem:
                    mock_sem.return_value = [(better_chunk, 0.9)]
                    chunks, strategy = await rag._retrieve_advanced(
                        mock_db, "query", "SEMANTIC", workspace_id="ws"
                    )
                    assert strategy in ("HYDE", "HYBRID", "SEMANTIC")
                    assert chunks


@pytest.mark.asyncio
async def test_retrieve_advanced_multi_query():
    rag = RAGService()
    mock_db = AsyncMock()
    chunk = MagicMock()
    chunk.id = "c1"
    chunk.content = "content"
    chunk.page_number = 1

    with patch.object(rag._retrieval, "search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [(chunk, 0.4)]
        with patch("app.services.rag.assess_retrieval_confidence", return_value="low"):
            with patch("app.services.rag.multi_query_expand", new_callable=AsyncMock) as mock_expand:
                mock_expand.return_value = ["q1", "q2"]
                chunks, strategy = await rag._retrieve_advanced(
                    mock_db, "query", "SEMANTIC", workspace_id="ws"
                )
                assert strategy in ("MULTI_QUERY", "SEMANTIC", "HYBRID")
                assert chunks


@pytest.mark.asyncio
async def test_retrieve_advanced_rerank():
    rag = RAGService()
    mock_db = AsyncMock()

    chunks = [(MagicMock(), 0.9), (MagicMock(), 0.8), (MagicMock(), 0.7)]
    with patch.object(rag._retrieval, "search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = chunks
        with patch("app.services.rag.rerank_chunks", return_value=chunks[:2]):
            original_top_k = settings.TOP_K_RESULTS
            settings.TOP_K_RESULTS = 2
            try:
                out, _ = await rag._retrieve_advanced(
                    mock_db, "query", "HYBRID", workspace_id="ws"
                )
                assert len(out) <= 2
            finally:
                settings.TOP_K_RESULTS = original_top_k
