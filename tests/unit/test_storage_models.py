"""
test_storage_models.py
----------------------

Unit tests for storage models with mocked dependencies.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from app.models.storage import StorageFile, FileVersion


class TestStorageFile:
    """Test cases for StorageFile model."""

    def test_storage_file_creation(self, session):
        """Test creating a new storage file."""
        file_obj = StorageFile(
            path="/test/file.txt",
            filename="file.txt",
            user_id=1,
            project_id=1,
            size=1024,
            content_type="text/plain",
            storage_key="test_key_123",
            is_directory=False
        )
        
        assert file_obj.path == "/test/file.txt"
        assert file_obj.filename == "file.txt"
        assert file_obj.user_id == 1
        assert file_obj.project_id == 1
        assert file_obj.size == 1024
        assert file_obj.is_directory is False

    @patch('app.models.storage.db.session')
    def test_create_file(self, mock_session):
        """Test file creation with mocked database session."""
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        
        file_obj = StorageFile.create(
            path="/test/newfile.txt",
            filename="newfile.txt",
            user_id=1,
            project_id=1,
            size=2048
        )
        
        assert file_obj.path == "/test/newfile.txt"
        assert file_obj.filename == "newfile.txt"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_get_next_version_number(self, session):
        """Test version number generation."""
        # Create a file with existing versions
        file_obj = StorageFile(
            path="/test/versioned.txt",
            filename="versioned.txt",
            user_id=1,
            storage_key="versioned_key"
        )
        session.add(file_obj)
        session.commit()
        
        # Add some versions
        version1 = FileVersion(
            file_id=file_obj.id,
            version_number=1,
            storage_key="version1_key",
            size=1024,
            created_by=1
        )
        version2 = FileVersion(
            file_id=file_obj.id,
            version_number=2,
            storage_key="version2_key", 
            size=2048,
            created_by=1
        )
        session.add(version1)
        session.add(version2)
        session.commit()
        
        # Test getting next version number
        next_version = file_obj.get_next_version_number()
        assert next_version == 3

    def test_soft_delete(self, session):
        """Test soft delete functionality."""
        file_obj = StorageFile(
            path="/test/todelete.txt",
            filename="todelete.txt",
            user_id=1,
            storage_key="delete_key"
        )
        
        with patch('app.models.storage.db.session.commit') as mock_commit:
            file_obj.soft_delete()
            assert file_obj.is_deleted is True
            mock_commit.assert_called_once()


class TestFileVersion:
    """Test cases for FileVersion model."""

    @patch('app.models.storage.db.session')
    def test_create_version(self, mock_session):
        """Test version creation with mocked database session."""
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        
        version = FileVersion.create(
            file_id=1,
            version_number=1,
            storage_key="version_key_1",
            size=1024,
            comment="Initial version",
            tag="draft",
            created_by=1
        )
        
        assert version.file_id == 1
        assert version.version_number == 1
        assert version.comment == "Initial version"
        assert version.tag == "draft"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_update_tag(self, session):
        """Test tag update functionality."""
        version = FileVersion(
            file_id=1,
            version_number=1,
            storage_key="test_key",
            created_by=1,
            tag="draft"
        )
        
        with patch('app.models.storage.db.session.commit') as mock_commit:
            version.update_tag("approved", "Ready for production")
            assert version.tag == "approved"
            assert version.comment == "Ready for production"
            mock_commit.assert_called_once()