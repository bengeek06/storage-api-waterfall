"""
storage_admin.py
----------------

Administrative and utility endpoints for storage management.

Resources:
    - FileDeleteResource: Delete files (logical + optional physical)
    - LocksListResource: List locks with filtering
"""

from datetime import datetime, timezone
from flask import request, g
from flask_restful import Resource
from marshmallow import ValidationError, Schema, fields
from minio.error import S3Error

from app.models.db import db
from app.models.storage import StorageFile, Lock, AuditLog, FileVersion
from app.schemas.storage_schema import (
    LockSchema,
    ErrorResponseSchema,
    SuccessResponseSchema,
)
from app.logger import logger
from app.utils import require_jwt_auth, check_bucket_access
from app.services.storage_service import storage_backend

# Constants
ACCESS_DENIED = "Access denied"
INVALID_REQUEST_DATA = "Invalid request data"
FILE_NOT_FOUND = "File not found"

# Schemas
error_schema = ErrorResponseSchema()
success_schema = SuccessResponseSchema()
lock_schema = LockSchema()


class DeleteRequestSchema(Schema):
    """Schema for delete file requests."""

    file_id = fields.String(required=True)
    physical = fields.Boolean(load_default=False)


class LocksListRequestSchema(Schema):
    """Schema for listing locks."""

    bucket_type = fields.String(allow_none=True)
    bucket_id = fields.String(allow_none=True)
    file_id = fields.String(allow_none=True)


delete_request_schema = DeleteRequestSchema()
locks_list_request_schema = LocksListRequestSchema()


class FileDeleteResource(Resource):
    """Resource for deleting files."""

    @require_jwt_auth()
    def delete(self):
        """
        Delete a file (logical delete, optional physical delete).

        Request body:
        - file_id: UUID of the file to delete
        - physical: If true, also delete from MinIO (default: false)

        Returns:
        - 200: File deleted successfully
        - 400: Validation error
        - 403: Access denied
        - 404: File not found
        - 500: Server error
        """
        try:
            # Validate request
            data = delete_request_schema.load(request.get_json())

            # Get current user info
            user_id = g.user_id
            _ = g.company_id  # Not used for this endpoint

            # Find the file
            file_obj = StorageFile.get_by_file_id(data["file_id"])
            if not file_obj:
                return (
                    error_schema.dump(
                        {"error": "FILE_NOT_FOUND", "message": FILE_NOT_FOUND}
                    ),
                    404,
                )

            # Check bucket access (delete permission)
            allowed, error_msg, status_code = check_bucket_access(
                bucket_type=file_obj.bucket_type,
                bucket_id=file_obj.bucket_id,
                action="delete",
            )

            if not allowed:
                return (
                    error_schema.dump(
                        {
                            "error": "ACCESS_DENIED",
                            "message": error_msg or ACCESS_DENIED,
                        }
                    ),
                    status_code,
                )

            # Logical delete - mark as archived
            file_obj.status = "archived"
            file_obj.updated_at = datetime.now(timezone.utc)

            # Physical delete if requested
            physical_deleted = False
            if data.get("physical", False):
                # Get all versions (convert to list to avoid lazy loading issues)
                versions = list(file_obj.versions)
                versions_count = len(versions)

                # Delete all versions from MinIO
                for version in versions:
                    try:
                        storage_backend.delete_object(version.object_key)
                        physical_deleted = True
                    except S3Error as e:
                        logger.warning(
                            f"Failed to delete object {version.object_key}: {e}"
                        )

                # Log the action for audit BEFORE deleting from DB
                AuditLog.log_action(
                    file_id=file_obj.id,
                    action="delete",
                    user_id=user_id,
                    details={
                        "logical_delete": True,
                        "physical_delete": physical_deleted,
                        "versions_count": versions_count,
                    },
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get("User-Agent"),
                )

                # Delete from database (cascade will delete FileVersion and Lock records)
                file_id = file_obj.id
                db.session.delete(file_obj)
                db.session.commit()

                logger.info(
                    f"File {file_id} physically deleted "
                    f"(MinIO objects and DB records removed)"
                )

                return (
                    success_schema.dump(
                        {
                            "message": "File deleted successfully",
                            "data": {
                                "file_id": str(file_id),
                                "logical_delete": True,
                                "physical_delete": physical_deleted,
                            },
                        }
                    ),
                    200,
                )

            # Logical delete only - commit the archived status
            db.session.commit()

            # Log the action for audit
            versions_count = FileVersion.query.filter_by(
                file_id=file_obj.id
            ).count()
            AuditLog.log_action(
                file_id=file_obj.id,
                action="delete",
                user_id=user_id,
                details={
                    "logical_delete": True,
                    "physical_delete": False,
                    "versions_count": versions_count,
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            logger.info(
                f"File {data['file_id']} deleted "
                f"(physical: {physical_deleted})"
            )

            return (
                success_schema.dump(
                    {
                        "message": "File deleted successfully",
                        "data": {
                            "file_id": file_obj.id,
                            "logical_delete": True,
                            "physical_delete": physical_deleted,
                        },
                    }
                ),
                200,
            )

        except ValidationError as e:
            logger.warning(f"Validation error in delete: {e.messages}")
            return (
                error_schema.dump(
                    {
                        "error": "VALIDATION_ERROR",
                        "message": INVALID_REQUEST_DATA,
                        "details": e.messages,
                    }
                ),
                400,
            )

        except (ValueError, TypeError, AttributeError, LookupError) as e:
            logger.error(f"Error deleting file: {str(e)}", exc_info=True)
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to delete file",
                    }
                ),
                500,
            )


