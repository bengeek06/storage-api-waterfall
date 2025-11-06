"""
storage_schema.py
-----------------

This module defines Marshmallow schemas for serializing and validating
the storage system's data models.

Classes:
    - StorageFileSchema: Schema for StorageFile model.
    - FileVersionSchema: Schema for FileVersion model.
    - FileListSchema: Schema for directory listing responses.
    - UploadRequestSchema: Schema for file upload requests.
    - MkdirRequestSchema: Schema for directory creation requests.
    - FileCopyMoveRequestSchema: Schema for copy/move operations.
    - PromoteRequestSchema: Schema for file promotion.
    - TagRequestSchema: Schema for version tagging.
    - DeleteRequestSchema: Schema for file deletion.
"""

from marshmallow import Schema, fields, ValidationError, validates, validates_schema
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models.storage import StorageFile, FileVersion

# Constants for validation messages
EMPTY_PATH_ERROR = "Path cannot be empty."
EMPTY_FILENAME_ERROR = "Filename cannot be empty."
INVALID_PATH_SEQUENCE_ERROR = "Path cannot contain '..' sequences."
EMPTY_SOURCE_PATH_ERROR = "Source path cannot be empty."
EMPTY_DESTINATION_PATH_ERROR = "Destination path cannot be empty."


class StorageFileSchema(SQLAlchemyAutoSchema):
    """
    Serialization and validation schema for the StorageFile model.
    """

    class Meta:
        model = StorageFile
        load_instance = True
        include_fk = True
        dump_only = ("id", "storage_key", "created_at", "updated_at", "is_deleted")

    @validates("path")
    def validate_path(self, value, **kwargs):
        """Validate file path format."""
        _ = kwargs
        if not value or not value.strip():
            raise ValidationError(EMPTY_PATH_ERROR)
        
        # Basic path validation
        if '..' in value:
            raise ValidationError(INVALID_PATH_SEQUENCE_ERROR)
        
        if value.startswith('/'):
            value = value[1:]  # Remove leading slash
            
        return value

    @validates("filename")
    def validate_filename(self, value, **kwargs):
        """Validate filename."""
        _ = kwargs
        if not value or not value.strip():
            raise ValidationError(EMPTY_FILENAME_ERROR)
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in value for char in invalid_chars):
            raise ValidationError(f"Filename cannot contain: {', '.join(invalid_chars)}")
        
        return value

    @validates("size")
    def validate_size(self, value, **kwargs):
        """Validate file size."""
        _ = kwargs
        if value < 0:
            raise ValidationError("File size cannot be negative.")
        return value


class FileVersionSchema(SQLAlchemyAutoSchema):
    """
    Serialization and validation schema for the FileVersion model.
    """

    class Meta:
        model = FileVersion
        load_instance = True
        include_fk = True
        dump_only = ("id", "storage_key", "created_at")

    @validates("version_number")
    def validate_version_number(self, value, **kwargs):
        """Validate version number."""
        _ = kwargs
        if value < 1:
            raise ValidationError("Version number must be positive.")
        return value

    @validates("tag")
    def validate_tag(self, value, **kwargs):
        """Validate version tag."""
        _ = kwargs
        if value:
            allowed_tags = ['draft', 'review', 'approved', 'archived', 'rejected']
            if value not in allowed_tags:
                raise ValidationError(f"Tag must be one of: {', '.join(allowed_tags)}")
        return value


class FileListSchema(Schema):
    """Schema for directory listing responses."""
    
    path = fields.String(required=True)
    items = fields.List(fields.Nested(lambda: FileItemSchema()), required=True)


class FileItemSchema(Schema):
    """Schema for individual file items in directory listings."""
    
    name = fields.String(required=True)
    type = fields.String(required=True, validate=lambda x: x in ['file', 'directory'])
    size = fields.Integer(required=True)
    modified_at = fields.DateTime(required=True)


class UploadRequestSchema(Schema):
    """Schema for file upload requests."""
    
    project_id = fields.Integer(required=False, allow_none=True)
    user_id = fields.Integer(required=False, allow_none=True)
    path = fields.String(required=True)
    filename = fields.String(required=False, allow_none=True)
    content_type = fields.String(required=False, allow_none=True)

    @validates("path")
    def validate_path(self, value, **kwargs):
        """Validate upload path."""
        _ = kwargs
        if not value or not value.strip():
            raise ValidationError(EMPTY_PATH_ERROR)
        return value

    @validates_schema
    def validate_context(self, data, **kwargs):
        """Validate that either project_id or user_id is provided."""
        _ = kwargs
        if not data.get('project_id') and not data.get('user_id'):
            raise ValidationError("Either project_id or user_id must be provided.")


