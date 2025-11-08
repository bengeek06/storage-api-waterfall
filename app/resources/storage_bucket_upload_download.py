"""
storage_bucket_upload_download.py
---------------------------------

Updated upload and download resources for bucket-based architecture.
Supports the new collaborative workflow with buckets, UUIDs, and MinIO integration.

Resources:
    - BucketPresignedUrlResource: Generate presigned URLs for buckets
"""

from datetime import datetime, timezone, timedelta
from flask import request
from flask_restful import Resource
from marshmallow import ValidationError

from app.schemas.storage_schema import (
    PresignedUrlRequestSchema,
    PresignedUrlResponseSchema,
    ErrorResponseSchema,
    SuccessResponseSchema,
)
from app.logger import logger
from app.utils import require_jwt_auth, extract_jwt_data
from app.services.storage_service import storage_backend

# Constants
ACCESS_DENIED = "Access denied"
INVALID_REQUEST_DATA = "Invalid request data"

# Initialize schemas
presigned_request_schema = PresignedUrlRequestSchema()
presigned_response_schema = PresignedUrlResponseSchema()
error_schema = ErrorResponseSchema()
success_schema = SuccessResponseSchema()


class BucketPresignedUrlResource(Resource):
    """Resource for generating presigned URLs for bucket operations."""

    @require_jwt_auth()
    def post(self):
        """
        Generate a presigned URL for uploading to a bucket.

        Request body:
        - bucket_type: Type of bucket
        - bucket_id: UUID of the bucket
        - logical_path: Path for the file within bucket
        - expires_in: Expiration time in seconds (default: 3600, max: 86400)

        Returns:
        - 200: Presigned upload URL
        - 400: Validation error
        - 403: Access denied
        - 500: Server error
        """
        try:
            # Validate request
            data = presigned_request_schema.load(request.get_json())

            # Get current user info
            jwt_data = extract_jwt_data()
            user_id = jwt_data.get("user_id")
            company_id = jwt_data.get("company_id")

            # Check bucket access
            if not self._check_bucket_access(
                data["bucket_type"], data["bucket_id"], user_id, company_id
            ):
                return (
                    error_schema.dump(
                        {"error": "ACCESS_DENIED", "message": ACCESS_DENIED}
                    ),
                    403,
                )

            # Generate object key
            temp_version = (
                1  # This will be updated when file is actually created
            )
            object_key = f"{data['bucket_type']}/{data['bucket_id']}/{data['logical_path']}/{temp_version}"

            # Generate presigned URL using storage backend
            upload_url, actual_expires_in = (
                storage_backend.generate_upload_url(
                    storage_key=object_key, content_type=None
                )
            )

            # Log the action for debugging (non-persistent)
            logger.info(
                f"Generated upload URL for {object_key}, expires in {actual_expires_in}s"
            )

            return (
                presigned_response_schema.dump(
                    {
                        "url": upload_url,
                        "object_key": object_key,
                        "expires_in": actual_expires_in,
                        "expires_at": datetime.now(timezone.utc)
                        + timedelta(seconds=actual_expires_in),
                    }
                ),
                200,
            )

        except ValidationError as e:
            logger.warning(f"Validation error in presigned URL: {e.messages}")
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
            logger.error(
                f"Error generating presigned URL: {str(e)}", exc_info=True
            )
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to generate presigned URL",
                    }
                ),
                500,
            )

    def _check_bucket_access(
        self, bucket_type, bucket_id, user_id, company_id
    ):
        """Check if user has write access to bucket."""
        if bucket_type == "users":
            return bucket_id == user_id
        elif bucket_type == "companies":
            return bucket_id == company_id
        elif bucket_type == "projects":
            # TODO: Implement proper project access control
            return True
        return False
