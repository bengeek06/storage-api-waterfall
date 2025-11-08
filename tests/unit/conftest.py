"""
conftest.py for unit tests
---------------------------

Fixtures and configuration specific to unit tests with mocking.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv
import jwt
from app import create_app
from app.models.db import db

# Load test environment
os.environ["FLASK_ENV"] = "testing"
load_dotenv(
    dotenv_path=os.path.join(
        os.path.dirname(__file__), "..", "..", ".env.testing"
    )
)


@pytest.fixture
def app():
    """
    Fixture to create and configure a Flask application for unit testing.
    Uses in-memory SQLite for fast, isolated tests.
    """
    # Set test configuration for unit tests
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["MINIO_SERVICE_URL"] = "http://localhost:9000"  # Mocked anyway

    app = create_app("app.config.TestingConfig")
    app.config.update(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """
    Fixture to create a test client for the Flask application.
    """
    return app.test_client()


@pytest.fixture
def session(app):
    """
    Fixture to provide a database session for tests.
    """
    with app.app_context():
        yield db.session


@pytest.fixture
def auth_headers():
    """Generate mock JWT token headers for unit tests."""
    return {
        "Authorization": "Bearer mock_jwt_token_unit_test",
        "Content-Type": "application/json",
    }


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    user = MagicMock()
    user.id = 1
    user.username = "testuser"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_project():
    """Create a mock project object."""
    project = MagicMock()
    project.id = 1
    project.name = "Test Project"
    project.description = "A test project"
    return project


@pytest.fixture
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


@pytest.fixture
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


@pytest.fixture
def mock_storage_service():
    """Create a mock storage service for unit tests."""
    with patch("app.services.storage_service.StorageService") as mock_service:
        service_instance = MagicMock()
        mock_service.return_value = service_instance

        # Configure default return values for unit tests
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
        service_instance.list_objects.return_value = []
        service_instance.copy_object.return_value = True

        yield service_instance


@pytest.fixture
def mock_jwt_auth():
    """Mock JWT authentication decorators for unit tests."""

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


@pytest.fixture
def mock_db_session():
    """Create a mock database session for unit tests."""
    with patch("app.models.db.db.session") as mock_session:
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        mock_session.rollback = MagicMock()
        mock_session.query = MagicMock()
        yield mock_session


# Helper functions for unit tests
def create_mock_request(json_data=None, args=None):
    """Helper to create mock request objects."""
    mock_request = MagicMock()
    mock_request.get_json.return_value = json_data or {}
    mock_request.args = args or {}
    mock_request.user_id = 1
    return mock_request


def assert_error_response(response, status_code, message_contains=None):
    """Helper to assert error responses in unit tests."""
    assert response.status_code == status_code
    if message_contains:
        data = response.get_json()
        assert message_contains in data.get("message", "")


def assert_success_response(response, status_code=200, data_contains=None):
    """Helper to assert success responses in unit tests."""
    assert response.status_code == status_code
    if data_contains:
        data = response.get_json()
        for key, value in data_contains.items():
            assert data.get(key) == value


def get_init_db_payload():
    """
    Generate a valid payload for full database initialization via /init-db.
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