class MkdirRequestSchema(Schema):
    """Schema for directory creation requests."""
    
    project_id = fields.Integer(required=True)
    path = fields.String(required=True)

    @validates("path")
    def validate_path(self, value, **kwargs):
        """Validate directory path."""
        _ = kwargs
        if not value or not value.strip():
            raise ValidationError(EMPTY_PATH_ERROR)
        
        if '..' in value:
            raise ValidationError(INVALID_PATH_SEQUENCE_ERROR)
        
        return value


class FileCopyMoveRequestSchema(Schema):
    """Schema for file copy/move operations."""
    
    source_project_id = fields.Integer(required=False, allow_none=True)
    source_user_id = fields.Integer(required=False, allow_none=True)
    destination_project_id = fields.Integer(required=False, allow_none=True)
    destination_user_id = fields.Integer(required=False, allow_none=True)
    source_path = fields.String(required=True)
    destination_path = fields.String(required=True)

    @validates("source_path")
    def validate_source_path(self, value, **kwargs):
        """Validate source path."""
        _ = kwargs
        if not value or not value.strip():
            raise ValidationError(EMPTY_SOURCE_PATH_ERROR)
        return value

    @validates("destination_path")
    def validate_destination_path(self, value, **kwargs):
        """Validate destination path."""
        _ = kwargs
        if not value or not value.strip():
            raise ValidationError(EMPTY_DESTINATION_PATH_ERROR)
        return value

    @validates_schema
    def validate_contexts(self, data, **kwargs):
        """Validate source and destination contexts."""
        _ = kwargs
        # Validate source context
        if not data.get('source_project_id') and not data.get('source_user_id'):
            raise ValidationError("Either source_project_id or source_user_id must be provided.")
        
        # Validate destination context
        if not data.get('destination_project_id') and not data.get('destination_user_id'):
            raise ValidationError("Either destination_project_id or destination_user_id must be provided.")


class PromoteRequestSchema(Schema):
    """Schema for file promotion (personal → project)."""
    
    project_id = fields.Integer(required=True)
    user_id = fields.Integer(required=True)
    source_path = fields.String(required=True)
    destination_path = fields.String(required=True)
    comment = fields.String(required=False, allow_none=True)

    @validates("source_path")
    def validate_source_path(self, value, **kwargs):
        """Validate source path."""
        _ = kwargs
        if not value or not value.strip():
            raise ValidationError(EMPTY_SOURCE_PATH_ERROR)
        return value

    @validates("destination_path")
    def validate_destination_path(self, value, **kwargs):
        """Validate destination path."""
        _ = kwargs
        if not value or not value.strip():
            raise ValidationError(EMPTY_DESTINATION_PATH_ERROR)
        return value


class TagRequestSchema(Schema):
    """Schema for version tagging requests."""
    
    project_id = fields.Integer(required=True)
    path = fields.String(required=True)
    version_id = fields.String(required=False, allow_none=True)
    version_number = fields.Integer(required=False, allow_none=True)
    tag = fields.String(required=True)
    comment = fields.String(required=False, allow_none=True)

    @validates("path")
    def validate_path(self, value, **kwargs):
        """Validate file path."""
        _ = kwargs
        if not value or not value.strip():
            raise ValidationError(EMPTY_PATH_ERROR)
        return value

    @validates("tag")
    def validate_tag(self, value, **kwargs):
        """Validate tag value."""
        _ = kwargs
        allowed_tags = ['draft', 'review', 'approved', 'archived', 'rejected']
        if value not in allowed_tags:
            raise ValidationError(f"Tag must be one of: {', '.join(allowed_tags)}")
        return value

    @validates_schema
    def validate_version_identifier(self, data, **kwargs):
        """Validate that either version_id or version_number is provided."""
        _ = kwargs
        if not data.get('version_id') and not data.get('version_number'):
            raise ValidationError("Either version_id or version_number must be provided.")


class DeleteRequestSchema(Schema):
    """Schema for file deletion requests."""
    
    project_id = fields.Integer(required=False, allow_none=True)
    user_id = fields.Integer(required=False, allow_none=True)
    path = fields.String(required=True)

    @validates("path")
    def validate_path(self, value, **kwargs):
        """Validate file path."""
        _ = kwargs
        if not value or not value.strip():
            raise ValidationError(EMPTY_PATH_ERROR)
        return value

    @validates_schema
    def validate_context(self, data, **kwargs):
        """Validate that either project_id or user_id is provided."""
        _ = kwargs
        if not data.get('project_id') and not data.get('user_id'):
            raise ValidationError("Either project_id or user_id must be provided.")


class PresignedUrlResponseSchema(Schema):
    """Schema for presigned URL responses."""
    
    url = fields.String(required=True)
    expires_in = fields.Integer(required=True)


class VersionListSchema(Schema):
    """Schema for version listing responses."""
    
    file = fields.String(required=True)
    versions = fields.List(fields.Nested(FileVersionSchema), required=True)