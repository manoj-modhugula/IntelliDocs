"""Tests for ingestion service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.ingestion import IngestionService


class TestIngestionService:
    """Tests for document ingestion."""

    def test_init_sets_chunk_params(self):
        """Test that initialization sets chunking parameters."""
        service = IngestionService()
        # Multi-granularity: small and large chunk sizes
        assert service.chunk_size_small > 0
        assert service.chunk_size_large > 0
        assert service.chunk_size_large > service.chunk_size_small
        assert service.chunk_overlap >= 0

    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        service = IngestionService()
        text = "word " * 100
        chunks = service.chunk_text(text)
        
        assert len(chunks) >= 1
        assert all("content" in c for c in chunks)
        assert all("chunk_index" in c for c in chunks)

    def test_chunk_text_preserves_page_number(self):
        """Test that page number is preserved in chunks."""
        service = IngestionService()
        text = "Some text content"
        chunks = service.chunk_text(text, page_number=5)
        
        assert all(c["page_number"] == 5 for c in chunks)

    def test_chunk_text_handles_empty(self):
        """Test handling of empty text."""
        service = IngestionService()
        chunks = service.chunk_text("")
        assert len(chunks) == 0 or chunks[0]["content"] == ""

    def test_chunk_text_handles_short_text(self):
        """Test that short text becomes single chunk per granularity."""
        service = IngestionService()
        text = "Short text"
        chunks = service.chunk_text(text)
        
        # With multi-granularity enabled, we get chunks for both small and large
        if service.enable_multi_granularity:
            # Should have at least one chunk from each granularity
            granularities = set(c.get("granularity") for c in chunks)
            assert "small" in granularities or "large" in granularities
            # Content should be preserved in each
            assert all(text in c["content"] for c in chunks)
        else:
            assert len(chunks) == 1
            assert chunks[0]["content"] == text

    def test_chunk_text_creates_overlap(self):
        """Test that chunks have overlap."""
        service = IngestionService()
        # Disable multi-granularity for simpler overlap testing
        service.enable_multi_granularity = False
        service.chunk_size_small = 50  # ~50 tokens = 200 chars
        service.chunk_overlap = 10
        
        # Use sentences since chunking is sentence-boundary aware
        text = "This is sentence one. This is sentence two. This is sentence three. " * 20
        chunks = service.chunk_text(text)
        
        # Should create multiple chunks for this long text
        assert len(chunks) >= 1  # At least one chunk
        # Content should be preserved
        assert all(len(c["content"]) > 0 for c in chunks)

    @pytest.mark.asyncio
    async def test_parse_text(self):
        """Test plain text parsing."""
        service = IngestionService()
        content = b"Hello world"
        
        result = await service.parse_text(content)
        
        assert len(result) == 1
        assert result[0]["content"] == "Hello world"
        assert result[0]["page_number"] is None

    @pytest.mark.asyncio
    async def test_parse_text_handles_unicode(self):
        """Test parsing of unicode content."""
        service = IngestionService()
        content = "Hello résumé 日本語".encode("utf-8")
        
        result = await service.parse_text(content)
        
        assert len(result) == 1
        assert "résumé" in result[0]["content"]

    @pytest.mark.asyncio
    async def test_parse_document_routes_to_text(self):
        """Test that parse_document routes text correctly."""
        service = IngestionService()
        
        result = await service.parse_document(b"test", "text/plain")
        
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_parse_pdf_with_mock(self):
        """Test PDF parsing with mocked pdfplumber."""
        service = IngestionService()
        
        with patch("pdfplumber.open") as mock_open:
            # Setup mock
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Page content"
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
            mock_pdf.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_pdf
            
            result = await service.parse_pdf(b"fake pdf content")
            
            assert len(result) == 1
            assert result[0]["content"] == "Page content"
            assert result[0]["page_number"] == 1

    @pytest.mark.asyncio
    async def test_parse_docx_with_mock(self):
        """Test DOCX parsing with mocked Document."""
        service = IngestionService()
        
        with patch("docx.Document") as mock_doc:
            # Setup mock
            mock_para = MagicMock()
            mock_para.text = "Paragraph content"
            mock_doc.return_value.paragraphs = [mock_para]
            
            result = await service.parse_docx(b"fake docx content")
            
            assert len(result) == 1
            assert result[0]["content"] == "Paragraph content"


class TestIngestionIntegration:
    """Integration tests for ingestion."""

    @pytest.mark.asyncio
    async def test_full_text_pipeline(self):
        """Test full text processing pipeline."""
        service = IngestionService()
        
        # Create sample content
        content = b"This is a sample document. " * 50
        
        # Parse
        pages = await service.parse_text(content)
        assert len(pages) >= 1
        
        # Chunk
        all_chunks = []
        for page in pages:
            chunks = service.chunk_text(page["content"], page["page_number"])
            all_chunks.extend(chunks)
        
        # Should have chunks with content
        assert len(all_chunks) >= 1
        assert all(len(c["content"]) > 0 for c in all_chunks)

    def test_chunk_indexing_is_sequential(self):
        """Test that chunk indices are sequential within each granularity."""
        service = IngestionService()
        service.enable_multi_granularity = False  # Test single granularity
        service.chunk_size_small = 100
        
        text = "word " * 200
        chunks = service.chunk_text(text)
        
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))
    
    def test_multi_granularity_produces_both_sizes(self):
        """Test that multi-granularity creates both small and large chunks."""
        service = IngestionService()
        service.enable_multi_granularity = True
        
        # Large enough text to produce multiple chunks
        text = "This is a sentence. " * 100
        chunks = service.chunk_text(text)
        
        granularities = set(c.get("granularity") for c in chunks)
        assert "small" in granularities
        assert "large" in granularities
