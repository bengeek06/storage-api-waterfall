"""
storage_validation.py
---------------------

REST resources for the validation workflow in the collaborative storage system.
Implements endpoints for version management, approval, and rejection.

Resources:
    - VersionCommitResource: Commit a version for validation
    - VersionApproveResource: Approve a version
    - VersionRejectResource: Reject a version
    - VersionListResource: List versions with filtering
"""

from datetime import datetime, timezone
from flask import request
from flask_restful import Resource
from marshmallow import ValidationError

from app.models.db import db
from app.models.storage import StorageFile, FileVersion, AuditLog
from app.schemas.storage_schema import (
    ValidationRequestSchema,
    VersionCommitRequestSchema,
    VersionListRequestSchema,
    VersionListResponseSchema,
    FileVersionSchema,
    ErrorResponseSchema,
    SuccessResponseSchema,
)
from app.logger import logger
from app.utils import require_jwt_auth, extract_jwt_data

# Constants
INVALID_REQUEST_DATA = "Invalid request data"
VERSION_NOT_FOUND = "Version not found"
ACCESS_DENIED = "Access denied"
SERVER_ERROR = "Server error"

# Initialize schemas
version_commit_schema = VersionCommitRequestSchema()
validation_request_schema = ValidationRequestSchema()
version_list_request_schema = VersionListRequestSchema()
version_list_response_schema = VersionListResponseSchema()
file_version_schema = FileVersionSchema()
error_schema = ErrorResponseSchema()
success_schema = SuccessResponseSchema()


class VersionCommitResource(Resource):
    """Resource for committing versions for validation."""

    @require_jwt_auth()
    def post(self):
        """
        Commit a version to make it available for validation.

        Request body:
        - file_id: UUID of the file
        - object_key: MinIO object key for the new version
        - created_by: UUID of the user creating the version
        - changelog: Optional description of changes

        Returns:
        - 200: Version committed successfully
        - 400: Validation error
        - 403: Access denied
        - 404: File not found
        - 500: Server error
        """
        try:
            # Validate request
            data = version_commit_schema.load(request.get_json())

            # Get current user info
            jwt_data = extract_jwt_data()
            user_id = jwt_data.get("user_id")

            # Verify user_id matches created_by (security check)
            if data["created_by"] != user_id:
                return (
                    error_schema.dump(
                        {
                            "error": "ACCESS_DENIED",
                            "message": "You can only commit versions created by yourself",
                        }
                    ),
                    403,
                )

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

            # Create new version
            next_version_number = file_obj.get_next_version_number()
            version = FileVersion(
                file_id=data["file_id"],
                version_number=next_version_number,
                object_key=data["object_key"],
                created_by=user_id,
                changelog=data.get("changelog"),
                status="pending_validation"
            )
            
            db.session.add(version)
            db.session.commit()

            # Log the action
            AuditLog.log_action(
                file_id=data["file_id"],
                version_id=version.id,
                action="validate",
                user_id=user_id,
                details={
                    "action": "commit_for_validation",
                    "version_number": version.version_number,
                    "changelog": version.changelog,
                    "object_key": data["object_key"],
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            return (
                success_schema.dump(
                    {
                        "message": "Version committed for validation successfully",
                        "data": {
                            "version_id": version.id,
                            "status": version.status,
                            "version_number": version.version_number,
                            "file_id": data["file_id"],
                        },
                    }
                ),
                201,
            )

        except ValidationError as e:
            logger.warning(f"Validation error in version commit: {e.messages}")
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

        except Exception as e:
            logger.error(f"Error committing version: {str(e)}", exc_info=True)
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to commit version",
                    }
                ),
                500,
            )


class VersionApproveResource(Resource):
    """Resource for approving versions."""

    @require_jwt_auth()
    def post(self, version_id):
        """
        Approve a version that is pending validation.

        URL parameter:
        - version_id: UUID of the version to approve (from URL path)

        Request body:
        - comment: Optional approval comment

        Returns:
        - 200: Version approved successfully
        - 400: Validation error
        - 403: Access denied
        - 404: Version not found
        - 409: Version not in pending status
        - 500: Server error
        """
        try:
            # Get request data (comment only)
            request_data = request.get_json() or {}
            comment = request_data.get("comment")

            # Get current user info
            jwt_data = extract_jwt_data()
            user_id = jwt_data.get("user_id")

            # Find the version
            version = db.session.get(FileVersion, version_id)
            if not version:
                return (
                    error_schema.dump(
                        {
                            "error": "VERSION_NOT_FOUND",
                            "message": VERSION_NOT_FOUND,
                        }
                    ),
                    404,
                )

            # Check if user can validate this version
            if not version.can_be_validated_by(user_id):
                return (
                    error_schema.dump(
                        {
                            "error": "CANNOT_VALIDATE",
                            "message": "You cannot validate this version (either not pending or you created it)",
                        }
                    ),
                    403,
                )

            # Approve the version
            version.approve(validated_by=user_id, comment=comment)

            # Log the action
            AuditLog.log_action(
                file_id=version.file_id,
                version_id=version_id,
                action="approve",
                user_id=user_id,
                details={
                    "version_number": version.version_number,
                    "comment": comment,
                    "approved_by": user_id,
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            return (
                success_schema.dump(
                    {
                        "message": "Version approved successfully",
                        "data": {
                            "version_id": version.id,
                            "status": version.status,
                            "file_id": version.file_id,
                            "is_current": version.file.current_version_id
                            == version.id,
                        },
                    }
                ),
                200,
            )

        except ValidationError as e:
            logger.warning(
                f"Validation error in version approve: {e.messages}"
            )
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

        except Exception as e:
            logger.error(f"Error approving version: {str(e)}", exc_info=True)
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to approve version",
                    }
                ),
                500,
            )


