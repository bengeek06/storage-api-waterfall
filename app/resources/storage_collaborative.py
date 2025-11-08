"""
storage_collaborative.py
------------------------

New REST resources for the collaborative storage system with bucket-based architecture.
Implements endpoints for file operations with buckets, locks, and validation workflow.

Resources:
    - BucketListResource: List files in a bucket
    - FileCopyResource: Copy files between buckets
    - FileLockResource: Lock files for editing
    - FileUnlockResource: Unlock files
    - FileInfoResource: Get comprehensive file information
"""

from datetime import datetime, timezone, timedelta
from flask import request
from flask_restful import Resource
from marshmallow import ValidationError

from app.models.db import db
from app.models.storage import StorageFile, FileVersion, Lock, AuditLog
from app.schemas.storage_schema import (
    FileListRequestSchema,
    FileListResponseSchema,
    FileCopyRequestSchema,
    LockRequestSchema,
    UnlockRequestSchema,
    FileInfoRequestSchema,
    FileInfoResponseSchema,
    StorageFileSchema,
    ErrorResponseSchema,
    SuccessResponseSchema,
)
from app.logger import logger
from app.utils import require_jwt_auth, extract_jwt_data
from app.services.storage_service import storage_backend

# Initialize schemas
file_list_request_schema = FileListRequestSchema()
file_list_response_schema = FileListResponseSchema()
file_copy_request_schema = FileCopyRequestSchema()
lock_request_schema = LockRequestSchema()
unlock_request_schema = UnlockRequestSchema()
file_info_request_schema = FileInfoRequestSchema()
file_info_response_schema = FileInfoResponseSchema()
storage_file_schema = StorageFileSchema()
error_schema = ErrorResponseSchema()
success_schema = SuccessResponseSchema()


class BaseStorageResource:
    """Base class with common functionality for storage resources."""

    def _check_bucket_access(self, bucket, bucket_id, user_id, company_id):
        """
        Check if user has access to the bucket.

        Args:
            bucket (str): Type of bucket (users/companies/projects)
            bucket_id (str): Bucket ID
            user_id (str): Current user ID
            company_id (str): Current user's company ID

        Returns:
            bool: True if access allowed
        """
        if bucket == "users":
            # User can only access their own bucket
            return bucket_id == user_id
        if bucket == "companies":
            # User can access their company's bucket
            return bucket_id == company_id
        if bucket == "projects":
            # For projects, we would need to check project membership
            # For now, allow if user belongs to the same company
            # TODO: Implement proper project access control
            return True

        return False


class BucketListResource(Resource, BaseStorageResource):
    """Resource for listing files in a bucket."""

    @require_jwt_auth()
    def get(self):
        """
        List files in a bucket with pagination.

        Query parameters:
        - bucket_type: Type of bucket (users/companies/projects)
        - bucket_id: UUID of the bucket
        - path: Optional directory path within bucket
        - page: Page number (default: 1)
        - limit: Items per page (default: 50, max: 1000)

        Returns:
        - 200: List of files with pagination info
        - 400: Validation error
        - 403: Access denied
        - 500: Server error
        """
        try:
            # Validate request parameters
            args = file_list_request_schema.load(request.args)

            bucket = args["bucket"]  # OpenAPI uses 'bucket' not 'bucket_type'
            bucket_id = args["id"]  # OpenAPI uses 'id' not 'bucket_id'
            path = args.get("path", "")
            page = args.get("page", 1)
            limit = args.get("limit", 50)

            # Get current user info
            jwt_data = extract_jwt_data()
            user_id = jwt_data.get("user_id")
            company_id = jwt_data.get("company_id")

            # Check access permissions
            if not self._check_bucket_access(
                bucket, bucket_id, user_id, company_id
            ):
                return (
                    error_schema.dump(
                        {
                            "error": "ACCESS_DENIED",
                            "message": "You do not have access to this bucket",
                        }
                    ),
                    403,
                )

            # List files in the bucket
            files, total_count = StorageFile.list_directory(
                bucket_type=bucket,  # Use bucket as bucket_type for model
                bucket_id=bucket_id,
                path=path,
                page=page,
                limit=limit,
            )

            # Calculate pagination info
            total_pages = (total_count + limit - 1) // limit

            # Prepare response
            response_data = {
                "files": files,  # Pass raw objects, let the schema handle serialization
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_items": total_count,
                    "total_pages": total_pages,
                },
            }

            # Log the action
            if files:
                AuditLog.log_action(
                    file_id=files[
                        0
                    ].id,  # Log for first file as representative
                    action="download",  # Directory listing is considered a form of access
                    user_id=user_id,
                    details={
                        "action": "list_directory",
                        "path": path,
                        "count": len(files),
                    },
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get("User-Agent"),
                )

            return file_list_response_schema.dump(response_data), 200

        except ValidationError as e:
            logger.warning(f"Validation error in bucket list: {e.messages}")
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

        except (ValueError, TypeError, LookupError) as e:
            logger.error(
                f"Error listing bucket files: {str(e)}", exc_info=True
            )
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to list files",
                    }
                ),
                500,
            )


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
            jwt_data = extract_jwt_data()
            user_id = jwt_data.get("user_id")
            company_id = jwt_data.get("company_id")

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

                # TODO: Implement MinIO object copy
                # storage_backend.copy_object(version.object_key, new_object_key)

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

                # TODO: Implement MinIO object copy
                # storage_backend.copy_object(current_version.object_key, new_object_key)

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


