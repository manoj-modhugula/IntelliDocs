"""Document file storage: local disk (default) or S3."""

import asyncio
import re
import shutil
from pathlib import Path
from typing import BinaryIO, Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.utils import utc_now

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    cleaned = _UNSAFE_FILENAME.sub("_", name).strip("._")
    return cleaned or "file"


class StorageService:
    
    def __init__(
        self,
        backend: Optional[str] = None,
        local_dir: Optional[str] = None,
        client=None,
    ):
        self.backend = (backend or settings.STORAGE_BACKEND or "local").lower()
        self.local_dir = Path(local_dir or settings.LOCAL_STORAGE_DIR)
        self.bucket_name = settings.S3_BUCKET_NAME
        self.client = client
        if self.backend == "s3" and self.client is None:
            self.client = boto3.client(
                "s3",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
    
    def _local_path(self, document_id: str, filename: str) -> Path:
        return self.local_dir / document_id / _safe_filename(filename)

    def _local_key(self, document_id: str, filename: str) -> str:
        return f"{document_id}/{_safe_filename(filename)}"

    def _parse_local_key(self, key: str) -> Path:
        parts = Path(key).parts
        if len(parts) < 2:
            raise ValueError(f"Invalid storage key: {key}")
        document_id = parts[0]
        filename = _safe_filename(parts[-1])
        return self.local_dir / document_id / filename

    async def upload_document(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str,
        document_id: str,
    ) -> str:
        if self.backend == "local":
            dest = self._local_path(document_id, filename)
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = file.read() if hasattr(file, "read") else file
            if not isinstance(data, (bytes, bytearray)):
                data = bytes(data)
            dest.write_bytes(data)
            return self._local_key(document_id, filename)

        timestamp = utc_now().strftime("%Y/%m/%d")
        s3_key = f"documents/{timestamp}/{document_id}/{filename}"
        
        try:
            await asyncio.to_thread(
                self.client.upload_fileobj,
                file,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "Metadata": {
                        "document_id": document_id,
                        "original_filename": filename,
                    },
                },
            )
            return s3_key
        except ClientError as e:
            raise Exception(f"Failed to upload to S3: {e}")
    
    async def download_document(self, s3_key: str) -> bytes:
        if self.backend == "local":
            path = self._parse_local_key(s3_key)
            return path.read_bytes()
        try:
            response = await asyncio.to_thread(
                self.client.get_object,
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return await asyncio.to_thread(response["Body"].read)
        except ClientError as e:
            raise Exception(f"Failed to download from S3: {e}")
    
    def save_bytes(self, document_id: str, relative_name: str, data: bytes) -> str:
        """Write extra files (figure crops) next to the original. Returns storage key."""
        safe_parts = [_safe_filename(p) for p in Path(relative_name).parts]
        dest = self.local_dir / document_id
        for part in safe_parts:
            dest = dest / part
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return f"{document_id}/{'/'.join(safe_parts)}"

    def local_abs_path(self, key: str) -> Path:
        return self.local_dir / key

    async def delete_document(self, s3_key: str) -> bool:
        if self.backend == "local":
            path = self._parse_local_key(s3_key)
            if path.exists():
                path.unlink()
            parent = path.parent
            figures = parent / "figures"
            if figures.exists():
                shutil.rmtree(figures, ignore_errors=True)
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
            return True
        try:
            await asyncio.to_thread(
                self.client.delete_object,
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return True
        except ClientError as e:
            raise Exception(f"Failed to delete from S3: {e}")
    
    async def get_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600,
    ) -> str:
        try:
            url = await asyncio.to_thread(
                self.client.generate_presigned_url,
                "get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": s3_key,
                },
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            raise Exception(f"Failed to generate presigned URL: {e}")
    
    def ensure_bucket_exists(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                # Bucket doesn't exist, create it
                try:
                    if settings.AWS_REGION == "us-east-1":
                        self.client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={
                                "LocationConstraint": settings.AWS_REGION
                            },
                        )
                    return True
                except ClientError:
                    return False
            return False


# Singleton instance
storage_service = StorageService()
