"""
Tests for RAG service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.rag import RAGService, create_rag_service


class TestRAGService:
    """Tests for RAGService."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.rag = RAGService()
    
    def test_format_context(self):
        """Test context formatting."""
        mock_chunk = MagicMock()
        mock_chunk.content = "This is test content."
        
        chunks = [(mock_chunk, 0.85)]
        context = self.rag._format_context(chunks)
        
        assert "[1]" in context
        assert "0.85" in context
        assert "This is test content." in context
    
    def test_format_context_multiple_chunks(self):
        """Test context formatting with multiple chunks."""
        mock_chunk1 = MagicMock()
        mock_chunk1.content = "First chunk."
        mock_chunk2 = MagicMock()
        mock_chunk2.content = "Second chunk."
        
        chunks = [(mock_chunk1, 0.9), (mock_chunk2, 0.8)]
        context = self.rag._format_context(chunks)
        
        assert "[1]" in context
        assert "[2]" in context
        assert "First chunk." in context
        assert "Second chunk." in context
    
    @pytest.mark.asyncio
    async def test_build_citations(self):
        """Test citation building."""
        mock_chunk = MagicMock()
        mock_chunk.id = "chunk-1"
        mock_chunk.document_id = "doc-1"
        mock_chunk.page_number = 5
        mock_chunk.content = "Short content"
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        
        chunks = [(mock_chunk, 0.85)]
        citations = await self.rag._build_citations(chunks, mock_db)
        
        assert len(citations) == 1
        assert citations[0]["id"] == "cite-1"
        assert citations[0]["documentId"] == "doc-1"
        assert citations[0]["pageNumber"] == 5
        assert citations[0]["relevanceScore"] == 0.85
    
    @pytest.mark.asyncio
    async def test_build_citations_truncates_long_content(self):
        """Test that long content is truncated in citations."""
        mock_chunk = MagicMock()
        mock_chunk.id = "chunk-1"
        mock_chunk.document_id = "doc-1"
        mock_chunk.page_number = None
        mock_chunk.content = "x" * 500  # Long content
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        
        chunks = [(mock_chunk, 0.85)]
        citations = await self.rag._build_citations(chunks, mock_db)
        
        assert len(citations[0]["chunkText"]) <= 203  # 200 + "..."
        assert citations[0]["chunkText"].endswith("...")
    
    def test_system_prompt_contains_context_placeholder(self):
        """Test system prompt has context placeholder."""
        assert "{context}" in self.rag.system_prompt
    
    @pytest.mark.asyncio
    async def test_answer_returns_no_documents_message(self):
        """Test answer returns appropriate message when no chunks found."""
        # Create mocked services
        mock_llm = MagicMock()
        mock_llm.route_query = AsyncMock(return_value="HYBRID")
        
        mock_retrieval = MagicMock()
        mock_retrieval.search = AsyncMock(return_value=[])
        
        mock_cache = MagicMock()
        mock_cache.get_semantic_cache = AsyncMock(return_value=None)
        
        mock_embedding = MagicMock()
        mock_embedding.embed_text = AsyncMock(return_value=[0.1] * 100)
        
        # Create RAG service with mocked dependencies
        rag = create_rag_service(
            llm_svc=mock_llm,
            retrieval_svc=mock_retrieval,
            cache_svc=mock_cache,
            embedding_svc=mock_embedding,
        )
        
        mock_db = AsyncMock()
        result = await rag.answer(mock_db, "test query")
        
        assert "couldn't find" in result["answer"].lower()
        assert result["citations"] == []
    
    @pytest.mark.asyncio
    async def test_answer_uses_cache_when_available(self):
        """Test answer returns cached result when available."""
        cached_response = {
            "answer": "Cached answer",
            "citations": [],
            "strategy": "HYBRID",
        }
        
        mock_cache = MagicMock()
        mock_cache.get_semantic_cache = AsyncMock(return_value=cached_response)
        
        mock_embedding = MagicMock()
        mock_embedding.embed_text = AsyncMock(return_value=[0.1] * 100)
        
        rag = create_rag_service(
            cache_svc=mock_cache,
            embedding_svc=mock_embedding,
        )
        
        mock_db = AsyncMock()
        result = await rag.answer(mock_db, "test query")
        
        assert result["answer"] == "Cached answer"
        assert result.get("from_cache") == True


