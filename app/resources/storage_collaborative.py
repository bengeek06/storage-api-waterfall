"""
storage_collaborative.py
------------------------

Collaborative storage system resources - Re-exports for backward compatibility.

This module has been split into smaller, focused modules:
- storage_base.py: Base classes
- storage_bucket.py: Bucket operations (list)
- storage_locks.py: Lock/unlock operations

For new code, import directly from the specific modules.
This file maintains backward compatibility by re-exporting all resources.
"""

from datetime import datetime, timezone

from flask import request, g
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy.orm.attributes import flag_modified

from app.models.db import db
from app.models.storage import StorageFile, FileVersion, Lock, AuditLog
from app.schemas.storage_schema import (
    FileCopyRequestSchema,
    FileInfoRequestSchema,
    FileInfoResponseSchema,
    MetadataUpdateRequestSchema,
    StorageFileSchema,
    ErrorResponseSchema,
    SuccessResponseSchema,
)
from app.logger import logger
from app.utils import require_jwt_auth
from app.services.storage_service import storage_backend
from app.resources.storage_base import BaseStorageResource
from app.resources.storage_bucket import BucketListResource
from app.resources.storage_locks import FileLockResource, FileUnlockResource

# Initialize schemas
file_copy_request_schema = FileCopyRequestSchema()
file_info_request_schema = FileInfoRequestSchema()
file_info_response_schema = FileInfoResponseSchema()
metadata_update_request_schema = MetadataUpdateRequestSchema()
storage_file_schema = StorageFileSchema()
error_schema = ErrorResponseSchema()
success_schema = SuccessResponseSchema()

__all__ = [
    "BaseStorageResource",
    "BucketListResource",
    "FileCopyResource",
    "FileLockResource",
    "FileUnlockResource",
    "FileInfoResource",
]