class LocksListResource(Resource):
    """Resource for listing locks."""

    @require_jwt_auth()
    def get(self):
        """
        List locks with optional filtering.

        Query parameters:
        - bucket_type: Filter by bucket type (optional)
        - bucket_id: Filter by bucket ID (optional)
        - file_id: Filter by specific file (optional)

        Returns:
        - 200: List of locks
        - 400: Validation error
        - 500: Server error
        """
        try:
            # Validate query parameters
            filters = locks_list_request_schema.load(request.args)

            # Get current user info
            user_id = g.user_id
            _ = g.company_id  # Not used for this endpoint

            # Build query
            query = Lock.query.filter(
                Lock.expires_at.is_(None)  # Active locks only
            )

            # Apply filters
            if filters.get("file_id"):
                query = query.filter_by(file_id=filters["file_id"])

            if filters.get("bucket_type") and filters.get("bucket_id"):
                # Join with StorageFile to filter by bucket
                query = query.join(StorageFile).filter(
                    StorageFile.bucket_type == filters["bucket_type"],
                    StorageFile.bucket_id == filters["bucket_id"],
                )

            # Get locks
            locks = query.all()

            # Filter locks based on access (user can only see locks in buckets they have access to)
            accessible_locks = []
            for lock in locks:
                file_obj = lock.file
                allowed, _, _ = check_bucket_access(
                    bucket_type=file_obj.bucket_type,
                    bucket_id=file_obj.bucket_id,
                    action="read",
                )
                if allowed:
                    accessible_locks.append(lock)

            # Note: No audit log for list operations as there's no specific file_id
            # and AuditLog requires file_id (nullable=False)

            logger.info(
                f"Listed {len(accessible_locks)} locks for user {user_id}"
            )

            return (
                {
                    "status": "success",
                    "data": {
                        "locks": [
                            {
                                "lock_id": str(lock.id),
                                "file_id": str(lock.file_id),
                                "locked_by": str(lock.locked_by),
                                "locked_at": (
                                    lock.created_at.isoformat()
                                    if lock.created_at
                                    else None
                                ),
                                "reason": lock.reason,
                                "lock_type": lock.lock_type,
                            }
                            for lock in accessible_locks
                        ],
                        "total": len(accessible_locks),
                    },
                },
                200,
            )

        except ValidationError as e:
            logger.warning(f"Validation error in list locks: {e.messages}")
            return (
                error_schema.dump(
                    {
                        "error": "VALIDATION_ERROR",
                        "message": "Invalid query parameters",
                        "details": e.messages,
                    }
                ),
                400,
            )

        except (ValueError, TypeError, AttributeError, LookupError) as e:
            logger.error(f"Error listing locks: {str(e)}", exc_info=True)
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to list locks",
                    }
                ),
                500,
            )
