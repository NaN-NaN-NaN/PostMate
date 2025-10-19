"""
PostMate Backend - Storage Service

Purpose: Unified storage interface supporting both local file system (dev) and AWS S3 (production).
Handles image uploads, PDF storage, and Textract JSON results.

Testing:
    # Local mode (USE_LOCAL_STORAGE=true)
    storage = StorageService()
    await storage.save_image("test.jpg", image_bytes, "image/jpeg")
    url = await storage.get_presigned_url("test.jpg")

    # S3 mode (USE_LOCAL_STORAGE=false)
    # Automatically uses boto3 to interact with S3

AWS Deployment Notes:
    - S3 bucket created by deploy_aws.sh script
    - Uses IAM role for ECS tasks (no hardcoded credentials)
    - Presigned URLs expire based on S3_PRESIGNED_URL_EXPIRY setting
    - Enable versioning on S3 bucket for production
    - Consider S3 lifecycle policies to archive old documents
"""

import os
import logging
from typing import Optional
from datetime import datetime, timedelta
import aiofiles
import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    Storage service with dual backend support: local file system or S3
    """

    def __init__(self):
        self.use_local = settings.USE_LOCAL_STORAGE

        if self.use_local:
            # Local storage setup
            self.base_path = settings.LOCAL_STORAGE_PATH
            self._ensure_local_directories()
            logger.info(f"Storage: Using local file system at {self.base_path}")

        else:
            # S3 setup
            self.bucket_name = settings.S3_BUCKET_NAME
            self.s3_client = boto3.client(
                's3',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            logger.info(f"Storage: Using S3 bucket {self.bucket_name}")

    def _ensure_local_directories(self):
        """Create local storage directories if they don't exist"""
        directories = [
            self.base_path,
            os.path.join(self.base_path, "images"),
            os.path.join(self.base_path, "pdfs"),
            os.path.join(self.base_path, "textract"),
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    # =========================================================================
    # IMAGE STORAGE
    # =========================================================================

    async def save_image(
        self,
        key: str,
        content: bytes,
        content_type: str = "image/jpeg"
    ) -> str:
        """
        Save image to storage

        Args:
            key: Storage key (path) for the image
            content: Image binary content
            content_type: MIME type

        Returns:
            URL or path to the saved image
        """
        if self.use_local:
            return await self._save_local(key, content, "images")
        else:
            return await self._save_s3(
                key=f"{settings.S3_PREFIX_IMAGES}{key}",
                content=content,
                content_type=content_type
            )

    async def get_image(self, key: str) -> bytes:
        """
        Retrieve image from storage

        Args:
            key: Storage key

        Returns:
            Image binary content
        """
        if self.use_local:
            return await self._get_local(key, "images")
        else:
            return await self._get_s3(f"{settings.S3_PREFIX_IMAGES}{key}")

    # =========================================================================
    # PDF STORAGE
    # =========================================================================

    async def save_pdf(
        self,
        key: str,
        content: bytes
    ) -> str:
        """
        Save PDF to storage

        Args:
            key: Storage key for the PDF
            content: PDF binary content

        Returns:
            URL or path to the saved PDF
        """
        if self.use_local:
            return await self._save_local(key, content, "pdfs")
        else:
            return await self._save_s3(
                key=f"{settings.S3_PREFIX_PDFS}{key}",
                content=content,
                content_type="application/pdf"
            )

    async def get_pdf(self, key: str) -> bytes:
        """
        Retrieve PDF from storage

        Args:
            key: Storage key

        Returns:
            PDF binary content
        """
        if self.use_local:
            return await self._get_local(key, "pdfs")
        else:
            return await self._get_s3(f"{settings.S3_PREFIX_PDFS}{key}")

    # =========================================================================
    # TEXTRACT JSON STORAGE
    # =========================================================================

    async def save_textract_json(
        self,
        key: str,
        content: bytes
    ) -> str:
        """
        Save Textract JSON result to storage

        Args:
            key: Storage key for the JSON
            content: JSON binary content

        Returns:
            URL or path to the saved JSON
        """
        if self.use_local:
            return await self._save_local(key, content, "textract")
        else:
            return await self._save_s3(
                key=f"{settings.S3_PREFIX_TEXTRACT}{key}",
                content=content,
                content_type="application/json"
            )

    async def get_textract_json(self, key: str) -> bytes:
        """
        Retrieve Textract JSON from storage

        Args:
            key: Storage key

        Returns:
            JSON binary content
        """
        if self.use_local:
            return await self._get_local(key, "textract")
        else:
            return await self._get_s3(f"{settings.S3_PREFIX_TEXTRACT}{key}")

    # =========================================================================
    # PRESIGNED URLS
    # =========================================================================

    async def get_presigned_url(
        self,
        key: str,
        expiry: Optional[int] = None
    ) -> str:
        """
        Generate presigned URL for downloading a file

        Args:
            key: Storage key (full key with prefix)
            expiry: URL expiry in seconds (default from settings)

        Returns:
            Presigned URL (S3) or local file path
        """
        if self.use_local:
            # For local storage, return file path
            # In production, you might serve these via nginx
            return f"file://{self.base_path}/{key}"

        else:
            # Generate S3 presigned URL
            expiry = expiry or settings.S3_PRESIGNED_URL_EXPIRY

            try:
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': self.bucket_name,
                        'Key': key
                    },
                    ExpiresIn=expiry
                )
                return url

            except ClientError as e:
                logger.error(f"Failed to generate presigned URL for {key}: {e}")
                raise

    # =========================================================================
    # DELETE
    # =========================================================================

    async def delete_file(self, key: str) -> bool:
        """
        Delete a file from storage

        Args:
            key: Storage key (full key with prefix)

        Returns:
            True if deleted successfully
        """
        if self.use_local:
            file_path = os.path.join(self.base_path, key)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Deleted local file: {file_path}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Failed to delete local file {file_path}: {e}")
                return False

        else:
            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
                logger.info(f"Deleted S3 object: {key}")
                return True

            except ClientError as e:
                logger.error(f"Failed to delete S3 object {key}: {e}")
                return False

    # =========================================================================
    # INTERNAL METHODS - LOCAL STORAGE
    # =========================================================================

    async def _save_local(
        self,
        key: str,
        content: bytes,
        subdirectory: str
    ) -> str:
        """
        Save file to local file system

        Args:
            key: File key (relative path)
            content: File content
            subdirectory: Subdirectory (images, pdfs, textract)

        Returns:
            Local file path
        """
        # Create directory structure if needed
        file_path = os.path.join(self.base_path, subdirectory, key)
        directory = os.path.dirname(file_path)
        os.makedirs(directory, exist_ok=True)

        # Write file asynchronously
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)

        logger.info(f"Saved file locally: {file_path}")
        return file_path

    async def _get_local(
        self,
        key: str,
        subdirectory: str
    ) -> bytes:
        """
        Read file from local file system

        Args:
            key: File key
            subdirectory: Subdirectory

        Returns:
            File content
        """
        file_path = os.path.join(self.base_path, subdirectory, key)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        async with aiofiles.open(file_path, 'rb') as f:
            content = await f.read()

        return content

    # =========================================================================
    # INTERNAL METHODS - S3 STORAGE
    # =========================================================================

    async def _save_s3(
        self,
        key: str,
        content: bytes,
        content_type: str
    ) -> str:
        """
        Save file to S3

        Args:
            key: S3 key (full path with prefix)
            content: File content
            content_type: MIME type

        Returns:
            S3 URL
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content,
                ContentType=content_type,
                ServerSideEncryption='AES256',  # Enable encryption
            )

            # Return S3 URL
            url = f"s3://{self.bucket_name}/{key}"
            logger.info(f"Saved file to S3: {url}")
            return url

        except ClientError as e:
            logger.error(f"Failed to save to S3: {e}")
            raise

    async def _get_s3(self, key: str) -> bytes:
        """
        Read file from S3

        Args:
            key: S3 key (full path with prefix)

        Returns:
            File content
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            content = response['Body'].read()
            return content

        except ClientError as e:
            logger.error(f"Failed to read from S3: {e}")
            raise

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    async def file_exists(self, key: str) -> bool:
        """
        Check if file exists in storage

        Args:
            key: Storage key (full key with prefix)

        Returns:
            True if file exists
        """
        if self.use_local:
            file_path = os.path.join(self.base_path, key)
            return os.path.exists(file_path)

        else:
            try:
                self.s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
                return True

            except ClientError:
                return False

    async def get_file_size(self, key: str) -> Optional[int]:
        """
        Get file size in bytes

        Args:
            key: Storage key (full key with prefix)

        Returns:
            File size in bytes, or None if file doesn't exist
        """
        if self.use_local:
            file_path = os.path.join(self.base_path, key)
            if os.path.exists(file_path):
                return os.path.getsize(file_path)
            return None

        else:
            try:
                response = self.s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
                return response['ContentLength']

            except ClientError:
                return None
