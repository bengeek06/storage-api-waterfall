"""
test_storage_service.py
-----------------------

Unit tests for storage service with mock backend.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.services.storage_service import StorageBackendService


class TestStorageBackendService:
    """Test cases for StorageBackendService."""

    @pytest.fixture
    def storage_service(self):
        """Create a StorageBackendService instance for testing."""
        return StorageBackendService()

    def test_init_service(self, storage_service):
        """Test StorageBackendService initialization."""
        assert storage_service.base_url == "https://minio.example.com"
        assert storage_service.default_expiry == 3600

    def test_generate_upload_url_success(self, storage_service):
        """Test successful upload URL generation."""
        storage_key = "project_1/test/file.txt"
        
        url, expires_in = storage_service.generate_upload_url(storage_key)
        
        assert url.startswith("https://minio.example.com/upload/")
        assert storage_key in url
        assert expires_in == 3600

    def test_generate_upload_url_with_content_type(self, storage_service):
        """Test upload URL generation with content type."""
        storage_key = "project_1/test/file.txt"
        content_type = "text/plain"
        
        url, expires_in = storage_service.generate_upload_url(storage_key, content_type)
        
        assert url.startswith("https://minio.example.com/upload/")
        assert storage_key in url
        assert expires_in == 3600

    def test_generate_download_url_success(self, storage_service):
        """Test successful download URL generation."""
        storage_key = "project_1/test/file.txt"
        
        url, expires_in = storage_service.generate_download_url(storage_key)
        
        assert url.startswith("https://minio.example.com/download/")
        assert storage_key in url
        assert expires_in == 3600

    def test_copy_object_success(self, storage_service):
        """Test successful object copying."""
        source_key = "project_1/source/file.txt"
        dest_key = "project_1/dest/file.txt"
        
        result = storage_service.copy_object(source_key, dest_key)
        
        assert result is True

    def test_move_object_success(self, storage_service):
        """Test successful object moving."""
        source_key = "project_1/source/file.txt"
        dest_key = "project_1/dest/file.txt"
        
        # Mock the copy and delete operations
        with patch.object(storage_service, 'copy_object', return_value=True), \
             patch.object(storage_service, 'delete_object', return_value=True):
            
            result = storage_service.move_object(source_key, dest_key)
            
            assert result is True

    def test_move_object_copy_failure(self, storage_service):
        """Test object moving when copy fails."""
        source_key = "project_1/source/file.txt"
        dest_key = "project_1/dest/file.txt"
        
        # Mock copy to fail
        with patch.object(storage_service, 'copy_object', return_value=False):
            result = storage_service.move_object(source_key, dest_key)
            
            assert result is False

    def test_delete_object_success(self, storage_service):
        """Test successful object deletion."""
        storage_key = "project_1/test/file.txt"
        
        result = storage_service.delete_object(storage_key)
        
        assert result is True

    def test_object_exists_success(self, storage_service):
        """Test object existence check."""
        storage_key = "project_1/test/file.txt"
        
        result = storage_service.object_exists(storage_key)
        
        assert result is True

    def test_get_object_metadata_success(self, storage_service):
        """Test successful object metadata retrieval."""
        storage_key = "project_1/test/file.txt"
        
        # Mock object_exists to return True
        with patch.object(storage_service, 'object_exists', return_value=True):
            metadata = storage_service.get_object_metadata(storage_key)
            
            assert metadata is not None
            assert 'size' in metadata
            assert 'last_modified' in metadata
            assert 'content_type' in metadata
            assert 'etag' in metadata
            assert metadata['size'] == 1024
            assert metadata['content_type'] == "application/octet-stream"

    def test_get_object_metadata_not_found(self, storage_service):
        """Test object metadata retrieval when object not found."""
        storage_key = "project_1/nonexistent/file.txt"
        
        # Mock object_exists to return False
        with patch.object(storage_service, 'object_exists', return_value=False):
            metadata = storage_service.get_object_metadata(storage_key)
            
            assert metadata is None


class TestStorageBackendServiceIntegration:
    """Integration-style tests for StorageBackendService."""

    def test_upload_download_url_flow(self):
        """Test a complete upload-download URL flow."""
        service = StorageBackendService()
        storage_key = "project_1/integration/test_file.txt"
        
        # Generate upload URL
        upload_url, upload_expires = service.generate_upload_url(storage_key)
        assert upload_url is not None
        assert upload_expires == 3600
        
        # Generate download URL
        download_url, download_expires = service.generate_download_url(storage_key)
        assert download_url is not None
        assert download_expires == 3600
        
        # URLs should be different but both valid
        assert upload_url != download_url
        assert storage_key in upload_url
        assert storage_key in download_url

    def test_file_lifecycle_operations(self):
        """Test complete file lifecycle operations."""
        service = StorageBackendService()
        source_key = "project_1/lifecycle/source.txt"
        dest_key = "project_1/lifecycle/destination.txt"
        
        # Check existence (should be True in stub)
        assert service.object_exists(source_key) is True
        
        # Get metadata
        metadata = service.get_object_metadata(source_key)
        assert metadata is not None
        
        # Copy object
        copy_result = service.copy_object(source_key, dest_key)
        assert copy_result is True
        
        # Delete object
        delete_result = service.delete_object(source_key)
        assert delete_result is True

    def test_url_format_consistency(self):
        """Test that generated URLs follow consistent format."""
        service = StorageBackendService()
        
        # Test multiple files to ensure consistent URL format
        test_keys = [
            "project_1/test1.txt",
            "project_2/folder/test2.pdf",
            "user_123/documents/test3.docx"
        ]
        
        for key in test_keys:
            upload_url, _ = service.generate_upload_url(key)
            download_url, _ = service.generate_download_url(key)
            
            # Check URL format
            assert upload_url.startswith("https://minio.example.com/upload/")
            assert download_url.startswith("https://minio.example.com/download/")
            assert key in upload_url
            assert key in download_url
            assert "token=" in upload_url
            assert "token=" in download_url