"""
Test suite for storage service layer.

Tests the StorageBackendService class which handles MinIO/S3 operations.
"""

import unittest
from unittest.mock import patch
import os
from datetime import datetime

from app.services.storage_service import StorageBackendService, storage_backend


class TestStorageBackendService(unittest.TestCase):
    """Test cases for StorageBackendService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = StorageBackendService()

    def test_init_default_values(self):
        """Test initialization with default values."""
        service = StorageBackendService()
        
        self.assertEqual(service.bucket_name, "storage")
        self.assertEqual(service.default_expiry, 3600)
        self.assertEqual(service.public_url, "http://localhost:5000")

    @patch.dict(os.environ, {
        "MINIO_SERVICE_URL": "https://minio.example.com:9001",
        "MINIO_ACCESS_KEY": "test_access",
        "MINIO_SECRET_KEY": "test_secret",
        "MINIO_BUCKET_NAME": "test_bucket",
        "STORAGE_PUBLIC_URL": "https://api.example.com"
    })
    @patch('minio.Minio')
    def test_init_with_environment_variables(self, mock_minio):
        """Test initialization with environment variables."""
        StorageBackendService()
        
        # Verify Minio client was initialized with correct parameters
        mock_minio.assert_called_once_with(
            "minio.example.com:9001",
            access_key="test_access",
            secret_key="test_secret",
            secure=True
        )

    @patch.dict(os.environ, {
        "MINIO_SERVICE_URL": "http://localhost:9000"
    })
    @patch('minio.Minio')
    def test_init_with_http_url(self, mock_minio):
        """Test initialization with HTTP URL (secure=False)."""
        StorageBackendService()
        
        # Verify secure=False for HTTP
        mock_minio.assert_called_once_with(
            "localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False
        )

    def test_generate_upload_url_without_content_type(self):
        """Test upload URL generation without content type."""
        storage_key = "test/file.txt"
        
        upload_url, expires_in = self.service.generate_upload_url(storage_key)
        
        self.assertIn("http://localhost:5000/storage/upload/", upload_url)
        self.assertIn(f"storage_key={storage_key}", upload_url)
        self.assertEqual(expires_in, 3600)

    def test_generate_upload_url_with_content_type(self):
        """Test upload URL generation with content type."""
        storage_key = "test/file.pdf"
        content_type = "application/pdf"
        
        upload_url, expires_in = self.service.generate_upload_url(
            storage_key, content_type
        )
        
        self.assertIn("http://localhost:5000/storage/upload/", upload_url)
        self.assertIn(f"storage_key={storage_key}", upload_url)
        self.assertIn(f"content_type={content_type}", upload_url)
        self.assertEqual(expires_in, 3600)

    def test_generate_download_url(self):
        """Test download URL generation."""
        storage_key = "test/file.txt"
        
        download_url, expires_in = self.service.generate_download_url(storage_key)
        
        self.assertIn(f"http://localhost:5000/storage/download/{storage_key}", download_url)
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
        with patch.object(self.service, 'copy_object', return_value=True), \
             patch.object(self.service, 'delete_object', return_value=True):
            result = self.service.move_object(source_key, destination_key)
        
        self.assertTrue(result)

    def test_move_object_copy_failure(self):
        """Test object moving when copy fails."""
        source_key = "source/file.txt"
        destination_key = "dest/file.txt"
        
        # Mock copy to return False
        with patch.object(self.service, 'copy_object', return_value=False):
            result = self.service.move_object(source_key, destination_key)
        
        self.assertFalse(result)

    def test_move_object_delete_failure(self):
        """Test object moving when delete fails."""
        source_key = "source/file.txt"
        destination_key = "dest/file.txt"
        
        # Mock copy to succeed, delete to fail
        with patch.object(self.service, 'copy_object', return_value=True), \
             patch.object(self.service, 'delete_object', return_value=False):
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
        with patch.object(self.service, 'object_exists', return_value=True):
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
        with patch.object(self.service, 'object_exists', return_value=False):
            metadata = self.service.get_object_metadata(storage_key)
        
        self.assertIsNone(metadata)

    def test_global_storage_backend_instance(self):
        """Test that global storage_backend instance is available."""
        self.assertIsInstance(storage_backend, StorageBackendService)


class TestStorageBackendServiceUrlParsing(unittest.TestCase):
    """Test cases for URL parsing edge cases."""

    @patch.dict(os.environ, {
        "MINIO_SERVICE_URL": "https://minio.example.com"  # No port specified
    })
    @patch('minio.Minio')
    def test_init_with_https_no_port(self, mock_minio):
        """Test initialization with HTTPS URL without explicit port."""
        StorageBackendService()
        
        # Should default to port 9000
        mock_minio.assert_called_once_with(
            "minio.example.com:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=True
        )

    @patch.dict(os.environ, {
        "MINIO_SERVICE_URL": "minio.example.com:9001"  # No protocol specified
    })
    @patch('minio.Minio')
    def test_init_with_hostname_port_only(self, mock_minio):
        """Test initialization with hostname:port only."""
        StorageBackendService()
        
        # Should handle missing protocol gracefully
        mock_minio.assert_called_once()


if __name__ == "__main__":
    unittest.main()