class FileCopyResource(Resource, BaseStorageResource):
    """Resource for copying files between buckets."""

    @require_jwt_auth()
    def post(self):
        """
        Copy a file from one bucket/path to another.

        Request body:
        - source_bucket_type: Source bucket type
        - source_bucket_id: Source bucket ID
        - source_path: Source file path
        - destination_bucket_type: Destination bucket type
        - destination_bucket_id: Destination bucket ID
        - destination_path: Destination file path
        - new_filename: Optional new filename
        - copy_versions: Whether to copy all versions (default: false)

        Returns:
        - 200: File copied successfully
        - 400: Validation error
        - 403: Access denied
        - 404: Source file not found
        - 409: Destination already exists
        - 500: Server error
        """
        try:
            # Validate request
            data = file_copy_request_schema.load(request.get_json())

            # Get current user info
            # Get current user info from g (set by @require_jwt_auth decorator)
            user_id = g.user_id
            company_id = g.company_id

            # Check access to source bucket
            if not self._check_bucket_access(
                data["source_bucket"], data["source_id"], user_id, company_id
            ):
                return (
                    error_schema.dump(
                        {
                            "error": "ACCESS_DENIED",
                            "message": "No access to source bucket",
                        }
                    ),
                    403,
                )

            # Check access to destination bucket
            if not self._check_bucket_access(
                data["target_bucket"], data["target_id"], user_id, company_id
            ):
                return (
                    error_schema.dump(
                        {
                            "error": "ACCESS_DENIED",
                            "message": "No access to destination bucket",
                        }
                    ),
                    403,
                )

            # Find source file
            source_file = StorageFile.get_by_path(
                bucket_type=data["source_bucket"],  # Map to model field
                bucket_id=data["source_id"],
                logical_path=data["source_path"],
            )

            if not source_file:
                return (
                    error_schema.dump(
                        {
                            "error": "FILE_NOT_FOUND",
                            "message": "Source file not found",
                        }
                    ),
                    404,
                )

            # Check if source file is locked
            if source_file.is_locked():
                return (
                    error_schema.dump(
                        {
                            "error": "FILE_LOCKED",
                            "message": "Source file is currently locked",
                        }
                    ),
                    409,
                )

            # Check if destination already exists
            destination_filename = data.get(
                "new_filename", source_file.filename
            )
            existing_file = StorageFile.get_by_path(
                bucket_type=data["target_bucket"],  # Map to model field
                bucket_id=data["target_id"],
                logical_path=data["target_path"],
            )

            if existing_file:
                return (
                    error_schema.dump(
                        {
                            "error": "FILE_EXISTS",
                            "message": "Destination file already exists",
                        }
                    ),
                    409,
                )

            # Perform the copy
            copied_file = self._copy_file(
                source_file=source_file,
                destination_bucket_type=data[
                    "target_bucket"
                ],  # Map to model field
                destination_bucket_id=data["target_id"],
                destination_path=data["target_path"],
                new_filename=destination_filename,
                copy_versions=data.get("copy_versions", False),
                user_id=user_id,
            )

            # Log the action
            AuditLog.log_action(
                file_id=copied_file.id,
                action="copy",
                user_id=user_id,
                details={
                    "source_bucket": f"{data['source_bucket']}/{data['source_id']}",
                    "source_path": data["source_path"],
                    "destination_bucket": f"{data['target_bucket']}/{data['target_id']}",
                    "destination_path": data["target_path"],
                    "copy_versions": data.get("copy_versions", False),
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            return (
                success_schema.dump(
                    {
                        "message": "File copied successfully",
                        "data": {
                            "file_id": copied_file.id,
                            "destination_path": copied_file.logical_path,
                        },
                    }
                ),
                200,
            )

        except ValidationError as e:
            logger.warning(f"Validation error in file copy: {e.messages}")
            return (
                error_schema.dump(
                    {
                        "error": "VALIDATION_ERROR",
                        "message": "Invalid request data",
                        "details": e.messages,
                    }
                ),
                400,
            )

        except (ValueError, TypeError, LookupError) as e:
            logger.error(f"Error copying file: {str(e)}", exc_info=True)
            return (
                error_schema.dump(
                    {"error": "SERVER_ERROR", "message": "Failed to copy file"}
                ),
                500,
            )

    def _copy_file(
        self,
        source_file,
        destination_bucket_type,
        destination_bucket_id,
        destination_path,
        new_filename,
        copy_versions,
        user_id,
    ):
        """
        Copy a file and optionally its versions.

        Args:
            source_file: Source StorageFile object
            destination_bucket_type: Destination bucket type
            destination_bucket_id: Destination bucket ID
            destination_path: Destination path
            new_filename: New filename
            copy_versions: Whether to copy versions
            user_id: User performing the copy

        Returns:
            StorageFile: Copied file object
        """
        # Create new file record
        copied_file = StorageFile.create(
            bucket_type=destination_bucket_type,
            bucket_id=destination_bucket_id,
            logical_path=destination_path,
            filename=new_filename,
            owner_id=user_id,
            mime_type=source_file.mime_type,
            size=source_file.size,
            status="draft",
            tags=source_file.tags.copy() if source_file.tags else {},
            source_file_id=source_file.id,
        )

        if copy_versions:
            # Copy all versions
            for version in source_file.versions:
                # Copy the object in MinIO with new key
                new_object_key = (
                    f"{destination_bucket_type}/{destination_bucket_id}/"
                    f"{destination_path}/{version.version_number}"
                )

                # Copy object in MinIO
                storage_backend.copy_object(version.object_key, new_object_key)

                # Create new version record
                new_version = FileVersion.create(
                    file_id=copied_file.id,
                    version_number=version.version_number,
                    object_key=new_object_key,
                    size=version.size,
                    mime_type=version.mime_type,
                    changelog=f"Copied from {source_file.logical_path}",
                    created_by=user_id,
                    checksum=version.checksum,
                )

                # Set as current version if it was current in source
                if source_file.current_version_id == version.id:
                    copied_file.current_version_id = new_version.id
                    db.session.commit()
        else:
            # Copy only current version
            current_version = source_file.get_current_version()
            if current_version:
                new_object_key = (
                    f"{destination_bucket_type}/{destination_bucket_id}/"
                    f"{destination_path}/1"
                )

                # Copy object in MinIO
                storage_backend.copy_object(
                    current_version.object_key, new_object_key
                )

                new_version = FileVersion.create(
                    file_id=copied_file.id,
                    version_number=1,
                    object_key=new_object_key,
                    size=current_version.size,
                    mime_type=current_version.mime_type,
                    changelog=f"Copied from {source_file.logical_path}",
                    created_by=user_id,
                    checksum=current_version.checksum,
                )

                copied_file.current_version_id = new_version.id
                db.session.commit()

        return copied_file


class FileInfoResource(Resource, BaseStorageResource):
    """Resource for getting comprehensive file information."""

    @require_jwt_auth()
    def get(self):
        """
        Get detailed information about a file including versions, locks, and audit trail.

        Query parameters:
        - bucket_type: Bucket type
        - bucket_id: Bucket ID
        - logical_path: File path
        - include_versions: Include version history (default: false)
        - include_locks: Include lock information (default: false)
        - include_audit: Include audit trail (default: false)

        Returns:
        - 200: File information
        - 400: Validation error
        - 403: Access denied
        - 404: File not found
        - 500: Server error
        """
        try:
            # Validate request parameters
            args = file_info_request_schema.load(request.args)

            # Get current user info
            # Get current user info from g (set by @require_jwt_auth decorator)
            user_id = g.user_id
            company_id = g.company_id

            # Check bucket access
            if not self._check_bucket_access(
                args["bucket"],  # OpenAPI uses 'bucket'
                args["id"],  # OpenAPI uses 'id'
                user_id,
                company_id,
            ):
                return (
                    error_schema.dump(
                        {
                            "error": "ACCESS_DENIED",
                            "message": "No access to this bucket",
                        }
                    ),
                    403,
                )

            # Find the file
            file_obj = StorageFile.get_by_path(
                bucket_type=args["bucket"],  # Map to model field
                bucket_id=args["id"],
                logical_path=args["logical_path"],
            )

            if not file_obj:
                return (
                    error_schema.dump(
                        {
                            "error": "FILE_NOT_FOUND",
                            "message": "File not found",
                        }
                    ),
                    404,
                )

            # Prepare response data
            response_data = {
                "file": file_obj,  # Pass raw object, let schema handle serialization
                "current_version": None,
            }

            # Get current version
            current_version = file_obj.get_current_version()
            if current_version:
                response_data["current_version"] = (
                    current_version  # Pass raw object
                )

            # Include additional data if requested
            if args.get("include_versions", False):
                versions = FileVersion.get_versions_by_file(file_obj.id)
                response_data["versions"] = versions  # Pass raw objects

            if args.get("include_locks", False):
                locks = Lock.get_locks_by_user(
                    user_id, active_only=False
                )  # Get all locks for this user
                # Filter for this file
                file_locks = [
                    lock for lock in locks if lock.file_id == file_obj.id
                ]
                response_data["locks"] = file_locks  # Pass raw objects

            if args.get("include_audit", False):
                audit_logs = AuditLog.get_file_history(file_obj.id, limit=50)
                response_data["audit_logs"] = audit_logs  # Pass raw objects

            # Log the access
            AuditLog.log_action(
                file_id=file_obj.id,
                action="download",  # File info access
                user_id=user_id,
                details={
                    "action": "get_file_info",
                    "include_versions": args.get("include_versions", False),
                    "include_locks": args.get("include_locks", False),
                    "include_audit": args.get("include_audit", False),
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            return file_info_response_schema.dump(response_data), 200

        except ValidationError as e:
            logger.warning(f"Validation error in file info: {e.messages}")
            return (
                error_schema.dump(
                    {
                        "error": "VALIDATION_ERROR",
                        "message": "Invalid request parameters",
                        "details": e.messages,
                    }
                ),
                400,
            )

        except (ValueError, TypeError, AttributeError, LookupError) as e:
            logger.error(f"Error getting file info: {str(e)}", exc_info=True)
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to get file information",
                    }
                ),
                500,
            )

    @require_jwt_auth()
    def patch(self):
        """
        Update file metadata (tags, description).

        Query parameters:
        - bucket: Bucket type (users/companies/projects)
        - id: Bucket ID
        - logical_path: File path

        Request body:
        - tags: Dictionary of tags (optional)
        - description: File description (optional)

        Returns:
        - 200: Metadata updated
        - 400: Validation error
        - 403: Access denied
        - 404: File not found
        - 500: Server error
        """
        try:
            # Validate query parameters
            args = file_info_request_schema.load(request.args)

            # Validate request body
            data = metadata_update_request_schema.load(request.get_json())

            # Get current user info
            user_id = g.user_id
            company_id = g.company_id

            # Check bucket access (write permission)
            if not self._check_bucket_access(
                args["bucket"],
                args["id"],
                user_id,
                company_id,
            ):
                return (
                    error_schema.dump(
                        {
                            "error": "ACCESS_DENIED",
                            "message": "No access to this bucket",
                        }
                    ),
                    403,
                )

            # Find the file
            file_obj = StorageFile.get_by_path(
                bucket_type=args["bucket"],
                bucket_id=args["id"],
                logical_path=args["logical_path"],
            )

            if not file_obj:
                return (
                    error_schema.dump(
                        {
                            "error": "FILE_NOT_FOUND",
                            "message": "File not found",
                        }
                    ),
                    404,
                )

            # Update metadata
            updated_fields = {}
            if "tags" in data:
                file_obj.tags = data["tags"]
                updated_fields["tags"] = data["tags"]

            # Note: 'description' is not a field in StorageFile model
            # If needed, it should be added to the tags dictionary
            if "description" in data:
                if file_obj.tags is None:
                    file_obj.tags = {}
                file_obj.tags["description"] = data["description"]
                updated_fields["description"] = data["description"]
                # Mark the tags field as modified for SQLAlchemy to detect changes
                flag_modified(file_obj, "tags")

            file_obj.updated_at = datetime.now(timezone.utc)
            db.session.commit()

            # Log the action
            AuditLog.log_action(
                file_id=file_obj.id,
                action="upload",  # Metadata update is considered modification
                user_id=user_id,
                details={
                    "action": "update_metadata",
                    "updated_fields": updated_fields,
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            logger.info(f"Updated metadata for file {file_obj.id}")

            return (
                success_schema.dump(
                    {
                        "message": "Metadata updated successfully",
                        "data": {
                            "file_id": file_obj.id,
                            "updated_fields": updated_fields,
                        },
                    }
                ),
                200,
            )

        except ValidationError as e:
            logger.warning(
                f"Validation error in metadata update: {e.messages}"
            )
            return (
                error_schema.dump(
                    {
                        "error": "VALIDATION_ERROR",
                        "message": "Invalid request data",
                        "details": e.messages,
                    }
                ),
                400,
            )

        except (ValueError, TypeError, AttributeError, LookupError) as e:
            db.session.rollback()
            logger.error(f"Error updating metadata: {str(e)}", exc_info=True)
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to update metadata",
                    }
                ),
                500,
            )
