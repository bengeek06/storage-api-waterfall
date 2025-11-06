"""
test_storage_schemas.py
-----------------------

Unit tests for storage schemas validation.
"""

import pytest
from marshmallow import ValidationError

from app.schemas.storage_schema import (
    UploadRequestSchema,
    MkdirRequestSchema,
    DeleteRequestSchema,
    FileCopyMoveRequestSchema,
    TagRequestSchema,
    PromoteRequestSchema
)


"""
test_storage_schemas.py
-----------------------

Unit tests for storage schemas validation.
"""

import pytest
from marshmallow import ValidationError

from app.schemas.storage_schema import (
    UploadRequestSchema,
    MkdirRequestSchema,
    DeleteRequestSchema,
    FileCopyMoveRequestSchema,
    TagRequestSchema,
    PromoteRequestSchema,
    StorageFileSchema,
    FileVersionSchema
)


class TestUploadRequestSchema:
    """Test cases for UploadRequestSchema."""

    def test_valid_with_project_id(self):
        """Test valid schema with project_id."""
        schema = UploadRequestSchema()
        data = {
            'project_id': 1,
            'path': '/test/file.txt'
        }
        result = schema.load(data)
        assert result['project_id'] == 1
        assert result['path'] == '/test/file.txt'

    def test_valid_with_user_id(self):
        """Test valid schema with user_id."""
        schema = UploadRequestSchema()
        data = {
            'user_id': 123,
            'path': '/user/files/document.pdf'
        }
        result = schema.load(data)
        assert result['user_id'] == 123
        assert result['path'] == '/user/files/document.pdf'

    def test_missing_both_ids_error(self):
        """Test error when both project_id and user_id are missing."""
        schema = UploadRequestSchema()
        data = {'path': '/test/file.txt'}
        
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "Either project_id or user_id must be provided" in str(exc_info.value)

    def test_empty_path_error(self):
        """Test error with empty path."""
        schema = UploadRequestSchema()
        data = {
            'project_id': 1,
            'path': ''
        }
        
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "Path cannot be empty" in str(exc_info.value)


