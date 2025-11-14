"""
storage_bucket.py
-----------------

Bucket operations for the collaborative storage system.

Resources:
    - BucketListResource: List files in a bucket
"""

from flask import request, g
from flask_restful import Resource
from marshmallow import ValidationError

from app.models.storage import StorageFile, AuditLog
from app.schemas.storage_schema import (
    FileListRequestSchema,
    FileListResponseSchema,
    ErrorResponseSchema,
)
from app.logger import logger
from app.utils import require_jwt_auth
from app.resources.storage_base import BaseStorageResource

# Initialize schemas
file_list_request_schema = FileListRequestSchema()
file_list_response_schema = FileListResponseSchema()
error_schema = ErrorResponseSchema()


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

            # Get current user info from g (set by @require_jwt_auth decorator)
            user_id = g.user_id
            company_id = g.company_id

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