class TestRAGIntegration:
    """Integration tests for RAG service."""
    
    @pytest.mark.asyncio
    async def test_answer_flow_with_chunks(self):
        """Test complete answer flow with chunks."""
        mock_chunk = MagicMock()
        mock_chunk.id = "chunk-1"
        mock_chunk.document_id = "doc-1"
        mock_chunk.content = "The answer is 42."
        mock_chunk.page_number = 1
        
        mock_llm = MagicMock()
        mock_llm.route_query = AsyncMock(return_value="SEMANTIC")
        mock_llm.generate = AsyncMock(return_value="Based on the document, the answer is 42.")
        
        mock_retrieval = MagicMock()
        mock_retrieval.search = AsyncMock(return_value=[(mock_chunk, 0.9)])
        
        mock_cache = MagicMock()
        mock_cache.get_semantic_cache = AsyncMock(return_value=None)
        mock_cache.set_semantic_cache = AsyncMock(return_value=True)
        
        mock_embedding = MagicMock()
        mock_embedding.embed_text = AsyncMock(return_value=[0.1] * 100)
        
        rag = create_rag_service(
            llm_svc=mock_llm,
            retrieval_svc=mock_retrieval,
            cache_svc=mock_cache,
            embedding_svc=mock_embedding,
        )
        
        mock_db = AsyncMock()
        exec_result = MagicMock()
        exec_result.all.return_value = [("doc-1", "doc.pdf")]
        mock_db.execute = AsyncMock(return_value=exec_result)
        result = await rag.answer(mock_db, "What is the answer?")
        
        assert "42" in result["answer"]
        assert len(result["citations"]) == 1
        assert result["strategy"] in ("SEMANTIC", "KEYWORD", "HYBRID")


class TestRAGLowConfidenceRetry:
    """Test RAG low-confidence retry logic."""

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_hybrid_retry(self):
        """When best semantic score < 0.5, retry with HYBRID."""
        mock_chunk = MagicMock()
        mock_chunk.id = "c1"
        mock_chunk.document_id = "d1"
        mock_chunk.content = "Low relevance content"
        mock_chunk.page_number = 1
        mock_chunk.chunk_index = 0

        mock_llm = MagicMock()
        mock_llm.route_query = AsyncMock(return_value="SEMANTIC")
        mock_llm.generate = AsyncMock(return_value="Generated answer")

        mock_retrieval = MagicMock()
        mock_retrieval.search = AsyncMock(side_effect=[
            [(mock_chunk, 0.3)],
            [(mock_chunk, 0.85)],
        ])

        mock_cache = MagicMock()
        mock_cache.get_semantic_cache = AsyncMock(return_value=None)
        mock_cache.set_semantic_cache = AsyncMock()
        mock_embedding = MagicMock()
        mock_embedding.embed_text = AsyncMock(return_value=[0.1] * 1024)

        rag = create_rag_service(
            llm_svc=mock_llm, retrieval_svc=mock_retrieval,
            cache_svc=mock_cache, embedding_svc=mock_embedding,
        )
        mock_db = AsyncMock()
        exec_result = MagicMock()
        exec_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=exec_result)
        result = await rag.answer(mock_db, "test query", use_cache=False)

        assert result["strategy"] == "HYBRID"
        assert result["answer"] == "Generated answer"
        assert mock_retrieval.search.call_count == 2


class TestRAGContextFormatting:
    """Additional context formatting tests."""

    def test_format_context_empty_chunks(self):
        """Test formatting with no chunks."""
        rag = RAGService()
        assert rag._format_context([]) == ""


class TestRAGCitationsAdvanced:
    """Additional citation tests."""

    @pytest.mark.asyncio
    async def test_build_citations_empty(self):
        """Test building citations with no chunks."""
        rag = RAGService()
        result = await rag._build_citations([], MagicMock())
        assert result == []


class TestRAGInitAndFactory:
    """RAG init and factory tests."""

    def test_service_exists(self):
        """Test RAG service can be imported."""
        assert RAGService is not None

    def test_rag_service_error(self):
        """Test RAGServiceError exception."""
        from app.services.rag import RAGServiceError
        assert str(RAGServiceError("err")) == "err"