class TestMkdirRequestSchema:
    """Test cases for MkdirRequestSchema."""

    def test_valid_directory_creation(self):
        """Test valid directory creation request."""
        schema = MkdirRequestSchema()
        data = {
            'project_id': 1,
            'path': '/new/directory'
        }
        result = schema.load(data)
        assert result['project_id'] == 1
        assert result['path'] == '/new/directory'

    def test_path_with_double_dot(self):
        """Test error with double dot in path."""
        schema = MkdirRequestSchema()
        data = {
            'project_id': 1,
            'path': '/path/../traversal'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "Path cannot contain '..' sequences" in str(exc_info.value)

    def test_empty_path_error(self):
        """Test error with empty path."""
        schema = MkdirRequestSchema()
        data = {
            'project_id': 1,
            'path': ''
        }
        
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "Path cannot be empty" in str(exc_info.value)


class TestDeleteRequestSchema:
    """Test cases for DeleteRequestSchema."""

    def test_valid_delete_request(self):
        """Test valid delete request."""
        schema = DeleteRequestSchema()
        data = {
            'project_id': 1,
            'path': '/file/to/delete.txt'
        }
        result = schema.load(data)
        assert result['project_id'] == 1
        assert result['path'] == '/file/to/delete.txt'

    def test_with_user_id(self):
        """Test delete request with user_id."""
        schema = DeleteRequestSchema()
        data = {
            'user_id': 456,
            'path': '/user/files/document.pdf'
        }
        result = schema.load(data)
        assert result['user_id'] == 456
        assert result['path'] == '/user/files/document.pdf'

    def test_missing_both_ids_error(self):
        """Test error when both project_id and user_id are missing."""
        schema = DeleteRequestSchema()
        data = {'path': '/test/file.txt'}
        
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "Either project_id or user_id must be provided" in str(exc_info.value)


class TestFileCopyMoveRequestSchema:
    """Test cases for FileCopyMoveRequestSchema."""

    def test_valid_copy_request(self):
        """Test valid copy/move request."""
        schema = FileCopyMoveRequestSchema()
        data = {
            'source_project_id': 1,
            'destination_project_id': 2,
            'source_path': '/source/file.txt',
            'destination_path': '/dest/file.txt'
        }
        result = schema.load(data)
        assert result['source_project_id'] == 1
        assert result['destination_project_id'] == 2

    def test_missing_source_context_error(self):
        """Test error when source context is missing."""
        schema = FileCopyMoveRequestSchema()
        data = {
            'destination_project_id': 2,
            'source_path': '/source/file.txt',
            'destination_path': '/dest/file.txt'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "Either source_project_id or source_user_id must be provided" in str(exc_info.value)

    def test_empty_source_path_error(self):
        """Test error with empty source path."""
        schema = FileCopyMoveRequestSchema()
        data = {
            'source_project_id': 1,
            'destination_project_id': 2,
            'source_path': '',
            'destination_path': '/dest/file.txt'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "Source path cannot be empty" in str(exc_info.value)


class TestTagRequestSchema:
    """Test cases for TagRequestSchema."""

    def test_valid_tag_request(self):
        """Test valid tag request."""
        schema = TagRequestSchema()
        data = {
            'project_id': 1,
            'path': '/file/to/tag.txt',
            'version_number': 1,
            'tag': 'approved'
        }
        result = schema.load(data)
        assert result['tag'] == 'approved'

    def test_invalid_tag_error(self):
        """Test error with invalid tag."""
        schema = TagRequestSchema()
        data = {
            'project_id': 1,
            'path': '/file/to/tag.txt',
            'version_number': 1,
            'tag': 'invalid_tag'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "Tag must be one of:" in str(exc_info.value)

    def test_missing_version_identifier_error(self):
        """Test error when no version identifier is provided."""
        schema = TagRequestSchema()
        data = {
            'project_id': 1,
            'path': '/file/to/tag.txt',
            'tag': 'approved'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "Either version_id or version_number must be provided" in str(exc_info.value)


class TestStorageFileSchema:
    """Test cases for StorageFileSchema."""

    def test_valid_file_data(self, session):
        """Test valid file data."""
        schema = StorageFileSchema(session=session)
        data = {
            'filename': 'test.txt',
            'path': 'documents/test.txt',
            'size': 1024,
            'user_id': 1,
            'is_directory': False
        }
        # Test validation without loading (as it's a unit test)
        errors = schema.validate(data)
        assert errors == {}

    def test_invalid_filename_with_slash(self, session):
        """Test error with invalid filename containing slash."""
        schema = StorageFileSchema(session=session)
        data = {
            'filename': 'invalid/filename.txt',
            'path': 'documents/',
            'size': 1024,
            'user_id': 1
        }
        
        # Test validation errors
        errors = schema.validate(data)
        assert 'filename' in errors

    def test_negative_size_error(self, session):
        """Test error with negative file size."""
        schema = StorageFileSchema(session=session)
        data = {
            'filename': 'test.txt',
            'path': 'documents/',
            'size': -100,
            'user_id': 1
        }
        
        # Test validation errors
        errors = schema.validate(data)
        assert 'size' in errors


class TestFileVersionSchema:
    """Test cases for FileVersionSchema."""

    def test_valid_version_data(self, session):
        """Test valid version data."""
        schema = FileVersionSchema(session=session)
        data = {
            'file_id': 1,
            'version_number': 1,
            'size': 1024,
            'created_by': 1
        }
        # Test validation only  
        errors = schema.validate(data)
        assert errors == {}

    def test_invalid_version_number_error(self, session):
        """Test error with invalid version number."""
        schema = FileVersionSchema(session=session)
        data = {
            'file_id': 1,
            'version_number': 0,
            'size': 1024,
            'created_by': 1
        }
        
        # Test validation errors
        errors = schema.validate(data)
        assert 'version_number' in errors

    def test_invalid_tag_error(self, session):
        """Test error with invalid tag."""
        schema = FileVersionSchema(session=session)
        data = {
            'file_id': 1,
            'version_number': 1,
            'tag': 'invalid_tag',
            'size': 1024,
            'created_by': 1
        }
        
        # Test validation errors
        errors = schema.validate(data)
        assert 'tag' in errors