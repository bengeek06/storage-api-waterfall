"""
storage_bucket_upload_download.py
---------------------------------

Upload and download resources for bucket-based architecture.
Supports the collaborative workflow with buckets, UUIDs, and MinIO integration.

Resources:
    - BucketPresignedUrlResource: Generate presigned URLs for upload
    - BucketUploadProxyResource: Upload files via multipart proxy
    - BucketDownloadPresignResource: Generate presigned URLs for download
    - BucketDownloadProxyResource: Stream download via proxy
"""

from io import BytesIO
from datetime import datetime, timezone, timedelta
from flask import request, g, Response
from flask.views import MethodView
from flask_restful import Resource
from marshmallow import ValidationError
from werkzeug.utils import secure_filename

from app.schemas.storage_schema import (
    PresignedUrlRequestSchema,
    PresignedUrlResponseSchema,
    ErrorResponseSchema,
    SuccessResponseSchema,
)
from app.logger import logger
from app.utils import require_jwt_auth, check_bucket_access
from app.services.storage_service import storage_backend
from app.models.storage import StorageFile, FileVersion
from app.models.db import db
from app.models.storage import AuditLog

# Constants
ACCESS_DENIED = "Access denied"
INVALID_REQUEST_DATA = "Invalid request data"
FILE_NOT_FOUND = "File not found"
NO_FILE_PROVIDED = "No file provided in request"

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

            # Get current user info from g (set by @require_jwt_auth decorator)
            user_id = g.user_id
            company_id = g.company_id

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
            object_key = (
                f"{data['bucket_type']}/{data['bucket_id']}/"
                f"{data['logical_path']}/{temp_version}"
            )

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

        except (ValueError, TypeError, AttributeError, LookupError) as e:
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

        if bucket_type == "companies":
            return bucket_id == company_id
        if bucket_type == "projects":
            # Project access control delegated to project service via check_bucket_access()
            return True
        return False


