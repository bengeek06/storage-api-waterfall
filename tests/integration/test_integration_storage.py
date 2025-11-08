"""
test_integration_storage.py
----------------------------

Integration tests for storage service with real MinIO backend.
Run with: docker-compose -f docker-compose.test.yml up --build
"""

import pytest
import requests
import json
import time
from minio.error import S3Error


class TestStorageIntegration:
    """Integration tests with real MinIO backend."""

    @pytest.mark.skip(reason="Integration test temporarily skipped")
    def test_service_health(self, storage_api_base_url):
        """Test that storage service is healthy."""
        from .conftest import wait_for_service

        assert wait_for_service(
            storage_api_base_url
        ), "Storage service not ready"

        response = requests.get(f"{storage_api_base_url}/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.skip(reason="Integration test temporarily skipped")
    def test_minio_connectivity(self, minio_client, test_bucket_name):
        """Test direct MinIO connectivity."""
        # Test bucket creation
        bucket_name = f"{test_bucket_name}-connectivity-test"

        try:
            # Clean up if exists
            if minio_client.bucket_exists(bucket_name):
                # Remove objects first
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

    @pytest.mark.skip(reason="Integration test temporarily skipped")
    def test_storage_upload_download_flow(
        self, storage_api_base_url, auth_headers
    ):
        """Test complete upload/download flow via API."""
        # Request upload URL
        upload_data = {
            "project_id": 1,
            "path": "/integration/test_file.txt",
            "content_type": "text/plain",
        }

        response = requests.post(
            f"{storage_api_base_url}/storage/upload-url",
            headers=auth_headers,
            data=json.dumps(upload_data),
        )

        assert response.status_code == 200
        upload_response = response.json()
        assert "url" in upload_response
        assert "expires_in" in upload_response

        upload_url = upload_response["url"]

        # Upload file to presigned URL
        test_content = "Integration test file content"
        upload_response = requests.put(
            upload_url,
            data=test_content,
            headers={"Content-Type": "text/plain"},
        )

        # Note: This might return 200 or 204 depending on MinIO configuration
        assert upload_response.status_code in [200, 204]

        # Request download URL
        download_params = {
            "project_id": 1,
            "path": "/integration/test_file.txt",
        }

        response = requests.get(
            f"{storage_api_base_url}/storage/download-url",
            headers=auth_headers,
            params=download_params,
        )

        assert response.status_code == 200
        download_response = response.json()
        assert "url" in download_response

        download_url = download_response["url"]

        # Download file from presigned URL
        download_response = requests.get(download_url)
        assert download_response.status_code == 200
        assert download_response.text == test_content

    @pytest.mark.skip(reason="Integration test temporarily skipped")
    def test_storage_directory_operations(
        self, storage_api_base_url, auth_headers
    ):
        """Test directory creation and listing."""
        # Create directory
        mkdir_data = {
            "project_id": 1,
            "path": "/integration/test_directory",
            "tags": ["integration", "test"],
        }

        response = requests.post(
            f"{storage_api_base_url}/storage/mkdir",
            headers=auth_headers,
            data=json.dumps(mkdir_data),
        )

        assert response.status_code == 201
        mkdir_response = response.json()
        assert "Directory created successfully" in mkdir_response["message"]

        # List directory contents
        list_params = {"project_id": 1, "path": "/integration"}

        response = requests.get(
            f"{storage_api_base_url}/storage/list",
            headers=auth_headers,
            params=list_params,
        )

        assert response.status_code == 200
        list_response = response.json()
        assert list_response["path"] == "/integration"
        assert "items" in list_response

        # Check that our directory is listed
        directory_found = False
        for item in list_response["items"]:
            if (
                item["name"] == "test_directory"
                and item["type"] == "directory"
            ):
                directory_found = True
                break

        assert directory_found, "Created directory not found in listing"

    @pytest.mark.skip(reason="Integration test temporarily skipped")
    def test_storage_file_deletion(
        self,
        storage_api_base_url,
        auth_headers,
        minio_client,
        test_bucket_name,
    ):
        """Test file deletion through API."""
        # First, create a file directly in MinIO for testing
        object_name = "project_1/integration_test_delete/file_to_delete.txt"
        test_content = "This file will be deleted"

        from .conftest import (
            upload_test_file,
            assert_file_exists_in_minio,
            assert_file_not_exists_in_minio,
        )

        upload_test_file(
            minio_client, test_bucket_name, object_name, test_content
        )

        # Verify file exists
        assert assert_file_exists_in_minio(
            minio_client, test_bucket_name, object_name
        )

        # Delete file via API
        delete_data = {
            "project_id": 1,
            "path": "/integration_test_delete/file_to_delete.txt",
        }

        response = requests.delete(
            f"{storage_api_base_url}/storage/delete",
            headers=auth_headers,
            data=json.dumps(delete_data),
        )

        assert response.status_code == 204

        # Verify file is deleted from MinIO
        assert assert_file_not_exists_in_minio(
            minio_client, test_bucket_name, object_name
        )

    @pytest.mark.skip(reason="Integration test temporarily skipped")
    def test_storage_error_handling(self, storage_api_base_url, auth_headers):
        """Test API error handling."""
        # Test missing parameters
        response = requests.get(
            f"{storage_api_base_url}/storage/list", headers=auth_headers
        )

        assert response.status_code == 400
        error_response = response.json()
        assert "message" in error_response
        assert "error" in error_response

        # Test file not found
        download_params = {"project_id": 1, "path": "/nonexistent/file.txt"}

        response = requests.get(
            f"{storage_api_base_url}/storage/download-url",
            headers=auth_headers,
            params=download_params,
        )

        assert response.status_code == 404
        error_response = response.json()
        assert "File not found" in error_response["message"]

        # Test directory already exists
        mkdir_data = {
            "project_id": 1,
            "path": "/integration/test_directory",  # Should already exist from previous test
        }

        response = requests.post(
            f"{storage_api_base_url}/storage/mkdir",
            headers=auth_headers,
            data=json.dumps(mkdir_data),
        )

        assert response.status_code == 409
        error_response = response.json()
        assert "Directory already exists" in error_response["message"]


class TestStoragePerformance:
    """Performance tests for storage operations."""

    @pytest.mark.skip(reason="Integration test temporarily skipped")
    @pytest.mark.slow
    def test_multiple_upload_urls_performance(
        self, storage_api_base_url, auth_headers
    ):
        """Test performance of generating multiple upload URLs."""
        import time

        start_time = time.time()

        # Generate 50 upload URLs
        for i in range(50):
            upload_data = {
                "project_id": 1,
                "path": f"/integration_test_performance/test_file_{i}.txt",
                "content_type": "text/plain",
            }

            response = requests.post(
                f"{storage_api_base_url}/storage/upload-url",
                headers=auth_headers,
                data=json.dumps(upload_data),
            )

            assert response.status_code == 200

        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_url = total_time / 50

        # Should be reasonably fast - less than 100ms per URL
        assert (
            avg_time_per_url < 0.1
        ), f"Average time per URL generation: {avg_time_per_url:.3f}s"
        print(
            f"Generated 50 upload URLs in {total_time:.2f}s (avg: {avg_time_per_url:.3f}s per URL)"
        )

    @pytest.mark.skip(reason="Integration test temporarily skipped")
    @pytest.mark.slow
    def test_large_directory_listing(
        self,
        storage_api_base_url,
        auth_headers,
        minio_client,
        test_bucket_name,
    ):
        """Test listing directory with many files."""
        # Create multiple files for testing
        file_count = 100
        from .conftest import upload_test_file

        for i in range(file_count):
            object_name = (
                f"project_1/integration_test_large_dir/file_{i:03d}.txt"
            )
            content = f"Content of file {i}"
            upload_test_file(
                minio_client, test_bucket_name, object_name, content
            )

        # Test listing performance
        start_time = time.time()

        list_params = {"project_id": 1, "path": "/integration_test_large_dir"}

        response = requests.get(
            f"{storage_api_base_url}/storage/list",
            headers=auth_headers,
            params=list_params,
        )

        end_time = time.time()
        listing_time = end_time - start_time

        assert response.status_code == 200
        list_response = response.json()
        assert len(list_response["items"]) == file_count

        # Should list 100 files in reasonable time
        assert (
            listing_time < 2.0
        ), f"Directory listing took {listing_time:.2f}s for {file_count} files"
        print(f"Listed {file_count} files in {listing_time:.2f}s")

        # Cleanup handled by autouse fixture
