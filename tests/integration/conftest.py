"""
conftest.py for integration tests
----------------------------------

Fixtures and configuration specific to integration tests with real services.
"""

import pytest
import time
import os
import uuid
from io import BytesIO
from minio import Minio
from minio.error import S3Error

from app import create_app
from app.config import TestingConfig
from app.models.db import db as database
from app.models.storage import StorageFile, FileVersion, Lock


@pytest.fixture(scope="session")
def app():
    """Create Flask app for testing."""
    app = create_app(TestingConfig)
    return app


@pytest.fixture
def session(app):
    """Create database session for tests."""
    with app.app_context():
        database.create_all()
        yield database.session
        database.session.remove()
        database.drop_all()


# Alias pour compatibilité avec les tests qui utilisent 'db'
@pytest.fixture
def db(session):
    """Alias for session fixture."""
    return session


@pytest.fixture
def client(app):
    """Create Flask test client with database setup."""
    with app.app_context():
        # Create all tables
        database.create_all()
        
        yield app.test_client()
        
        # Cleanup after test
        database.session.remove()
        database.drop_all()


@pytest.fixture(scope="session")
def minio_client():
    """Create a real MinIO client for integration testing."""
    return Minio(
        "localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False,
    )


@pytest.fixture
def test_bucket_name():
    """Name of the test bucket for integration tests."""
    return "storage-test"


@pytest.fixture(autouse=True)
def setup_test_environment(minio_client, test_bucket_name):
    """
    Setup and cleanup test environment for each integration test.
    """
    # Setup: Ensure buckets exist and are clean
    for bucket_name in [test_bucket_name, "storage"]:  # storage est le bucket par défaut
        try:
            if not minio_client.bucket_exists(bucket_name):
                minio_client.make_bucket(bucket_name)

            # Clean up any existing test objects
            objects = minio_client.list_objects(bucket_name, recursive=True)
            for obj in objects:
                if obj.object_name.startswith("integration_test_") or obj.object_name.startswith("users/"):
                    minio_client.remove_object(bucket_name, obj.object_name)
        except S3Error:
            pass  # Bucket might not exist yet

    yield

    # Cleanup: Remove test objects created during the test
    for bucket_name in [test_bucket_name, "storage"]:
        try:
            objects = minio_client.list_objects(bucket_name, recursive=True)
            for obj in objects:
                if obj.object_name.startswith("integration_test_") or obj.object_name.startswith("users/"):
                    minio_client.remove_object(bucket_name, obj.object_name)
        except S3Error:
            pass


def wait_for_minio(minio_client, max_attempts=30, delay=2):
    """
    Wait for MinIO to be ready.
    """
    for attempt in range(max_attempts):
        try:
            # Try to list buckets as a health check
            list(minio_client.list_buckets())
            return True
        except Exception:
            pass

        if attempt < max_attempts - 1:
            time.sleep(delay)

    return False


@pytest.fixture(scope="session", autouse=True)
def ensure_services_ready(minio_client):
    """
    Ensure all required services are ready before running integration tests.
    """
    print("Waiting for MinIO to be ready...")
    assert wait_for_minio(minio_client), "MinIO service not ready"

    print("All services are ready for integration testing")


# Helper functions for integration tests
def upload_test_file(minio_client, bucket_name, object_name, content):
    """Helper to upload a test file directly to MinIO."""
    from io import BytesIO

    if isinstance(content, str):
        content = content.encode()

    minio_client.put_object(
        bucket_name,
        object_name,
        BytesIO(content),
        len(content),
        content_type="text/plain",
    )


def assert_file_exists_in_minio(minio_client, bucket_name, object_name):
    """Helper to assert that a file exists in MinIO."""
    try:
        stat = minio_client.stat_object(bucket_name, object_name)
        return stat is not None
    except S3Error:
        return False


def assert_file_not_exists_in_minio(minio_client, bucket_name, object_name):
    """Helper to assert that a file does not exist in MinIO."""
    try:
        minio_client.stat_object(bucket_name, object_name)
        return False  # File exists when it shouldn't
    except S3Error:
        return True  # File doesn't exist, which is expected


