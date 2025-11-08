"""
Test suite for storage service layer.

Tests the StorageBackendService stub implementation.
"""

import unittest

from app.services import StorageBackendService, storage_backend


class TestStorageBackendService(unittest.TestCase):
    """Test cases for StorageBackendService stub implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = StorageBackendService()

    def test_init_default_values(self):
        """Test initialization with default values."""
        service = StorageBackendService()

        self.assertEqual(service.default_expiry, 3600)
        self.assertEqual(service.base_url, "https://minio.example.com")

    def test_generate_upload_url(self):
        """Test presigned URL generation for upload."""
        storage_key = "test-file.txt"
        url, expires_in = self.service.generate_upload_url(storage_key)

        self.assertIsInstance(url, str)
        self.assertIn(storage_key, url)
        self.assertEqual(expires_in, 3600)

    def test_generate_download_url(self):
        """Test presigned URL generation for download."""
        storage_key = "test-file.txt"
        url, expires_in = self.service.generate_download_url(storage_key)

        self.assertIsInstance(url, str)
        self.assertIn(storage_key, url)
        self.assertEqual(expires_in, 3600)

    def test_copy_object(self):
        """Test object copying."""
        result = self.service.copy_object("source.txt", "dest.txt")
        self.assertTrue(result)

    def test_move_object(self):
        """Test object moving."""
        result = self.service.move_object("source.txt", "dest.txt")
        self.assertTrue(result)

    def test_delete_object(self):
        """Test object deletion."""
        result = self.service.delete_object("test.txt")
        self.assertTrue(result)

    def test_object_exists(self):
        """Test object existence check."""
        result = self.service.object_exists("test.txt")
        self.assertTrue(result)

    def test_get_object_metadata(self):
        """Test object metadata retrieval."""
        metadata = self.service.get_object_metadata("test.txt")
        
        self.assertIsInstance(metadata, dict)
        self.assertIn("size", metadata)
        self.assertIn("last_modified", metadata)
        self.assertIn("content_type", metadata)
        self.assertIn("etag", metadata)

    def test_global_storage_backend_instance(self):
        """Test that global storage_backend instance exists."""
        self.assertIsNotNone(storage_backend)
        self.assertIsInstance(storage_backend, StorageBackendService)


if __name__ == "__main__":
    unittest.main()