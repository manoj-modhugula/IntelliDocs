"""Tests for storage service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from io import BytesIO


class TestStorageServiceInit:
    """Tests for storage service initialization."""
    
    def test_service_initialization(self):
        """Test storage service initializes with S3 client."""
        with patch('boto3.client'):
            from app.services.storage import StorageService
            
            service = StorageService()
            
            assert service.client is not None
            assert service.bucket_name is not None
    
    def test_service_bucket_name(self):
        """Test storage service uses correct bucket name."""
        with patch('boto3.client'):
            from app.services.storage import StorageService
            
            service = StorageService()
            
            assert service.bucket_name is not None


class TestUploadDocument:
    """Tests for document upload."""
    
    @pytest.mark.asyncio
    async def test_upload_returns_s3_key(self):
        """Test upload returns S3 key."""
        with patch('boto3.client') as mock_client:
            from app.services.storage import StorageService
            
            service = StorageService()
            service.client.upload_fileobj = MagicMock()
            
            file = BytesIO(b"test content")
            s3_key = await service.upload_document(
                file=file,
                filename="test.pdf",
                content_type="application/pdf",
                document_id="doc-123",
            )
            
            assert "doc-123" in s3_key
            assert "test.pdf" in s3_key
    
    @pytest.mark.asyncio
    async def test_upload_calls_upload_fileobj(self):
        """Test upload calls S3 upload_fileobj."""
        with patch('boto3.client') as mock_client:
            from app.services.storage import StorageService
            
            service = StorageService()
            service.client.upload_fileobj = MagicMock()
            
            file = BytesIO(b"content")
            await service.upload_document(
                file=file,
                filename="doc.txt",
                content_type="text/plain",
                document_id="doc-456",
            )
            
            service.client.upload_fileobj.assert_called_once()


class TestDownloadDocument:
    """Tests for document download."""
    
    @pytest.mark.asyncio
    async def test_download_returns_bytes(self):
        """Test download returns file content as bytes."""
        with patch('boto3.client') as mock_boto:
            from app.services.storage import StorageService
            
            service = StorageService()
            
            # Mock S3 response
            mock_body = MagicMock()
            mock_body.read.return_value = b"file content"
            service.client.get_object = MagicMock(return_value={"Body": mock_body})
            
            content = await service.download_document("test-key.txt")
            
            assert content == b"file content"
    
    @pytest.mark.asyncio
    async def test_download_calls_get_object(self):
        """Test download calls S3 get_object."""
        with patch('boto3.client') as mock_boto:
            from app.services.storage import StorageService
            
            service = StorageService()
            
            mock_body = MagicMock()
            mock_body.read.return_value = b"content"
            service.client.get_object = MagicMock(return_value={"Body": mock_body})
            
            await service.download_document("my-key")
            
            service.client.get_object.assert_called_once()


class TestDeleteDocument:
    """Tests for document deletion."""
    
    @pytest.mark.asyncio
    async def test_delete_returns_true(self):
        """Test delete returns True on success."""
        with patch('boto3.client') as mock_boto:
            from app.services.storage import StorageService
            
            service = StorageService()
            service.client.delete_object = MagicMock()
            
            result = await service.delete_document("test-key")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_calls_delete_object(self):
        """Test delete calls S3 delete_object."""
        with patch('boto3.client') as mock_boto:
            from app.services.storage import StorageService
            
            service = StorageService()
            service.client.delete_object = MagicMock()
            
            await service.delete_document("test-key")
            
            service.client.delete_object.assert_called_once()


class TestGetPresignedUrl:
    """Tests for presigned URL generation."""
    
    @pytest.mark.asyncio
    async def test_presigned_url_format(self):
        """Test presigned URL has correct format."""
        with patch('boto3.client') as mock_boto:
            from app.services.storage import StorageService
            
            service = StorageService()
            service.client.generate_presigned_url = MagicMock(
                return_value="https://s3.amazonaws.com/bucket/key?sig=xxx"
            )
            
            url = await service.get_presigned_url("test-key")
            
            assert url.startswith("https://")
    
    @pytest.mark.asyncio
    async def test_presigned_url_custom_expiry(self):
        """Test presigned URL with custom expiry."""
        with patch('boto3.client') as mock_boto:
            from app.services.storage import StorageService
            
            service = StorageService()
            service.client.generate_presigned_url = MagicMock(
                return_value="https://example.com/file"
            )
            
            url = await service.get_presigned_url("key", expiration=7200)
            
            assert url is not None


class TestEnsureBucketExists:
    """Tests for bucket existence check."""
    
    def test_bucket_exists(self):
        """Test bucket exists returns True."""
        with patch('boto3.client') as mock_boto:
            from app.services.storage import StorageService
            
            service = StorageService()
            service.client.head_bucket = MagicMock()
            
            result = service.ensure_bucket_exists()
            
            assert result is True


class TestStorageSingleton:
    """Tests for storage service singleton."""
    
    def test_singleton_exists(self):
        """Test singleton instance exists."""
        with patch('boto3.client'):
            from app.services.storage import storage_service
            
            assert storage_service is not None
