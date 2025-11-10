"""
storage_schema.py
-----------------

Clean Marshmallow schemas for the OpenAPI-compliant storage system.
"""

import uuid
from datetime import datetime, timezone
from marshmallow import Schema, fields, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models.storage import StorageFile, FileVersion, Lock, AuditLog

# Constants for validation
VALID_BUCKET_TYPES = ["users", "companies", "projects"]
VALID_FILE_STATUSES = ["draft", "active", "archived", "deleted"]
VALID_VERSION_STATUSES = [
    "draft",
    "pending_validation",
    "validated",
    "rejected",
]
VALID_LOCK_TYPES = ["edit", "review", "admin"]
VALID_AUDIT_ACTIONS = [
    "upload",
    "download",
    "copy",
    "move",
    "delete",
    "lock",
    "unlock",
    "validate",
    "approve",
    "reject",
    "restore",
]


def validate_uuid(value):
    """Validate UUID format."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError) as exc:
        raise ValidationError("Must be a valid UUID") from exc


def validate_path(value):
    """Validate logical path format."""
    if not value or not value.strip():
        raise ValidationError("Logical path cannot be empty")
    if ".." in value or value.startswith("/"):
        raise ValidationError(
            "Path cannot contain '..' sequences or start with '/'"
        )
    return value.strip()


def validate_filename(value):
    """Validate filename format."""
    if not value or not value.strip():
        raise ValidationError("Filename cannot be empty")
    invalid_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|", "\0"]
    if any(char in value for char in invalid_chars):
        raise ValidationError("Filename contains invalid characters")
    return value.strip()


# Model Schemas


class StorageFileSchema(SQLAlchemyAutoSchema):
    """Schema for StorageFile model."""

    class Meta:  # pylint: disable=missing-class-docstring
        model = StorageFile
        load_instance = True
        include_fk = True
        dump_only = ("id", "created_at", "updated_at")

    bucket_type = fields.String(
        required=True, validate=lambda x: x in VALID_BUCKET_TYPES
    )
    bucket_id = fields.String(required=True, validate=validate_uuid)
    logical_path = fields.String(required=True, validate=validate_path)
    filename = fields.String(required=True, validate=validate_filename)
    owner_id = fields.String(required=True, validate=validate_uuid)
    status = fields.String(validate=lambda x: x in VALID_FILE_STATUSES)
    current_version_id = fields.String(allow_none=True, validate=validate_uuid)
    source_file_id = fields.String(allow_none=True, validate=validate_uuid)
    created_at = fields.DateTime(dump_only=True, format="iso")
    updated_at = fields.DateTime(dump_only=True, format="iso")


class FileVersionSchema(SQLAlchemyAutoSchema):
    """Schema for FileVersion model."""

    class Meta:  # pylint: disable=missing-class-docstring
        model = FileVersion
        load_instance = True
        include_fk = True
        dump_only = ("id", "created_at", "updated_at")

    file_id = fields.String(required=True, validate=validate_uuid)
    object_key = fields.String(required=True)
    status = fields.String(validate=lambda x: x in VALID_VERSION_STATUSES)
    created_by = fields.String(required=True, validate=validate_uuid)
    validated_by = fields.String(allow_none=True, validate=validate_uuid)
    created_at = fields.DateTime(dump_only=True, format="iso")
    updated_at = fields.DateTime(dump_only=True, format="iso")
    validated_at = fields.DateTime(
        dump_only=True, format="iso", allow_none=True
    )


class LockSchema(SQLAlchemyAutoSchema):
    """Schema for Lock model."""

    class Meta:  # pylint: disable=missing-class-docstring
        model = Lock
        load_instance = True
        include_fk = True
        dump_only = ("id", "created_at", "updated_at")

    file_id = fields.String(required=True, validate=validate_uuid)
    locked_by = fields.String(required=True, validate=validate_uuid)
    created_at = fields.DateTime(dump_only=True, format="iso")
    updated_at = fields.DateTime(dump_only=True, format="iso")
    expires_at = fields.DateTime(dump_only=True, format="iso", allow_none=True)
    lock_type = fields.String(validate=lambda x: x in VALID_LOCK_TYPES)


class AuditLogSchema(SQLAlchemyAutoSchema):
    """Schema for AuditLog model."""

    class Meta:  # pylint: disable=missing-class-docstring
        model = AuditLog
        load_instance = True
        include_fk = True
        dump_only = ("id", "created_at")

    file_id = fields.String(required=True, validate=validate_uuid)
    user_id = fields.String(required=True, validate=validate_uuid)
    created_at = fields.DateTime(dump_only=True, format="iso")
    action = fields.String(
        required=True, validate=lambda x: x in VALID_AUDIT_ACTIONS
    )


# Utility Schemas


class PaginationSchema(Schema):
    """Schema for pagination info."""

    page = fields.Integer(required=True)
    limit = fields.Integer(required=True)
    total_items = fields.Integer(required=True)
    total_pages = fields.Integer(required=True)


class ErrorResponseSchema(Schema):
    """Schema for error responses."""

    error = fields.String(required=True)
    message = fields.String(required=True)
    details = fields.Dict(allow_none=True)
    timestamp = fields.DateTime(
        required=True, dump_default=lambda: datetime.now(timezone.utc)
    )


class SuccessResponseSchema(Schema):
    """Schema for success responses."""

    success = fields.Boolean(required=True, dump_default=True)
    message = fields.String(required=True)
    data = fields.Dict(allow_none=True)
    timestamp = fields.DateTime(
        required=True, dump_default=lambda: datetime.now(timezone.utc)
    )


# OpenAPI-compliant API Schemas


class FileListRequestSchema(Schema):
    """Schema for /list endpoint query parameters."""

    bucket = fields.String(
        required=True, validate=lambda x: x in VALID_BUCKET_TYPES
    )
    id = fields.String(required=True, validate=validate_uuid)
    path = fields.String(load_default="")
    page = fields.Integer(load_default=1, validate=lambda x: x >= 1)
    limit = fields.Integer(load_default=50, validate=lambda x: 1 <= x <= 1000)


class FileListResponseSchema(Schema):
    """Schema for /list endpoint response."""

    files = fields.List(fields.Nested(StorageFileSchema))
    pagination = fields.Dict(required=True)


class FileCopyRequestSchema(Schema):
    """Schema for /copy endpoint request body."""

    source_bucket = fields.String(
        required=True, validate=lambda x: x in VALID_BUCKET_TYPES
    )
    source_id = fields.String(required=True, validate=validate_uuid)
    source_path = fields.String(required=True, validate=validate_path)
    target_bucket = fields.String(
        required=True, validate=lambda x: x in VALID_BUCKET_TYPES
    )
    target_id = fields.String(required=True, validate=validate_uuid)
    target_path = fields.String(required=True, validate=validate_path)
    new_filename = fields.String(validate=validate_filename, allow_none=True)
    copy_versions = fields.Boolean(load_default=False)


class LockRequestSchema(Schema):
    """Schema for /lock endpoint request body."""

    file_id = fields.String(required=True, validate=validate_uuid)
    reason = fields.String(allow_none=True)
    lock_type = fields.String(
        validate=lambda x: x in VALID_LOCK_TYPES, load_default="edit"
    )
    expires_in = fields.Integer(allow_none=True, validate=lambda x: x > 0)


class UnlockRequestSchema(Schema):
    """Schema for /unlock endpoint request body."""

    file_id = fields.String(required=True, validate=validate_uuid)
    force = fields.Boolean(load_default=False)


class FileInfoRequestSchema(Schema):
    """Schema for /metadata endpoint query parameters."""

    bucket = fields.String(
        required=True, validate=lambda x: x in VALID_BUCKET_TYPES
    )
    id = fields.String(required=True, validate=validate_uuid)
    logical_path = fields.String(required=True, validate=validate_path)
    include_versions = fields.Boolean(load_default=False)
    include_locks = fields.Boolean(load_default=False)
    include_audit = fields.Boolean(load_default=False)


class FileInfoResponseSchema(Schema):
    """Schema for /metadata endpoint response."""

    file = fields.Nested(StorageFileSchema)
    current_version = fields.Nested(FileVersionSchema, allow_none=True)
    versions = fields.List(fields.Nested(FileVersionSchema), allow_none=True)
    locks = fields.List(fields.Nested(LockSchema), allow_none=True)
    audit_logs = fields.List(fields.Nested(AuditLogSchema), allow_none=True)


class MetadataUpdateRequestSchema(Schema):
    """Schema for /metadata PATCH request body."""

    tags = fields.Dict(allow_none=True)
    description = fields.String(allow_none=True)


# Legacy schemas for APIs not yet migrated


class PresignedUrlRequestSchema(Schema):
    """Schema for presigned URL requests."""

    bucket_type = fields.String(
        required=True, validate=lambda x: x in VALID_BUCKET_TYPES
    )
    bucket_id = fields.String(required=True, validate=validate_uuid)
    logical_path = fields.String(required=True, validate=validate_path)
    expires_in = fields.Integer(
        load_default=3600, validate=lambda x: 300 <= x <= 86400
    )


class PresignedUrlResponseSchema(Schema):
    """Schema for presigned URL responses."""

    url = fields.String(required=True)
    object_key = fields.String(required=True)
    expires_in = fields.Integer(required=True)
    expires_at = fields.DateTime(required=True)


class VersionCommitRequestSchema(Schema):
    """Schema for version commit requests (OpenAPI compliant)."""

    file_id = fields.String(required=True, validate=validate_uuid)
    object_key = fields.String(required=True)
    created_by = fields.String(required=True, validate=validate_uuid)
    changelog = fields.String(allow_none=True)


class VersionListRequestSchema(Schema):
    """Schema for version listing requests (OpenAPI compliant)."""

    file_id = fields.String(required=True, validate=validate_uuid)
    status = fields.String(
        validate=lambda x: x in VALID_VERSION_STATUSES, allow_none=True
    )
    limit = fields.Integer(load_default=50, validate=lambda x: 1 <= x <= 200)
    offset = fields.Integer(load_default=0, validate=lambda x: x >= 0)


class VersionListResponseSchema(Schema):
    """Schema for version listing responses (OpenAPI compliant)."""

    file_id = fields.String(required=True)
    versions = fields.List(fields.Nested(FileVersionSchema))
    total_count = fields.Integer(required=True)


class ValidationRequestSchema(Schema):
    """Schema for validation requests."""

    version_id = fields.String(required=True, validate=validate_uuid)
    action = fields.String(
        required=True, validate=lambda x: x in ["approve", "reject"]
    )
    comment = fields.String(allow_none=True)