def cleanup_test_objects(
    minio_client, bucket_name, prefix="integration_test_"
):
    """Helper to cleanup test objects from MinIO."""
    try:
        objects = minio_client.list_objects(
            bucket_name, prefix=prefix, recursive=True
        )
        for obj in objects:
            minio_client.remove_object(bucket_name, obj.object_name)
    except S3Error:
        pass


# Pytest markers for integration tests
def pytest_configure(config):
    """Configure pytest markers for integration tests."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )


# Test data fixtures
@pytest.fixture
def test_user_id():
    """Generate a consistent test user ID."""
    return str(uuid.uuid4())


@pytest.fixture
def test_company_id():
    """Generate a consistent test company ID."""
    return str(uuid.uuid4())


@pytest.fixture
def test_creator_id():
    """Generate a separate creator ID for validation tests."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_file(app, test_user_id):
    """Create a sample file in database without MinIO content."""
    with app.app_context():
        file_obj = StorageFile(
            bucket_type='users',
            bucket_id=test_user_id,
            logical_path='test/sample.txt',
            filename='sample.txt',
            owner_id=test_user_id,
            status='approved'
        )
        database.session.add(file_obj)
        database.session.flush()
        
        version = FileVersion(
            file_id=file_obj.id,
            version_number=1,
            object_key=f'users/{test_user_id}/test/sample.txt/1',
            created_by=test_user_id,
            status='draft',
            size=100,
            mime_type='text/plain'
        )
        database.session.add(version)
        database.session.flush()
        
        file_obj.current_version_id = version.id
        database.session.commit()
        
        yield file_obj
        
        # Cleanup
        database.session.delete(file_obj)
        database.session.commit()


@pytest.fixture
def sample_file_with_content(app, minio_client, test_bucket_name, test_user_id):
    """Create a sample file with actual MinIO content."""
    with app.app_context():
        # Create file in database
        file_obj = StorageFile(
            bucket_type='users',
            bucket_id=test_user_id,
            logical_path='test/sample_with_content.txt',
            filename='sample_with_content.txt',
            owner_id=test_user_id,
            status='approved'
        )
        database.session.add(file_obj)
        database.session.flush()
        
        # Create version
        object_key = f'users/{test_user_id}/test/sample_with_content.txt/1'
        content = b'Sample file content for testing'
        
        version = FileVersion(
            file_id=file_obj.id,
            version_number=1,
            object_key=object_key,
            created_by=test_user_id,
            status='draft',
            size=len(content),
            mime_type='text/plain'
        )
        database.session.add(version)
        database.session.flush()
        
        file_obj.current_version_id = version.id
        database.session.commit()
        
        # Upload to MinIO (use "storage" bucket which is the default for the service)
        storage_bucket = "storage"
        try:
            if not minio_client.bucket_exists(storage_bucket):
                minio_client.make_bucket(storage_bucket)
            
            minio_client.put_object(
                storage_bucket,
                object_key,
                BytesIO(content),
                len(content),
                content_type='text/plain'
            )
        except S3Error:
            pass
        
        yield file_obj, content
        
        # Cleanup
        try:
            minio_client.remove_object(storage_bucket, object_key)
        except S3Error:
            pass
        database.session.delete(file_obj)
        database.session.commit()


@pytest.fixture
def locked_file(app, test_user_id):
    """Create a locked file for testing."""
    with app.app_context():
        file_obj = StorageFile(
            bucket_type='users',
            bucket_id=test_user_id,
            logical_path='test/locked.txt',
            filename='locked.txt',
            owner_id=test_user_id,
            status='approved'
        )
        database.session.add(file_obj)
        database.session.flush()
        
        version = FileVersion(
            file_id=file_obj.id,
            version_number=1,
            object_key=f'users/{test_user_id}/test/locked.txt/1',
            created_by=test_user_id,
            status='draft'
        )
        database.session.add(version)
        database.session.flush()
        
        file_obj.current_version_id = version.id
        
        lock = Lock(
            file_id=file_obj.id,
            locked_by=test_user_id,
            lock_type='edit',
            reason='Test lock'
        )
        database.session.add(lock)
        database.session.commit()
        
        yield file_obj
        
        # Cleanup
        database.session.delete(lock)
        database.session.delete(file_obj)
        database.session.commit()
