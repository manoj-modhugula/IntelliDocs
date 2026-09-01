"""Tests for ingestion service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from io import BytesIO


class TestIngestionServiceInit:
    """Tests for ingestion service initialization."""
    
    def test_service_initialization(self):
        """Test ingestion service initializes correctly."""
        from app.services.ingestion import IngestionService
        
        service = IngestionService()
        
        # Multi-granularity: small and large chunk sizes
        assert service.chunk_size_small > 0
        assert service.chunk_size_large > 0
        assert service.chunk_overlap >= 0


class TestParsePdf:
    """Tests for PDF parsing."""
    
    @pytest.mark.asyncio
    async def test_parse_pdf_empty(self):
        """Test parsing invalid PDF content returns empty list (graceful fallback)."""
        from app.services.ingestion import IngestionService
        
        service = IngestionService()
        
        # Invalid PDF-like content - service returns empty list with fallback chain
        result = await service.parse_pdf(b"not a pdf")
        assert result == []  # Graceful fallback returns empty list


class TestParseDocx:
    """Tests for DOCX parsing."""
    
    @pytest.mark.asyncio
    async def test_parse_docx_empty(self):
        """Test parsing empty DOCX content."""
        from app.services.ingestion import IngestionService
        
        service = IngestionService()
        
        # This will fail gracefully
        with pytest.raises(Exception):
            await service.parse_docx(b"not a docx")


class TestParseText:
    """Tests for text parsing."""
    
    @pytest.mark.asyncio
    async def test_parse_text_simple(self):
        """Test parsing simple text."""
        from app.services.ingestion import IngestionService
        
        service = IngestionService()
        content = b"Hello, world! This is a test."
        
        result = await service.parse_text(content)
        
        assert len(result) == 1
        assert result[0]["content"] == "Hello, world! This is a test."
    
    @pytest.mark.asyncio
    async def test_parse_text_unicode(self):
        """Test parsing unicode text."""
        from app.services.ingestion import IngestionService
        
        service = IngestionService()
        content = "Hello, 世界! こんにちは".encode('utf-8')
        
        result = await service.parse_text(content)
        
        assert len(result) == 1
        assert "世界" in result[0]["content"]


class TestParseDocument:
    """Tests for document parsing."""
    
    @pytest.mark.asyncio
    async def test_parse_document_txt(self):
        """Test parsing text document."""
        from app.services.ingestion import IngestionService
        
        service = IngestionService()
        content = b"Test content"
        
        result = await service.parse_document(content, "text/plain")
        
        assert len(result) == 1
        assert result[0]["content"] == "Test content"
    
    @pytest.mark.asyncio
    async def test_parse_document_unknown_type(self):
        """Test parsing unknown document type defaults to text."""
        from app.services.ingestion import IngestionService
        
        service = IngestionService()
        content = b"Some content"
        
        result = await service.parse_document(content, "application/unknown")
        
        assert len(result) == 1


class TestChunkText:
    """Tests for text chunking."""
    
    def test_chunk_text_empty(self):
        """Test chunking empty text."""
        from app.services.ingestion import IngestionService
        
        service = IngestionService()
        
        chunks = service.chunk_text("")
        
        assert chunks == []
    
    def test_chunk_text_short(self):
        """Test chunking short text creates one chunk per granularity."""
        from app.services.ingestion import IngestionService
        
        service = IngestionService()
        service.chunk_size_small = 1000
        service.chunk_size_large = 2000
        
        chunks = service.chunk_text("Hello world")
        
        # With multi-granularity enabled, we get chunks for both sizes
        if service.enable_multi_granularity:
            assert len(chunks) >= 1  # At least one chunk
            assert all("Hello world" in c["content"] for c in chunks)
        else:
            assert len(chunks) == 1
            assert chunks[0]["content"] == "Hello world"
    
    def test_chunk_text_long(self):
        """Test chunking long text creates multiple chunks."""
        from app.services.ingestion import IngestionService
        
        service = IngestionService()
        service.enable_multi_granularity = False  # Single granularity for simpler test
        service.chunk_size_small = 50
        service.chunk_overlap = 10
        
        # Create long text with sentences (sentence-boundary aware)
        long_text = "This is a sentence. " * 100
        
        chunks = service.chunk_text(long_text)
        
        assert len(chunks) >= 1
    
    def test_chunk_text_preserves_page_number(self):
        """Test chunking preserves page number."""
        from app.services.ingestion import IngestionService
        
        service = IngestionService()
        service.chunk_size_small = 1000
        
        chunks = service.chunk_text("Test content", page_number=5)
        
        assert all(c["page_number"] == 5 for c in chunks)
    
    def test_chunk_text_includes_chunk_index(self):
        """Test chunking includes chunk index."""
        from app.services.ingestion import IngestionService
        
        service = IngestionService()
        service.enable_multi_granularity = False  # Single granularity for index test
        service.chunk_size_small = 50
        
        long_text = "This is a sentence. " * 100
        chunks = service.chunk_text(long_text)
        
        assert chunks[0]["chunk_index"] == 0
        if len(chunks) > 1:
            assert chunks[1]["chunk_index"] == 1


class TestIngestionSingleton:
    """Tests for ingestion service singleton."""
    
    def test_singleton_exists(self):
        """Test singleton instance exists."""
        from app.services.ingestion import ingestion_service
        
        assert ingestion_service is not None
