"""
test_integration_storage.py
----------------------------

Integration tests for storage service with real MinIO backend.
Run with: pytest tests/integration/ -v
"""

import pytest
import json
import uuid
from minio.error import S3Error


class TestStorageIntegration:
    """Integration tests with real MinIO backend."""

    def test_service_health(self, client):
        """Test that storage service is healthy."""
        response = client.get("/health")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "healthy"

    def test_minio_connectivity(self, minio_client, test_bucket_name):
        """Test direct MinIO connectivity."""
        bucket_name = f"{test_bucket_name}-connectivity-test"

        try:
            # Clean up if exists
            if minio_client.bucket_exists(bucket_name):
                objects = minio_client.list_objects(
                    bucket_name, recursive=True
                )
                for obj in objects:
                    minio_client.remove_object(bucket_name, obj.object_name)
                minio_client.remove_bucket(bucket_name)

            # Create bucket
            minio_client.make_bucket(bucket_name)
            assert minio_client.bucket_exists(bucket_name)

            # Upload test file
            from .conftest import upload_test_file

            test_content = "Hello, MinIO integration test!"
            object_name = "integration_test_connectivity.txt"

            upload_test_file(
                minio_client, bucket_name, object_name, test_content
            )

            # Verify upload
            response = minio_client.get_object(bucket_name, object_name)
            assert response.read().decode() == test_content

            # Clean up
            minio_client.remove_object(bucket_name, object_name)
            minio_client.remove_bucket(bucket_name)

        except S3Error as e:
            pytest.fail(f"MinIO integration test failed: {e}")

    def test_storage_upload_presign_flow(self, client):
        """Test presigned upload URL generation via API."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        upload_data = {
            "bucket_type": "projects",
            "bucket_id": test_project_id,
            "logical_path": "integration/test_file.txt",
        }

        # Add auth headers for testing with valid UUIDs
        headers = {
            "Content-Type": "application/json",
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        response = client.post(
            "/upload/presign",
            data=json.dumps(upload_data),
            headers=headers,
        )

        assert response.status_code == 200
        upload_response = json.loads(response.data)
        assert "url" in upload_response
        assert "expires_in" in upload_response
        assert upload_response["expires_in"] > 0

    def test_storage_download_presign_flow(
        self, client, minio_client, test_bucket_name
    ):
        """Test presigned download URL generation via API."""
        from .conftest import upload_test_file

        object_name = "projects/test-project-123/integration/test_download.txt"
        test_content = "Integration test download content"

        upload_test_file(
            minio_client, test_bucket_name, object_name, test_content
        )

        # Test with non-existent file (requires database file_id)
        response = client.get(
            "/download/presign?file_id=non-existent-file-id"
        )
        assert response.status_code == 404

    def test_storage_list_files(self, client):
        """Test file listing via API."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        # Add auth headers for testing with valid UUIDs
        headers = {
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        response = client.get(
            f"/list?bucket=projects&id={test_project_id}", headers=headers
        )

        assert response.status_code == 200
        list_response = json.loads(response.data)
        assert "files" in list_response

    def test_storage_copy_endpoint_exists(self, client):
        """Test that copy endpoint exists and responds."""
        copy_data = {
            "source_file_id": "source-id",
            "dest_bucket": "users",
            "dest_id": "user-123",
            "dest_path": "/copied/file.txt",
        }

        response = client.post(
            "/copy",
            data=json.dumps(copy_data),
            content_type="application/json",
        )

        assert response.status_code != 404

    def test_storage_lock_unlock_endpoints_exist(self, client):
        """Test that lock/unlock endpoints exist."""
        lock_data = {"file_id": "test-file-id", "lock_type": "edit"}

        response = client.post(
            "/lock",
            data=json.dumps(lock_data),
            content_type="application/json",
        )
        assert response.status_code != 404

        unlock_data = {"file_id": "test-file-id"}

        response = client.delete(
            "/unlock",
            data=json.dumps(unlock_data),
            content_type="application/json",
        )
        assert response.status_code != 404

    def test_storage_versions_endpoint_exists(self, client):
        """Test that versions endpoints exist."""
        response = client.get("/versions?file_id=test-file-id")
        assert response.status_code != 404

        commit_data = {
            "file_id": "test-file-id",
            "object_key": "test/object/key",
            "size": 1024,
            "mime_type": "text/plain",
            "changes_description": "Test changes",
        }

        response = client.post(
            "/versions/commit",
            data=json.dumps(commit_data),
            content_type="application/json",
        )
        assert response.status_code != 404
