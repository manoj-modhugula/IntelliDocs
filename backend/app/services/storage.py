"""
S3 Storage service for document management.
"""

import asyncio
import boto3
from botocore.exceptions import ClientError
from typing import BinaryIO

from app.core.config import settings
from app.core.utils import utc_now


class StorageService:
    
    def __init__(self):
        self.client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.bucket_name = settings.S3_BUCKET_NAME
    
    async def upload_document(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str,
        document_id: str,
    ) -> str:
        # Generate unique S3 key
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
        try:
            response = await asyncio.to_thread(
                self.client.get_object,
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return await asyncio.to_thread(response["Body"].read)
        except ClientError as e:
            raise Exception(f"Failed to download from S3: {e}")
    
    async def delete_document(self, s3_key: str) -> bool:
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