class VersionRejectResource(Resource):
    """Resource for rejecting versions."""

    @require_jwt_auth()
    def post(self, version_id):
        """
        Reject a version that is pending validation.

        URL parameter:
        - version_id: UUID of the version to reject (from URL path)

        Request body:
        - comment: Optional rejection reason

        Returns:
        - 200: Version rejected successfully
        - 400: Validation error
        - 403: Access denied
        - 404: Version not found
        - 409: Version not in pending status
        - 500: Server error
        """
        try:
            # Get request data (comment only)
            request_data = request.get_json() or {}
            comment = request_data.get("comment")

            # Get current user info
            jwt_data = extract_jwt_data()
            user_id = jwt_data.get("user_id")

            # Find the version
            version = db.session.get(FileVersion, version_id)
            if not version:
                return (
                    error_schema.dump(
                        {
                            "error": "VERSION_NOT_FOUND",
                            "message": VERSION_NOT_FOUND,
                        }
                    ),
                    404,
                )

            # Check if user can validate this version
            if not version.can_be_validated_by(user_id):
                return (
                    error_schema.dump(
                        {
                            "error": "CANNOT_VALIDATE",
                            "message": "You cannot validate this version (either not pending or you created it)",
                        }
                    ),
                    403,
                )

            # Reject the version
            version.reject(validated_by=user_id, comment=comment)

            # Log the action
            AuditLog.log_action(
                file_id=version.file_id,
                version_id=version_id,
                action="reject",
                user_id=user_id,
                details={
                    "version_number": version.version_number,
                    "comment": comment,
                    "rejected_by": user_id,
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            return (
                success_schema.dump(
                    {
                        "message": "Version rejected successfully",
                        "data": {
                            "version_id": version.id,
                            "status": version.status,
                            "file_id": version.file_id,
                            "rejection_reason": comment,
                        },
                    }
                ),
                200,
            )

        except ValidationError as e:
            logger.warning(f"Validation error in version reject: {e.messages}")
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

        except Exception as e:
            logger.error(f"Error rejecting version: {str(e)}", exc_info=True)
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to reject version",
                    }
                ),
                500,
            )


class VersionListResource(Resource):
    """Resource for listing versions with filtering."""

    @require_jwt_auth()
    def get(self):
        """
        List versions for a file with optional filtering.

        Query parameters:
        - file_id: UUID of the file (required)
        - status: Optional status filter (draft/pending_validation/validated/rejected)
        - limit: Number of versions to return (default: 50, max: 200)
        - offset: Offset for pagination (default: 0)

        Returns:
        - 200: List of versions
        - 400: Validation error
        - 404: File not found
        - 500: Server error
        """
        try:
            # Validate request parameters
            args = version_list_request_schema.load(request.args)

            # Get current user info
            jwt_data = extract_jwt_data()
            user_id = jwt_data.get("user_id")

            # Find the file to check existence
            file_obj = StorageFile.get_by_file_id(args["file_id"])
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

            # Build query
            query = FileVersion.query.filter_by(file_id=args["file_id"])

            # Apply status filter if provided
            if args.get("status"):
                query = query.filter_by(status=args["status"])

            # Get total count
            total_count = query.count()

            # Apply pagination
            limit = args.get("limit", 50)
            offset = args.get("offset", 0)
            versions = (
                query.order_by(FileVersion.version_number.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            # Prepare response
            response_data = {
                "file_id": args["file_id"],
                "versions": versions,  # Pass raw objects, let schema handle serialization
                "total_count": total_count,
            }

            # Log the action
            AuditLog.log_action(
                file_id=args["file_id"],
                action="download",  # Version listing is a form of access
                user_id=user_id,
                details={
                    "action": "list_versions",
                    "status_filter": args.get("status"),
                    "count": len(versions),
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            return version_list_response_schema.dump(response_data), 200

        except ValidationError as e:
            logger.warning(f"Validation error in version list: {e.messages}")
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

        except Exception as e:
            logger.error(f"Error listing versions: {str(e)}", exc_info=True)
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to list versions",
                    }
                ),
                500,
            )
