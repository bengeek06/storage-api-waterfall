"""
conftest.py for integration tests
----------------------------------

Fixtures and configuration specific to integration tests with real services.
"""

import pytest
import requests
import time
import os
from minio import Minio
from minio.error import S3Error


@pytest.fixture(scope="session")
def docker_services():
    """
    Fixture to ensure Docker services are running.
    This would typically use pytest-docker or similar.
    """
    # In a real setup, this would start docker-compose services
    # For now, assume services are already running
    yield


@pytest.fixture(scope="session")
def minio_client():
    """Create a real MinIO client for integration testing."""
    return Minio(
        "localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False,
    )


@pytest.fixture(scope="session")
def storage_api_base_url():
    """Base URL for storage service API in integration tests."""
    return "http://localhost:5000"


@pytest.fixture
def auth_headers():
    """Authentication headers for integration test API requests."""
    # Use headers fallback for testing (simpler than JWT)
    return {
        "X-User-ID": "12345678-1234-5678-9abc-123456789012",
        "X-Company-ID": "87654321-4321-8765-cba9-876543210987",
        "Content-Type": "application/json",
    }


@pytest.fixture
def test_bucket_name():
    """Name of the test bucket for integration tests."""
    return "storage-test"


@pytest.fixture(autouse=True)
def setup_test_environment(minio_client, test_bucket_name):
    """
    Setup and cleanup test environment for each integration test.
    """
    # Setup: Ensure bucket exists and is clean
    try:
        if not minio_client.bucket_exists(test_bucket_name):
            minio_client.make_bucket(test_bucket_name)

        # Clean up any existing test objects
        objects = minio_client.list_objects(test_bucket_name, recursive=True)
        for obj in objects:
            if obj.object_name.startswith("integration_test_"):
                minio_client.remove_object(test_bucket_name, obj.object_name)
    except S3Error:
        pass  # Bucket might not exist yet

    yield

    # Cleanup: Remove test objects created during the test
    try:
        objects = minio_client.list_objects(test_bucket_name, recursive=True)
        for obj in objects:
            if obj.object_name.startswith("integration_test_"):
                minio_client.remove_object(test_bucket_name, obj.object_name)
    except S3Error:
        pass


def wait_for_service(url, max_attempts=30, delay=2):
    """
    Wait for a service to be ready by checking its health endpoint.
    """
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                return True
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ):
            pass

        if attempt < max_attempts - 1:
            time.sleep(delay)

    return False


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
def ensure_services_ready(minio_client, storage_api_base_url):
    """
    Ensure all required services are ready before running integration tests.
    """
    print("Waiting for MinIO to be ready...")
    assert wait_for_minio(minio_client), "MinIO service not ready"

    print("Waiting for Storage API to be ready...")
    assert wait_for_service(
        storage_api_base_url
    ), "Storage API service not ready"

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
