"""
Test suite for services/__init__.py

Tests the legacy storage service implementation.
"""

import unittest
from unittest.mock import patch
import os
from datetime import datetime

from app.services import StorageBackendService, storage_backend


class TestLegacyStorageBackendService(unittest.TestCase):
    """Test cases for legacy StorageBackendService in __init__.py."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = StorageBackendService()

    def test_init_default_values(self):
        """Test initialization with default values."""
        service = StorageBackendService()

        self.assertEqual(service.base_url, "https://minio.example.com")
        self.assertEqual(service.default_expiry, 3600)

    @patch.dict(
        os.environ, {"MINIO_PUBLIC_URL": "https://storage.example.com"}
    )
    def test_init_with_environment_variable(self):
        """Test initialization with custom environment variable."""
        service = StorageBackendService()

        self.assertEqual(service.base_url, "https://storage.example.com")
        self.assertEqual(service.default_expiry, 3600)

    def test_generate_upload_url_without_content_type(self):
        """Test upload URL generation without content type."""
        storage_key = "test/file.txt"

        upload_url, expires_in = self.service.generate_upload_url(storage_key)

        self.assertIn(
            f"https://minio.example.com/upload/{storage_key}", upload_url
        )
        self.assertIn("token=", upload_url)
        self.assertEqual(expires_in, 3600)

    def test_generate_upload_url_with_content_type(self):
        """Test upload URL generation with content type."""
        storage_key = "test/file.pdf"
        content_type = "application/pdf"

        # Note: This implementation doesn't actually use content_type
        upload_url, expires_in = self.service.generate_upload_url(
            storage_key, content_type
        )

        self.assertIn(
            f"https://minio.example.com/upload/{storage_key}", upload_url
        )
        self.assertIn("token=", upload_url)
        self.assertEqual(expires_in, 3600)

    def test_generate_download_url(self):
        """Test download URL generation."""
        storage_key = "test/file.txt"

        download_url, expires_in = self.service.generate_download_url(
            storage_key
        )

        self.assertIn(
            f"https://minio.example.com/download/{storage_key}", download_url
        )
        self.assertIn("token=", download_url)
        self.assertEqual(expires_in, 3600)

    def test_copy_object(self):
        """Test object copying."""
        source_key = "source/file.txt"
        destination_key = "dest/file.txt"

        result = self.service.copy_object(source_key, destination_key)

        self.assertTrue(result)

    def test_move_object_success(self):
        """Test successful object moving."""
        source_key = "source/file.txt"
        destination_key = "dest/file.txt"

        # Mock both copy and delete to return True
        with (
            patch.object(self.service, "copy_object", return_value=True),
            patch.object(self.service, "delete_object", return_value=True),
        ):
            result = self.service.move_object(source_key, destination_key)

        self.assertTrue(result)

    def test_move_object_copy_failure(self):
        """Test object moving when copy fails."""
        source_key = "source/file.txt"
        destination_key = "dest/file.txt"

        # Mock copy to return False
        with patch.object(self.service, "copy_object", return_value=False):
            result = self.service.move_object(source_key, destination_key)

        self.assertFalse(result)

    def test_move_object_delete_failure(self):
        """Test object moving when delete fails."""
        source_key = "source/file.txt"
        destination_key = "dest/file.txt"

        # Mock copy to succeed, delete to fail
        with (
            patch.object(self.service, "copy_object", return_value=True),
            patch.object(self.service, "delete_object", return_value=False),
        ):
            result = self.service.move_object(source_key, destination_key)

        self.assertFalse(result)

    def test_delete_object(self):
        """Test object deletion."""
        storage_key = "test/file.txt"

        result = self.service.delete_object(storage_key)

        self.assertTrue(result)

    def test_object_exists(self):
        """Test object existence check."""
        storage_key = "test/file.txt"

        result = self.service.object_exists(storage_key)

        self.assertTrue(result)

    def test_get_object_metadata_exists(self):
        """Test getting metadata for existing object."""
        storage_key = "test/file.txt"

        # Mock object_exists to return True
        with patch.object(self.service, "object_exists", return_value=True):
            metadata = self.service.get_object_metadata(storage_key)

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["size"], 1024)
        self.assertIn("last_modified", metadata)
        self.assertIsInstance(metadata["last_modified"], datetime)
        self.assertEqual(metadata["content_type"], "application/octet-stream")
        self.assertEqual(metadata["etag"], f"mock-etag-{storage_key}")

    def test_get_object_metadata_not_exists(self):
        """Test getting metadata for non-existent object."""
        storage_key = "test/nonexistent.txt"

        # Mock object_exists to return False
        with patch.object(self.service, "object_exists", return_value=False):
            metadata = self.service.get_object_metadata(storage_key)

        self.assertIsNone(metadata)

    def test_global_legacy_storage_backend_instance(self):
        """Test that global storage_backend instance is available."""
        self.assertIsInstance(storage_backend, StorageBackendService)


if __name__ == "__main__":
    unittest.main()
