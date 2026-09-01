"""Advanced tests for storage service."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from io import BytesIO
from app.services.storage import StorageService


class TestStorageUpload:
    """Tests for document upload."""

    @pytest.mark.asyncio
    async def test_upload_generates_s3_key(self):
        """Test that upload generates proper S3 key."""
        service = StorageService()
        
        with patch.object(service, "client") as mock_client:
            mock_client.put_object = MagicMock()
            
            file = BytesIO(b"test content")
            result = await service.upload_document(
                file, "test.pdf", "application/pdf", "doc-123"
            )
            
            assert "doc-123" in result
            assert result.startswith("documents/")

    @pytest.mark.asyncio
    async def test_upload_uses_s3_client(self):
        """Test that upload uses S3 client."""
        service = StorageService()
        
        # Just verify service has client attribute
        assert hasattr(service, "client")
        assert hasattr(service, "bucket_name")


class TestStorageDownload:
    """Tests for document download."""

    @pytest.mark.asyncio
    async def test_download_returns_bytes(self):
        """Test that download returns file bytes."""
        service = StorageService()
        
        with patch.object(service, "client") as mock_client:
            mock_body = MagicMock()
            mock_body.read.return_value = b"file content"
            mock_client.get_object = MagicMock(return_value={"Body": mock_body})
            
            result = await service.download_document("documents/test.pdf")
            
            assert result == b"file content"

    @pytest.mark.asyncio
    async def test_download_calls_get_object(self):
        """Test that download calls S3 get_object."""
        service = StorageService()
        
        with patch.object(service, "client") as mock_client:
            mock_body = MagicMock()
            mock_body.read.return_value = b"content"
            mock_client.get_object = MagicMock(return_value={"Body": mock_body})
            
            await service.download_document("documents/test.pdf")
            
            mock_client.get_object.assert_called_once()


class TestStorageDelete:
    """Tests for document deletion."""

    @pytest.mark.asyncio
    async def test_delete_returns_true(self):
        """Test that delete returns True on success."""
        service = StorageService()
        
        with patch.object(service, "client") as mock_client:
            mock_client.delete_object = MagicMock()
            
            result = await service.delete_document("documents/test.pdf")
            
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_calls_delete_object(self):
        """Test that delete calls S3 delete_object."""
        service = StorageService()
        
        with patch.object(service, "client") as mock_client:
            mock_client.delete_object = MagicMock()
            
            await service.delete_document("documents/test.pdf")
            
            mock_client.delete_object.assert_called_once()


class TestStoragePresignedUrl:
    """Tests for presigned URL generation."""

    @pytest.mark.asyncio
    async def test_presigned_url_returns_string(self):
        """Test that presigned URL returns a string."""
        service = StorageService()
        
        with patch.object(service, "client") as mock_client:
            mock_client.generate_presigned_url = MagicMock(
                return_value="https://s3.example.com/signed-url"
            )
            
            result = await service.get_presigned_url("documents/test.pdf")
            
            assert result == "https://s3.example.com/signed-url"

    @pytest.mark.asyncio
    async def test_presigned_url_custom_expiration(self):
        """Test presigned URL with custom expiration."""
        service = StorageService()
        
        with patch.object(service, "client") as mock_client:
            mock_client.generate_presigned_url = MagicMock(return_value="url")
            
            await service.get_presigned_url("key", expiration=7200)
            
            call_args = mock_client.generate_presigned_url.call_args
            assert call_args[1]["ExpiresIn"] == 7200


class TestBucketManagement:
    """Tests for bucket management."""

    def test_ensure_bucket_method_exists(self):
        """Test ensure_bucket_exists method exists."""
        service = StorageService()
        
        # Method should exist
        assert hasattr(service, "ensure_bucket_exists")
        assert callable(service.ensure_bucket_exists)

    def test_ensure_bucket_exists_returns_true(self):
        """Test returns True when bucket exists."""
        service = StorageService()
        
        with patch.object(service, "client") as mock_client:
            mock_client.head_bucket = MagicMock()  # No exception = exists
            
            result = service.ensure_bucket_exists()
            
            assert result is True
