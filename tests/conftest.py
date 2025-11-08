"""
conftest.py
-----------

Enhanced pytest configuration with additional fixtures for storage testing.
"""

import os
from pytest import fixture
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv
import jwt
from app import create_app
from app.models.db import db

os.environ["FLASK_ENV"] = "testing"
load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env.test")
)


@fixture(autouse=True)
def cleanup_db_connections():
    """
    Auto-use fixture to clean up database connections after each test.
    This prevents ResourceWarnings by ensuring all connections are properly closed.
    """
    yield
    # Cleanup after each test
    try:
        # Force close any remaining sessions
        if hasattr(db.session, "close"):
            db.session.close()

        # Remove session registry
        if hasattr(db.session, "remove"):
            db.session.remove()

        # Dispose of the engine connection pool
        if hasattr(db, "engine") and hasattr(db.engine, "dispose"):
            db.engine.dispose()

        # Force garbage collection to clean up any remaining connections
        import gc

        gc.collect()
    except Exception:
        # Ignore cleanup errors but don't let them fail tests
        pass


@fixture
def app():
    """
    Fixture to create and configure a Flask application for testing.
    This fixture sets up the application context, initializes the database,
    and ensures that the database is created before tests run and dropped after tests complete.
    """
    # Set test configuration for storage
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["MINIO_SERVICE_URL"] = "http://localhost:9000"

    app = create_app("app.config.TestingConfig")
    app.config.update(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "pool_pre_ping": True,
                "pool_recycle": 300,
            },
        }
    )

    with app.app_context():
        db.create_all()
        yield app
        # Properly close all database connections to avoid ResourceWarnings
        try:
            db.session.close()
            db.session.remove()
            db.engine.dispose()
        finally:
            db.drop_all()


@fixture
def client(app):
    """
    Fixture to create a test client for the Flask application.
    This client can be used to simulate HTTP requests to the application.
    """
    return app.test_client()


@fixture
def session(app):
    """
    Fixture to provide a database session for tests.
    This session is scoped to the application context and can be used
    to interact with the database during tests.
    """
    with app.app_context():
        session = db.session
        try:
            yield session
        finally:
            # Ensure proper cleanup of the session
            try:
                session.rollback()
            except Exception:
                pass
            finally:
                session.close()


def get_init_db_payload():
    """
    Generate a valid payload for full database initialization via /init-db.
    Returns a dictionary containing data for company, organization_unit, position, and user.
    """
    return {
        "company": {"name": "TestCorp", "description": "A test company"},
        "organization_unit": {
            "name": "Direction",
            "description": "Direction générale",
        },
        "position": {"title": "CEO", "description": "Chief Executive Officer"},
        "user": {
            "email": "admin@testcorp.com",
            "first_name": "Alice",
            "last_name": "Admin",
            "password": "supersecret",
        },
    }


def create_jwt_token(company_id, user_id):
    """Helper function to create a JWT token for testing."""
    jwt_secret = os.environ.get("JWT_SECRET", "test_secret")
    payload = {"company_id": company_id, "user_id": user_id}
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


# Additional fixtures for storage testing


@fixture
def auth_headers():
    """Generate mock JWT token headers."""
    return {
        "Authorization": "Bearer mock_jwt_token",
        "Content-Type": "application/json",
    }


@fixture
def mock_user():
    """Create a mock user object."""
    user = MagicMock()
    user.id = 1
    user.username = "testuser"
    user.email = "test@example.com"
    return user


@fixture
def mock_project():
    """Create a mock project object."""
    project = MagicMock()
    project.id = 1
    project.name = "Test Project"
    project.description = "A test project"
    return project


@fixture
def mock_storage_file():
    """Create a mock storage file object."""
    storage_file = MagicMock()
    storage_file.id = 1
    storage_file.filename = "test.txt"
    storage_file.filepath = "/test/file.txt"
    storage_file.is_directory = False
    storage_file.size = 1024
    storage_file.storage_key = "project_1/abc123/test/file.txt"
    storage_file.project_id = 1
    storage_file.user_id = 1
    storage_file.is_deleted = False
    storage_file.tags = ["test", "file"]
    return storage_file


@fixture
def mock_file_version():
    """Create a mock file version object."""
    version = MagicMock()
    version.id = 1
    version.version_number = 1
    version.storage_key = "project_1/abc123/test/file.txt"
    version.size = 1024
    version.checksum = "abc123def456"
    version.content_type = "text/plain"
    version.file_id = 1
    version.created_by = 1
    return version


@fixture
def mock_storage_service():
    """Create a mock storage service."""
    with patch("app.services.storage_service.StorageService") as mock_service:
        service_instance = MagicMock()
        mock_service.return_value = service_instance

        # Configure default return values
        service_instance.generate_upload_url.return_value = (
            "https://minio.test/upload",
            3600,
        )
        service_instance.generate_download_url.return_value = (
            "https://minio.test/download",
            3600,
        )
        service_instance.delete_object.return_value = True
        service_instance.object_exists.return_value = True
        service_instance.get_object_metadata.return_value = {
            "size": 1024,
            "etag": "abc123",
            "last_modified": "2025-11-06T10:00:00Z",
            "content_type": "text/plain",
        }

        yield service_instance


@fixture
def mock_jwt_auth():
    """Mock JWT authentication decorators."""

    def mock_require_jwt_auth(f):
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapper

    def mock_check_access_required(f):
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapper

    with (
        patch("app.resources.storage.require_jwt_auth", mock_require_jwt_auth),
        patch(
            "app.resources.storage.check_access_required",
            mock_check_access_required,
        ),
    ):
        yield


# Helper functions for tests
def create_mock_request(json_data=None, args=None):
    """Helper to create mock request objects."""
    mock_request = MagicMock()
    mock_request.get_json.return_value = json_data or {}
    mock_request.args = args or {}
    mock_request.user_id = 1
    return mock_request


def assert_error_response(response, status_code, message_contains=None):
    """Helper to assert error responses."""
    assert response.status_code == status_code
    if message_contains:
        data = response.get_json()
        assert message_contains in data.get("message", "")


def assert_success_response(response, status_code=200, data_contains=None):
    """Helper to assert success responses."""
    assert response.status_code == status_code
    if data_contains:
        data = response.get_json()
        for key, value in data_contains.items():
            assert data.get(key) == value
