"""
routes.py
-----------
Routes for the Flask application.
This module is responsible for registering the routes of the REST API
and linking them to the corresponding resources.

Routes are based on the OpenAPI specification (openapi.yml).
"""

from flask_restful import Api
from app.logger import logger

# System endpoints
from app.resources.version import VersionResource
from app.resources.config import ConfigResource
from app.resources.health import HealthResource

# Storage collaborative resources
from app.resources.storage_collaborative import (
    BucketListResource,
    FileCopyResource,
    FileLockResource,
    FileUnlockResource,
    FileInfoResource,
)

# Storage validation resources
from app.resources.storage_validation import (
    VersionCommitResource,
    VersionApproveResource,
    VersionRejectResource,
    VersionListResource,
)

# Storage upload/download resources
from app.resources.storage_bucket_upload_download import (
    BucketPresignedUrlResource,
)


def register_routes(app):
    """
    Register the REST API routes on the Flask application.

    Routes are registered according to the OpenAPI specification (openapi.yml).

    Args:
        app (Flask): The Flask application instance.
    """
    api = Api(app)

    # System endpoints
    api.add_resource(HealthResource, "/health")
    api.add_resource(VersionResource, "/version")
    api.add_resource(ConfigResource, "/config")

    # File listing and information
    api.add_resource(BucketListResource, "/list")
    api.add_resource(
        FileInfoResource, "/metadata"
    )  # OpenAPI spec uses /metadata not /info

    # Upload operations
    api.add_resource(BucketPresignedUrlResource, "/upload/presign")
    # Note: /upload/proxy endpoint not yet implemented

    # Download operations
    # Note: /download/presign and /download/proxy endpoints not yet implemented

    # File operations
    api.add_resource(FileCopyResource, "/copy")
    api.add_resource(FileLockResource, "/lock")
    api.add_resource(FileUnlockResource, "/unlock")
    # Note: /locks endpoint not yet implemented

    # Version management and validation workflow
    api.add_resource(VersionListResource, "/versions")
    api.add_resource(VersionCommitResource, "/versions/commit")
    # OpenAPI spec routes with version_id parameter
    api.add_resource(
        VersionApproveResource, "/versions/<string:version_id>/approve"
    )
    api.add_resource(
        VersionRejectResource, "/versions/<string:version_id>/reject"
    )

    # Note: /delete endpoint not yet implemented
    # Note: Metadata endpoint path corrected to match OpenAPI spec

    logger.info("Routes registered successfully.")
