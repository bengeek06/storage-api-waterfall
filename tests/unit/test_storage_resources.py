"""Unit tests for storage resources API endpoints."""

import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


class TestStorageListResource:
    """Test StorageListResource endpoints."""

    @patch('app.resources.storage.StorageFile.list_directory')
    def test_get_success(self, mock_list_dir, client):
        """Test successful directory listing."""
        mock_file = MagicMock()
        mock_file.filename = "test.txt"
        mock_file.is_directory = False
        mock_file.size = 1024
        mock_file.updated_at = datetime(2025, 11, 6, 10, 0, 0, tzinfo=timezone.utc)
        mock_list_dir.return_value = [mock_file]

        response = client.get('/storage/list?project_id=1&path=/test', 
                            headers={'X-User-ID': '1', 'X-Company-ID': '12345678-1234-1234-1234-123456789abc'})

        assert response.status_code == 200

    def test_get_missing_params(self, client):
        """Test error when missing required parameters."""
        response = client.get('/storage/list',
                            headers={'X-User-ID': '1', 'X-Company-ID': '12345678-1234-1234-1234-123456789abc'})

        assert response.status_code == 400


class TestStorageMkdirResource:
    """Test StorageMkdirResource endpoints."""

    @patch('app.resources.storage.StorageFile.get_by_path')
    @patch('app.resources.storage.StorageFile.create')
    def test_post_success(self, mock_create, mock_get, client):
        """Test successful directory creation."""
        mock_get.return_value = None
        mock_create.return_value = MagicMock()
        
        response = client.post('/storage/mkdir', 
                             data=json.dumps({
                                 'project_id': 1,
                                 'path': '/new_directory'
                             }),
                             content_type='application/json',
                             headers={'X-User-ID': '1', 'X-Company-ID': '12345678-1234-1234-1234-123456789abc'})
        
        assert response.status_code == 201

    @patch('app.resources.storage.StorageFile.get_by_path')
    def test_post_directory_exists(self, mock_get, client):
        """Test error when directory already exists."""
        mock_get.return_value = MagicMock()

        response = client.post('/storage/mkdir',
                             data=json.dumps({
                                 'project_id': 1,
                                 'path': '/existing_directory'
                             }),
                             content_type='application/json',
                             headers={'X-User-ID': '1', 'X-Company-ID': '12345678-1234-1234-1234-123456789abc'})

        assert response.status_code == 409


class TestStorageUploadUrlResource:
    """Test StorageUploadUrlResource endpoints."""

    @patch('app.resources.storage.storage_backend.generate_upload_url')
    def test_post_success(self, mock_generate, client):
        """Test successful upload URL generation."""
        mock_generate.return_value = ("https://minio.test/upload/key", 3600)

        response = client.post('/storage/upload-url',
                             data=json.dumps({
                                 'project_id': 1,
                                 'path': '/upload/test.txt'
                             }),
                             content_type='application/json',
                             headers={'X-User-ID': '1', 'X-Company-ID': '12345678-1234-1234-1234-123456789abc'})

        assert response.status_code == 200


class TestStorageDownloadUrlResource:
    """Test StorageDownloadUrlResource endpoints."""

    @patch('app.resources.storage.StorageFile.get_by_path')
    @patch('app.resources.storage.storage_backend.generate_download_url')
    def test_get_success(self, mock_generate, mock_get, client):
        """Test successful download URL generation."""
        mock_file = MagicMock()
        mock_file.is_directory = False
        mock_file.storage_key = "test_storage_key"
        mock_get.return_value = mock_file

        mock_generate.return_value = ("https://minio.test/download/key", 3600)

        response = client.get('/storage/download-url?project_id=1&path=/test.txt',
                            headers={'X-User-ID': '1', 'X-Company-ID': '12345678-1234-1234-1234-123456789abc'})

        assert response.status_code == 200

    @patch('app.resources.storage.StorageFile.get_by_path')
    def test_get_file_not_found(self, mock_get, client):
        """Test error when file not found."""
        mock_get.return_value = None

        response = client.get('/storage/download-url?project_id=1&path=/missing.txt',
                            headers={'X-User-ID': '1', 'X-Company-ID': '12345678-1234-1234-1234-123456789abc'})

        assert response.status_code == 404


class TestStorageDeleteResource:
    """Test StorageDeleteResource endpoints."""

    @patch('app.resources.storage.StorageFile.get_by_path')
    @patch('app.resources.storage.storage_backend.delete_object')
    def test_delete_success(self, mock_delete_obj, mock_get, client):
        """Test successful file deletion."""
        mock_file = MagicMock()
        mock_file.storage_key = "test_key"
        mock_file.soft_delete = MagicMock()
        mock_get.return_value = mock_file

        mock_delete_obj.return_value = True

        response = client.delete('/storage/delete',
                               data=json.dumps({
                                   'project_id': 1,
                                   'path': '/test.txt'
                               }),
                               content_type='application/json',
                               headers={'X-User-ID': '1', 'X-Company-ID': '12345678-1234-1234-1234-123456789abc'})

        assert response.status_code == 204
