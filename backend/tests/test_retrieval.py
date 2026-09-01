"""
Tests for retrieval service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.retrieval import RetrievalService, create_retrieval_service


class TestRetrievalService:
    """Tests for RetrievalService."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.retrieval = RetrievalService()
    
    @pytest.mark.asyncio
    async def test_search_routes_to_semantic(self):
        """Test search routes to semantic search for SEMANTIC strategy."""
        mock_chunk = MagicMock()
        mock_chunk.id = "c1"
        with patch.object(self.retrieval, 'semantic_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [(mock_chunk, 0.9)]  # Non-empty to avoid fallback
            mock_db = AsyncMock(spec=AsyncSession)
            
            # Disable multi-granularity to test individual routing
            await self.retrieval.search(
                mock_db, "test query", strategy="SEMANTIC", top_k=5,
                use_multi_granularity=False
            )
            
            mock_search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_routes_to_bm25(self):
        """Test search routes to BM25 for KEYWORD strategy."""
        mock_chunk = MagicMock()
        mock_chunk.id = "c1"
        with patch.object(self.retrieval, 'bm25_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [(mock_chunk, 0.8)]  # Non-empty to avoid fallback
            mock_db = AsyncMock(spec=AsyncSession)
            
            # Disable multi-granularity to test individual routing
            await self.retrieval.search(
                mock_db, "test query", strategy="KEYWORD", top_k=5,
                use_multi_granularity=False
            )
            
            mock_search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_routes_to_hybrid(self):
        """Test search routes to hybrid for HYBRID strategy."""
        with patch.object(self.retrieval, 'hybrid_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            mock_db = AsyncMock(spec=AsyncSession)
            
            # Disable multi-granularity to test individual routing
            await self.retrieval.search(
                mock_db, "test query", strategy="HYBRID", top_k=5,
                use_multi_granularity=False
            )
            
            mock_search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_defaults_to_hybrid(self):
        """Test search defaults to hybrid strategy when multi-granularity disabled."""
        with patch.object(self.retrieval, 'hybrid_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            mock_db = AsyncMock(spec=AsyncSession)
            
            # Disable multi-granularity to test default behavior
            await self.retrieval.search(
                mock_db, "test query", top_k=5, use_multi_granularity=False
            )
            
            mock_search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_hybrid_search_combines_results(self):
        """Test hybrid search combines semantic and BM25 results."""
        mock_chunk1 = MagicMock()
        mock_chunk1.id = "chunk-1"
        mock_chunk2 = MagicMock()
        mock_chunk2.id = "chunk-2"
        
        with patch.object(self.retrieval, 'semantic_search') as mock_semantic:
            with patch.object(self.retrieval, 'bm25_search') as mock_bm25:
                mock_semantic.return_value = [(mock_chunk1, 0.9)]
                mock_bm25.return_value = [(mock_chunk2, 0.8)]
                mock_db = AsyncMock(spec=AsyncSession)
                
                results = await self.retrieval.hybrid_search(
                    mock_db, "test query", top_k=5
                )
                
                # Both chunks should be in results
                chunk_ids = [chunk.id for chunk, score in results]
                assert "chunk-1" in chunk_ids
                assert "chunk-2" in chunk_ids
    
    @pytest.mark.asyncio
    async def test_workspace_filter_passed(self):
        """Test workspace filter is passed to search methods."""
        mock_chunk = MagicMock()
        mock_chunk.id = "c1"
        with patch.object(self.retrieval, 'semantic_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [(mock_chunk, 0.9)]  # Non-empty to avoid fallback
            mock_db = AsyncMock(spec=AsyncSession)
            
            # Disable multi-granularity to test individual routing
            await self.retrieval.search(
                mock_db, "test query",
                strategy="SEMANTIC",
                workspace_id="ws-123",
                use_multi_granularity=False
            )
            
            call_args = mock_search.call_args
            assert call_args.kwargs.get('workspace_id') == "ws-123" or \
                   (len(call_args.args) >= 4 and call_args.args[3] == "ws-123")


class TestRetrievalFallbacks:
    """Test retrieval fallback logic (empty results)."""

    @pytest.mark.asyncio
    async def test_keyword_empty_fallback_to_semantic(self):
        """When KEYWORD returns empty, fallback to SEMANTIC."""
        service = RetrievalService()
        service.bm25_search = AsyncMock(return_value=[])
        service.semantic_search = AsyncMock(return_value=[
            (MagicMock(id="c1", document_id="d1", content="test", page_number=1, chunk_index=0), 0.9)
        ])
        mock_db = AsyncMock()
        results = await service.search(mock_db, "test query", strategy="KEYWORD", top_k=5)
        assert len(results) == 1
        service.semantic_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_semantic_empty_fallback_to_hybrid(self):
        """When SEMANTIC returns empty, fallback to HYBRID."""
        service = RetrievalService()
        service.semantic_search = AsyncMock(return_value=[])
        service.hybrid_search = AsyncMock(return_value=[
            (MagicMock(id="c1", document_id="d1", content="test", page_number=1, chunk_index=0), 0.8)
        ])
        mock_db = AsyncMock()
        results = await service.search(mock_db, "test query", strategy="SEMANTIC", top_k=5)
        assert len(results) == 1
        service.hybrid_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_no_fallback(self):
        """HYBRID strategy does not trigger fallback."""
        service = RetrievalService()
        service.hybrid_search = AsyncMock(return_value=[])
        mock_db = AsyncMock()
        results = await service.search(mock_db, "test", strategy="HYBRID", top_k=5)
        assert results == []


class TestSemanticSearch:
    """Tests for semantic search."""

    @pytest.mark.asyncio
    async def test_semantic_search_builds_query(self):
        """Test semantic search executes query."""
        service = RetrievalService()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        with patch("app.services.retrieval.embedding_service") as mock_embed:
            mock_embed.embed_text = AsyncMock(return_value=[0.1] * 100)
            result = await service.semantic_search(mock_db, "test", top_k=5)
            assert result == []


class TestRetrievalInit:
    """Retrieval init and factory tests."""

    def test_service_exists(self):
        """Test retrieval service can be imported."""
        assert RetrievalService is not None

    def test_factory_exists(self):
        """Test factory function exists."""
        assert create_retrieval_service is not None

    def test_format_embedding_basic(self):
        """Test formatting embedding list."""
        service = RetrievalService()
        formatted = service._format_embedding([0.1, 0.2, 0.3])
        assert formatted.startswith("[") and formatted.endswith("]")
