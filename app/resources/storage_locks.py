"""
storage_locks.py
----------------

Lock management for the collaborative storage system.

Resources:
    - FileLockResource: Lock files for editing
    - FileUnlockResource: Unlock files
"""

from datetime import datetime, timezone, timedelta
from flask import request, g
from flask_restful import Resource
from marshmallow import ValidationError

from app.models.storage import StorageFile, Lock, AuditLog
from app.schemas.storage_schema import (
    LockRequestSchema,
    UnlockRequestSchema,
    ErrorResponseSchema,
    SuccessResponseSchema,
)
from app.logger import logger
from app.utils import require_jwt_auth

# Initialize schemas
lock_request_schema = LockRequestSchema()
unlock_request_schema = UnlockRequestSchema()
error_schema = ErrorResponseSchema()
success_schema = SuccessResponseSchema()


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
            # Get current user info from g (set by @require_jwt_auth decorator)
            user_id = g.user_id

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
            # Get current user info from g (set by @require_jwt_auth decorator)
            user_id = g.user_id

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

            # Note: force_unlock currently allowed for lock owner
            # Future: check admin privileges via project service for force_unlock by non-owner

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
