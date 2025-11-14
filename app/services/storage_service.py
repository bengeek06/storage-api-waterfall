"""
storage_service.py
------------------

This module provides a service layer for MinIO/S3 storage operations.
It abstracts the storage backend implementation details.
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from app.logger import logger


class StorageBackendService:
    """
    Service layer for MinIO operations.
    """

    def __init__(self):
        # Configuration
        default_minio_url = "http://localhost:9000"
        minio_url = os.environ.get("MINIO_SERVICE_URL", default_minio_url)
        access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
        self.bucket_name = os.environ.get("MINIO_BUCKET_NAME", "storage")
        self.default_expiry = 3600  # 1 hour

        # Public URL for storage service (not MinIO directly)
        self.public_url = os.environ.get(
            "STORAGE_PUBLIC_URL", "http://localhost:5000"
        )

        # Single MinIO client using hostname from environment
        parsed = urlparse(minio_url)
        minio_endpoint = f"{parsed.hostname}:{parsed.port or 9000}"

        logger.info(
            f"Initializing MinIO client - endpoint: {minio_endpoint}, "
            f"bucket: {self.bucket_name}"
        )

        self.minio_client = Minio(
            minio_endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=(parsed.scheme == "https"),
        )

        # Ensure bucket exists at startup (best-effort)
        # Skip if in testing mode without MinIO available
        if os.environ.get("FLASK_ENV") != "testing":
            try:
                self._ensure_bucket_exists()
            except Exception:  # pylint: disable=broad-exception-caught
                # _ensure_bucket_exists already logs errors; swallow to allow app to start
                pass

    def _ensure_bucket_exists(self):
        """
        Ensure the configured bucket exists, create it if not.
        """
        try:
            logger.debug(f"Checking if bucket '{self.bucket_name}' exists")
            if not self.minio_client.bucket_exists(self.bucket_name):
                logger.info(
                    f"Bucket '{self.bucket_name}' does not exist, creating it..."
                )
                self.minio_client.make_bucket(self.bucket_name)
                logger.info(
                    f"Successfully created bucket '{self.bucket_name}'"
                )
            else:
                logger.info(f"Bucket '{self.bucket_name}' already exists")
        except S3Error as exc:
            logger.error(
                f"Failed to ensure bucket '{self.bucket_name}' exists: {exc}",
                exc_info=True,
            )
            # Don't raise - let the service start, bucket will be created on first use

    def generate_upload_url(
        self,
        storage_key: str,
        content_type: Optional[str] = None,  # pylint: disable=unused-argument
    ) -> Tuple[str, int]:
        """
        Generate a presigned URL for file upload directly to MinIO.

        Args:
            storage_key (str): Unique storage key for the file.
            content_type (str, optional): MIME type of the file.

        Returns:
            tuple: (presigned_url, expires_in_seconds)
        """
        # Ensure bucket exists (in case it was deleted)
        self._ensure_bucket_exists()

        # Generate presigned PUT URL
        presigned_url = self.minio_client.presigned_put_object(
            bucket_name=self.bucket_name,
            object_name=storage_key,
            expires=timedelta(seconds=self.default_expiry),
        )

        return presigned_url, self.default_expiry

    def generate_download_url(
        self, storage_key: str, expires_in: int = None
    ) -> Tuple[str, int]:
        """
        Generate a presigned URL for file download directly from MinIO.

        Args:
            storage_key (str): Storage key of the file.
            expires_in (int, optional): Expiration time in seconds.

        Returns:
            tuple: (presigned_url, expires_in_seconds)
        """
        expiry = expires_in or self.default_expiry

        # Generate presigned GET URL
        presigned_url = self.minio_client.presigned_get_object(
            bucket_name=self.bucket_name,
            object_name=storage_key,
            expires=timedelta(seconds=expiry),
        )

        return presigned_url, expiry

    def get_object(self, storage_key: str):
        """
        Get an object from MinIO for streaming.

        Args:
            storage_key (str): Storage key of the file.

        Returns:
            HTTPResponse: MinIO response object for streaming.
        """
        return self.minio_client.get_object(
            bucket_name=self.bucket_name, object_name=storage_key
        )

    def copy_object(self, _source_key: str, _destination_key: str) -> bool:
        """
        Copy an object in storage.

        Args:
            _source_key (str): Source storage key.
            _destination_key (str): Destination storage key.

        Returns:
            bool: True if successful, False otherwise.
        """
        # In production, this would use boto3 or minio-py to copy objects
        # For now, just return True to simulate success
        return True

    def move_object(self, source_key: str, destination_key: str) -> bool:
        """
        Move an object in storage.

        Args:
            source_key (str): Source storage key.
            destination_key (str): Destination storage key.

        Returns:
            bool: True if successful, False otherwise.
        """
        # In production, this would copy then delete the source
        if self.copy_object(source_key, destination_key):
            return self.delete_object(source_key)
        return False

    def delete_object(self, _storage_key: str) -> bool:
        """
        Delete an object from storage.

        Args:
            _storage_key (str): Storage key of the file to delete.

        Returns:
            bool: True if successful, False otherwise.
        """
        # In production, this would use boto3 or minio-py to delete objects
        # For now, just return True to simulate success
        return True

    def object_exists(self, _storage_key: str) -> bool:
        """
        Check if an object exists in storage.

        Args:
            _storage_key (str): Storage key to check.

        Returns:
            bool: True if exists, False otherwise.
        """
        # In production, this would check if the object exists
        # For now, just return True to simulate existence
        return True

    def get_object_metadata(self, storage_key: str) -> Optional[dict]:
        """
        Get metadata for an object.

        Args:
            storage_key (str): Storage key of the object.

        Returns:
            dict: Object metadata or None if not found.
        """
        # In production, this would return actual metadata
        if self.object_exists(storage_key):
            return {
                "size": 1024,  # Mock size
                "last_modified": datetime.now(timezone.utc),
                "content_type": "application/octet-stream",
                "etag": f"mock-etag-{storage_key}",
            }
        return None


class _LazyStorageBackendProxy:
    """Lazy proxy for StorageBackendService.

    This avoids instantiating the real backend (which performs network I/O)
    at import time. On first attribute access the real backend is created and
    replaced in the module global so subsequent accesses hit the real object.
    """

    def __init__(self):
        self._lock = __import__("threading").Lock()
        self._real = None

    def _init_real(self):
        if self._real is None:
            with self._lock:
                if self._real is None:
                    logger.info(
                        "Initializing lazy StorageBackendService instance"
                    )
                    try:
                        real = StorageBackendService()
                    except Exception:
                        # If initialization fails, keep proxy in place and re-raise
                        logger.exception(
                            "Failed to initialize StorageBackendService"
                        )
                        raise
                    # replace module-level name for future imports/uses
                    globals()["storage_backend"] = real
                    self._real = real

    def __getattr__(self, item):
        self._init_real()
        return getattr(self._real, item)


# Export a proxy instance at module import time so other modules can import
# `storage_backend` without triggering network I/O during import. The proxy
# will instantiate the real backend on first use.
storage_backend = _LazyStorageBackendProxy()
