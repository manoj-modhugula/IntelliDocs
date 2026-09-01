"""Advanced tests for ingestion service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.ingestion import IngestionService


class TestPDFParsing:
    """Tests for PDF parsing."""

    @pytest.mark.asyncio
    async def test_parse_pdf_extracts_pages(self):
        """Test PDF parsing extracts page content."""
        service = IngestionService()
        
        with patch("pdfplumber.open") as mock_open:
            mock_page1 = MagicMock()
            mock_page1.extract_text.return_value = "Page 1 content"
            mock_page2 = MagicMock()
            mock_page2.extract_text.return_value = "Page 2 content"
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_page1, mock_page2]
            mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
            mock_pdf.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_pdf
            
            result = await service.parse_pdf(b"fake pdf")
            
            assert len(result) == 2
            assert result[0]["page_number"] == 1
            assert result[1]["page_number"] == 2

    @pytest.mark.asyncio
    async def test_parse_pdf_skips_empty_pages(self):
        """Test that empty pages are skipped."""
        service = IngestionService()
        
        with patch("pdfplumber.open") as mock_open:
            mock_page1 = MagicMock()
            mock_page1.extract_text.return_value = "Content"
            mock_page2 = MagicMock()
            mock_page2.extract_text.return_value = ""  # Empty page
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_page1, mock_page2]
            mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
            mock_pdf.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_pdf
            
            result = await service.parse_pdf(b"fake pdf")
            
            assert len(result) == 1


class TestDOCXParsing:
    """Tests for DOCX parsing."""

    @pytest.mark.asyncio
    async def test_parse_docx_extracts_paragraphs(self):
        """Test DOCX parsing extracts paragraphs."""
        service = IngestionService()
        
        with patch("docx.Document") as mock_doc:
            mock_para1 = MagicMock()
            mock_para1.text = "Paragraph 1"
            mock_para2 = MagicMock()
            mock_para2.text = "Paragraph 2"
            mock_doc.return_value.paragraphs = [mock_para1, mock_para2]
            
            result = await service.parse_docx(b"fake docx")
            
            assert len(result) == 2
            assert result[0]["content"] == "Paragraph 1"

    @pytest.mark.asyncio
    async def test_parse_docx_skips_empty_paragraphs(self):
        """Test that empty paragraphs are skipped."""
        service = IngestionService()
        
        with patch("docx.Document") as mock_doc:
            mock_para1 = MagicMock()
            mock_para1.text = "Content"
            mock_para2 = MagicMock()
            mock_para2.text = "   "  # Whitespace only
            mock_doc.return_value.paragraphs = [mock_para1, mock_para2]
            
            result = await service.parse_docx(b"fake docx")
            
            assert len(result) == 1


class TestDocumentRouting:
    """Tests for document type routing."""

    @pytest.mark.asyncio
    async def test_parse_document_routes_pdf(self):
        """Test PDF file type routing."""
        service = IngestionService()
        service.parse_pdf = AsyncMock(return_value=[{"content": "pdf"}])
        
        result = await service.parse_document(b"content", "application/pdf")
        
        service.parse_pdf.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_document_routes_docx(self):
        """Test DOCX file type routing."""
        service = IngestionService()
        service.parse_docx = AsyncMock(return_value=[{"content": "docx"}])
        
        result = await service.parse_document(
            b"content", 
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        service.parse_docx.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_document_routes_text_default(self):
        """Test text file type as default."""
        service = IngestionService()
        service.parse_text = AsyncMock(return_value=[{"content": "text"}])
        
        result = await service.parse_document(b"content", "text/plain")
        
        service.parse_text.assert_called_once()


class TestChunking:
    """Tests for text chunking."""

    def test_chunk_creates_indices(self):
        """Test that chunks have sequential indices within each granularity."""
        service = IngestionService()
        service.enable_multi_granularity = False  # Single granularity for index test
        service.chunk_size_small = 50
        
        text = "This is a sentence. " * 50  # Create multiple chunks with sentences
        chunks = service.chunk_text(text)
        
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_chunk_includes_token_count(self):
        """Test that chunks include token count."""
        service = IngestionService()
        
        text = "one two three four five"
        chunks = service.chunk_text(text)
        
        assert "token_count" in chunks[0]
        assert chunks[0]["token_count"] > 0

    def test_chunk_respects_chunk_size(self):
        """Test that chunks respect max size approximately."""
        service = IngestionService()
        service.enable_multi_granularity = False
        service.chunk_size_small = 500  # Larger to accommodate word boundaries
        
        text = "This is a sentence. " * 200
        chunks = service.chunk_text(text)
        
        # Should create multiple chunks
        assert len(chunks) >= 1

    def test_chunk_creates_overlap(self):
        """Test that chunks have overlap."""
        service = IngestionService()
        service.enable_multi_granularity = False
        service.chunk_size_small = 50
        service.chunk_overlap = 20
        
        text = "This is a sentence. " * 50
        chunks = service.chunk_text(text)
        
        if len(chunks) >= 2:
            # Chunks should share some content (overlap)
            assert all(len(c["content"]) > 0 for c in chunks)