class FileLockResource(Resource):
    """Resource for locking files."""

    @require_jwt_auth()
    def post(self):
        """
        Lock a file for editing or review.

        Request body:
        - file_id: UUID of the file to lock
        - lock_type: Type of lock (edit/review/admin)
        - reason: Optional reason for the lock
        - expires_in: Optional expiration time in seconds

        Returns:
        - 200: File locked successfully
        - 400: Validation error
        - 403: Access denied
        - 404: File not found
        - 409: File already locked
        - 500: Server error
        """
        try:
            # Validate request
            data = lock_request_schema.load(request.get_json())

            # Get current user info
            jwt_data = extract_jwt_data()
            user_id = jwt_data.get("user_id")

            # Find the file
            file_obj = StorageFile.get_by_file_id(data["file_id"])
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

            # Check if file is already locked
            existing_lock = file_obj.is_locked()
            if existing_lock:
                return (
                    error_schema.dump(
                        {
                            "error": "FILE_LOCKED",
                            "message": f"File is already locked by user {existing_lock.locked_by}",
                            "details": {
                                "lock_id": existing_lock.id,
                                "locked_by": existing_lock.locked_by,
                                "lock_type": existing_lock.lock_type,
                                "created_at": existing_lock.created_at.isoformat(),
                            },
                        }
                    ),
                    409,
                )

            # Create expiration time if specified
            expires_at = None
            if data.get("expires_in"):
                expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=data["expires_in"]
                )

            # Create the lock
            lock = Lock.create(
                file_id=data["file_id"],
                locked_by=user_id,
                lock_type=data.get("lock_type", "edit"),
                reason=data.get("reason"),
                expires_at=expires_at,
            )

            # Log the action
            AuditLog.log_action(
                file_id=data["file_id"],
                action="lock",
                user_id=user_id,
                details={
                    "lock_type": lock.lock_type,
                    "reason": lock.reason,
                    "expires_at": (
                        expires_at.isoformat() if expires_at else None
                    ),
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            return (
                success_schema.dump(
                    {
                        "message": "File locked successfully",
                        "data": {
                            "lock_id": lock.id,
                            "expires_at": (
                                expires_at.isoformat() if expires_at else None
                            ),
                        },
                    }
                ),
                200,
            )

        except ValidationError as e:
            logger.warning(f"Validation error in file lock: {e.messages}")
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
            logger.error(f"Error locking file: {str(e)}", exc_info=True)
            return (
                error_schema.dump(
                    {"error": "SERVER_ERROR", "message": "Failed to lock file"}
                ),
                500,
            )


class FileUnlockResource(Resource):
    """Resource for unlocking files."""

    @require_jwt_auth()
    def post(self):
        """
        Unlock a file.

        Request body:
        - file_id: UUID of the file to unlock
        - force: Whether to force unlock (admin only)

        Returns:
        - 200: File unlocked successfully
        - 400: Validation error
        - 403: Access denied
        - 404: File not found or not locked
        - 500: Server error
        """
        try:
            # Validate request
            data = unlock_request_schema.load(request.get_json())

            # Get current user info
            jwt_data = extract_jwt_data()
            user_id = jwt_data.get("user_id")

            # Find the file
            file_obj = StorageFile.get_by_file_id(data["file_id"])
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

            # Check if file is locked
            lock = file_obj.is_locked()
            if not lock:
                return (
                    error_schema.dump(
                        {
                            "error": "FILE_NOT_LOCKED",
                            "message": "File is not currently locked",
                        }
                    ),
                    404,
                )

            # Check if user can release the lock
            force_unlock = data.get("force", False)
            if not lock.can_be_released_by(user_id) and not force_unlock:
                return (
                    error_schema.dump(
                        {
                            "error": "ACCESS_DENIED",
                            "message": "You do not have permission to unlock this file",
                        }
                    ),
                    403,
                )

            # TODO: If force_unlock, check if user has admin privileges

            # Release the lock
            lock.release(_released_by=user_id)

            # Log the action
            AuditLog.log_action(
                file_id=data["file_id"],
                action="unlock",
                user_id=user_id,
                details={
                    "lock_id": lock.id,
                    "force_unlock": force_unlock,
                    "original_locked_by": lock.locked_by,
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            return (
                success_schema.dump({"message": "File unlocked successfully"}),
                200,
            )

        except ValidationError as e:
            logger.warning(f"Validation error in file unlock: {e.messages}")
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
            logger.error(f"Error unlocking file: {str(e)}", exc_info=True)
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to unlock file",
                    }
                ),
                500,
            )


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
            jwt_data = extract_jwt_data()
            user_id = jwt_data.get("user_id")
            company_id = jwt_data.get("company_id")

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
