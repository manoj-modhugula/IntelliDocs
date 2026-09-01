"""
Tests for S3 storage service.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from io import BytesIO

from app.services.storage import StorageService


class TestStorageService:
    """Tests for StorageService."""
    
    def test_init_creates_s3_client(self):
        """Test initialization creates S3 client."""
        with patch("boto3.client") as mock_client:
            service = StorageService(backend="s3")
            
            mock_client.assert_called_once()
            call_args = mock_client.call_args
            assert call_args.args[0] == "s3"
    
    @pytest.mark.asyncio
    async def test_upload_document_returns_s3_key(self):
        """Test upload returns S3 key."""
        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            
            service = StorageService(backend="s3")
            file = BytesIO(b"test content")
            
            result = await service.upload_document(
                file=file,
                filename="test.pdf",
                content_type="application/pdf",
                document_id="doc-123",
            )
            
            assert "documents/" in result
            assert "test.pdf" in result
            assert "doc-123" in result
    
    @pytest.mark.asyncio
    async def test_upload_document_calls_s3(self):
        """Test upload calls S3 upload_fileobj."""
        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            
            service = StorageService(backend="s3")
            file = BytesIO(b"test content")
            
            await service.upload_document(
                file=file,
                filename="test.pdf",
                content_type="application/pdf",
                document_id="doc-123",
            )
            
            mock_client.upload_fileobj.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_download_document_returns_bytes(self):
        """Test download returns bytes."""
        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            
            mock_response = {
                "Body": MagicMock()
            }
            mock_response["Body"].read.return_value = b"file content"
            mock_client.get_object.return_value = mock_response
            
            service = StorageService(backend="s3")
            result = await service.download_document("documents/test.pdf")
            
            assert result == b"file content"
    
    @pytest.mark.asyncio
    async def test_delete_document_returns_true(self):
        """Test delete returns True on success."""
        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            
            service = StorageService(backend="s3")
            result = await service.delete_document("documents/test.pdf")
            
            assert result == True
            mock_client.delete_object.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_presigned_url_returns_url(self):
        """Test presigned URL generation."""
        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            mock_client.generate_presigned_url.return_value = "https://s3.amazonaws.com/..."
            
            service = StorageService(backend="s3")
            result = await service.get_presigned_url("documents/test.pdf")
            
            assert result.startswith("https://")
            mock_client.generate_presigned_url.assert_called_once()


class TestBucketManagement:
    """Tests for S3 bucket management."""
    
    def test_ensure_bucket_exists_returns_true(self):
        """Test bucket check returns True when bucket exists."""
        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            
            service = StorageService(backend="s3")
            result = service.ensure_bucket_exists()
            
            assert result == True
            mock_client.head_bucket.assert_called_once()
