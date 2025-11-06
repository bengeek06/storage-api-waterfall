"""
routes.py
-----------
Routes for the Flask application.
# This module is responsible for registering the routes of the REST API
# and linking them to the corresponding resources.
"""

from flask_restful import Api
from app.logger import logger
from app.resources.dummy import DummyResource, DummyListResource
from app.resources.storage import (
    StorageListResource, StorageMkdirResource, StorageUploadUrlResource,
    StorageDownloadUrlResource, StorageCopyResource, StorageMoveResource,
    StorageDeleteResource, StoragePromoteResource, StorageVersionsResource,
    StorageTagResource
)
from app.resources.version import VersionResource
from app.resources.config import ConfigResource
from app.resources.health import HealthResource


def register_routes(app):
    """
    Register the REST API routes on the Flask application.

    Args:
        app (Flask): The Flask application instance.

    This function creates a Flask-RESTful Api instance, adds the resource
    endpoints for managing dummy items, and logs the successful registration
    of routes.
    """
    api = Api(app)

    # System endpoints
    api.add_resource(HealthResource, "/health")
    api.add_resource(VersionResource, "/version")
    api.add_resource(ConfigResource, "/config")

    # Dummy endpoints (examples)
    api.add_resource(DummyListResource, "/dummies")
    api.add_resource(DummyResource, "/dummies/<int:dummy_id>")

    # Storage endpoints
    api.add_resource(StorageListResource, "/storage/list")
    api.add_resource(StorageMkdirResource, "/storage/mkdir")
    api.add_resource(StorageUploadUrlResource, "/storage/upload-url")
    api.add_resource(StorageDownloadUrlResource, "/storage/download-url")
    api.add_resource(StorageCopyResource, "/storage/copy")
    api.add_resource(StorageMoveResource, "/storage/move")
    api.add_resource(StorageDeleteResource, "/storage/delete")
    
    # Version management endpoints
    api.add_resource(StoragePromoteResource, "/storage/promote")
    api.add_resource(StorageVersionsResource, "/storage/versions")
    api.add_resource(StorageTagResource, "/storage/tag")

    logger.info("Routes registered successfully.")