class BucketUploadProxyResource(MethodView):
    """MethodView for uploading files via multipart/form-data proxy.

    Uses MethodView instead of Resource to properly handle multipart/form-data
    which Flask-RESTful doesn't handle well by default.
    """

    decorators = [require_jwt_auth()]

    def post(self):  # pylint: disable=too-many-locals
        """
        Upload a file via multipart proxy (alternative to presigned URL).

        Form data:
        - bucket_type: Type of bucket (users/companies/projects)
        - bucket_id: UUID of the bucket
        - logical_path: Path for the file within bucket
        - file: The file to upload (multipart)

        Returns:
        - 201: File uploaded successfully
        - 400: Validation error or no file
        - 403: Access denied
        - 413: File too large
        - 500: Server error
        """
        try:
            # Get form data
            bucket_type = request.form.get("bucket_type")
            bucket_id = request.form.get("bucket_id")
            logical_path = request.form.get("logical_path")

            # Validate required fields
            if not all([bucket_type, bucket_id, logical_path]):
                return (
                    error_schema.dump(
                        {
                            "error": "MISSING_FIELDS",
                            "message": "bucket_type, bucket_id, and logical_path are required",
                        }
                    ),
                    400,
                )

            # Check if file is in request
            if "file" not in request.files:
                return (
                    error_schema.dump(
                        {"error": "NO_FILE", "message": NO_FILE_PROVIDED}
                    ),
                    400,
                )

            file_obj = request.files["file"]
            if file_obj.filename == "":
                return (
                    error_schema.dump(
                        {
                            "error": "EMPTY_FILENAME",
                            "message": "No file selected",
                        }
                    ),
                    400,
                )

            # Get current user info
            user_id = g.user_id
            _ = g.company_id  # Not used for this endpoint

            # Check bucket access (write permission)
            allowed, error_msg, status_code = check_bucket_access(
                bucket_type=bucket_type, bucket_id=bucket_id, action="write"
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

            # Secure the filename
            filename = secure_filename(file_obj.filename)
            content_type = file_obj.content_type or "application/octet-stream"

            # Find or create the file record
            storage_file = StorageFile.query.filter_by(
                bucket_type=bucket_type,
                bucket_id=bucket_id,
                logical_path=logical_path,
            ).first()

            if not storage_file:
                # Create new file record
                storage_file = StorageFile(
                    bucket_type=bucket_type,
                    bucket_id=bucket_id,
                    logical_path=logical_path,
                    filename=filename,
                    owner_id=user_id,
                    status="approved",
                )
                db.session.add(storage_file)
                db.session.flush()  # Get the file ID

            # Generate next version number
            next_version = storage_file.get_next_version_number()

            # Construct object key
            object_key = (
                f"{bucket_type}/{bucket_id}/{logical_path}/{next_version}"
            )

            # Upload to MinIO directly
            file_data = file_obj.read()
            file_size = len(file_data)

            # Upload using MinIO client
            storage_backend.minio_client.put_object(
                bucket_name=storage_backend.bucket_name,
                object_name=object_key,
                data=BytesIO(file_data),
                length=file_size,
                content_type=content_type,
            )

            # Create version record
            file_version = FileVersion(
                file_id=storage_file.id,
                version_number=next_version,
                object_key=object_key,
                created_by=user_id,
                status="draft",  # Use draft for FileVersion (not approved)
                size=file_size,
                mime_type=content_type,
            )
            db.session.add(file_version)
            db.session.flush()  # Flush to generate file_version.id

            # Update current version
            storage_file.current_version_id = file_version.id
            storage_file.updated_at = datetime.now(timezone.utc)

            db.session.commit()

            # Log the action
            AuditLog.log_action(
                file_id=storage_file.id,
                version_id=file_version.id,
                action="upload",
                user_id=user_id,
                details={
                    "method": "multipart_proxy",
                    "filename": filename,
                    "size": file_size,
                    "content_type": content_type,
                    "object_key": object_key,
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            logger.info(
                f"File uploaded via proxy: {object_key} ({file_size} bytes)"
            )

            return (
                success_schema.dump(
                    {
                        "message": "File uploaded successfully",
                        "data": {
                            "file_id": storage_file.id,
                            "version_id": file_version.id,
                            "version_number": next_version,
                            "object_key": object_key,
                            "size": file_size,
                            "filename": filename,
                        },
                    }
                ),
                201,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            db.session.rollback()
            logger.error(
                f"Error uploading file via proxy: {str(e)}", exc_info=True
            )
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": f"Failed to upload file: {str(e)}",
                    }
                ),
                500,
            )


class BucketDownloadPresignResource(Resource):
    """Resource for generating presigned URLs for download."""

    @require_jwt_auth()
    def get(self):
        """
        Generate a presigned URL for downloading from a bucket.

        Query parameters:
        - bucket_type: Type of bucket (users/companies/projects)
        - bucket_id: UUID of the bucket
        - logical_path: Path for the file within bucket
        - expires_in: Expiration time in seconds (default: 3600, max: 86400)

        Returns:
        - 200: Presigned download URL
        - 400: Validation error
        - 403: Access denied
        - 404: File not found
        - 500: Server error
        """
        try:
            # Validate query parameters
            data = presigned_request_schema.load(request.args)

            # Get current user info from g
            user_id = g.user_id
            _ = g.company_id  # Not used for this endpoint

            # Check bucket access (read permission)
            allowed, error_msg, status_code = check_bucket_access(
                bucket_type=data["bucket_type"],
                bucket_id=data["bucket_id"],
                action="read",
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

            # Find the file in database
            file_obj = StorageFile.query.filter_by(
                bucket_type=data["bucket_type"],
                bucket_id=data["bucket_id"],
                logical_path=data["logical_path"],
            ).first()

            if not file_obj or file_obj.status == "archived":
                return (
                    error_schema.dump(
                        {"error": "FILE_NOT_FOUND", "message": FILE_NOT_FOUND}
                    ),
                    404,
                )

            # Get current version's object key
            if not file_obj.current_version_id:
                return (
                    error_schema.dump(
                        {
                            "error": "NO_VERSION",
                            "message": "File has no current version",
                        }
                    ),
                    404,
                )

            # Get current version object
            current_version = FileVersion.query.get(
                file_obj.current_version_id
            )
            if not current_version:
                return (
                    error_schema.dump(
                        {
                            "error": "VERSION_NOT_FOUND",
                            "message": "Current version not found",
                        }
                    ),
                    404,
                )

            object_key = current_version.object_key
            expires_in = data.get("expires_in", 3600)

            # Generate presigned URL using storage backend
            download_url, actual_expires_in = (
                storage_backend.generate_download_url(
                    storage_key=object_key, expires_in=expires_in
                )
            )

            # Log the action for audit
            AuditLog.log_action(
                file_id=file_obj.id,
                version_id=file_obj.current_version_id,
                action="download",
                user_id=user_id,
                details={
                    "method": "presigned_url",
                    "object_key": object_key,
                    "expires_in": actual_expires_in,
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            logger.info(
                f"Generated download URL for {object_key}, expires in {actual_expires_in}s"
            )

            return (
                presigned_response_schema.dump(
                    {
                        "url": download_url,
                        "object_key": object_key,
                        "expires_in": actual_expires_in,
                        "expires_at": datetime.now(timezone.utc)
                        + timedelta(seconds=actual_expires_in),
                    }
                ),
                200,
            )

        except ValidationError as e:
            logger.warning(
                f"Validation error in download presign: {e.messages}"
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

        except (ValueError, TypeError, AttributeError, LookupError) as e:
            logger.error(
                f"Error generating download URL: {str(e)}", exc_info=True
            )
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to generate download URL",
                    }
                ),
                500,
            )


class BucketDownloadProxyResource(Resource):
    """Resource for downloading files via proxy (streaming)."""

    @require_jwt_auth()
    def get(self):
        """
        Stream download a file via proxy.

        Query parameters:
        - bucket_type: Type of bucket (users/companies/projects)
        - bucket_id: UUID of the bucket
        - logical_path: Path for the file within bucket

        Returns:
        - 200: File stream (application/octet-stream)
        - 400: Validation error
        - 403: Access denied
        - 404: File not found
        - 500: Server error
        """
        try:
            # Validate query parameters
            data = presigned_request_schema.load(request.args)

            # Get current user info from g
            user_id = g.user_id
            _ = g.company_id  # Not used for this endpoint

            # Check bucket access (read permission)
            allowed, error_msg, status_code = check_bucket_access(
                bucket_type=data["bucket_type"],
                bucket_id=data["bucket_id"],
                action="read",
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

            # Find the file in database
            file_obj = StorageFile.query.filter_by(
                bucket_type=data["bucket_type"],
                bucket_id=data["bucket_id"],
                logical_path=data["logical_path"],
            ).first()

            if not file_obj or file_obj.status == "archived":
                return (
                    error_schema.dump(
                        {"error": "FILE_NOT_FOUND", "message": FILE_NOT_FOUND}
                    ),
                    404,
                )

            # Get current version's object key
            if not file_obj.current_version_id:
                return (
                    error_schema.dump(
                        {
                            "error": "NO_VERSION",
                            "message": "File has no current version",
                        }
                    ),
                    404,
                )

            # Get current version object
            current_version = FileVersion.query.get(
                file_obj.current_version_id
            )
            if not current_version:
                return (
                    error_schema.dump(
                        {
                            "error": "VERSION_NOT_FOUND",
                            "message": "Current version not found",
                        }
                    ),
                    404,
                )

            object_key = current_version.object_key

            # Get object from MinIO
            response = storage_backend.get_object(storage_key=object_key)

            # Log the action for audit
            AuditLog.log_action(
                file_id=file_obj.id,
                version_id=file_obj.current_version_id,
                action="download",
                user_id=user_id,
                details={"method": "proxy_stream", "object_key": object_key},
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            logger.info(f"Streaming download for {object_key}")

            # Stream the file
            def generate():
                try:
                    yield from response.stream(amt=8192)
                finally:
                    response.close()
                    response.release_conn()

            # Determine content type
            content_type = (
                current_version.mime_type
                if hasattr(current_version, "mime_type")
                and current_version.mime_type
                else "application/octet-stream"
            )

            return Response(
                generate(),
                mimetype=content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{file_obj.filename}"',
                    "X-File-ID": str(file_obj.id),
                    "X-Version-ID": str(file_obj.current_version_id),
                },
            )

        except ValidationError as e:
            logger.warning(f"Validation error in download proxy: {e.messages}")
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
            logger.error(f"Error downloading file: {str(e)}", exc_info=True)
            return (
                error_schema.dump(
                    {
                        "error": "SERVER_ERROR",
                        "message": "Failed to download file",
                    }
                ),
                500,
            )
