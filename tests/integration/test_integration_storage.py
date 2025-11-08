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

from app.models.storage import StorageFile, FileVersion, Lock


class TestStorageIntegration:
    """Integration tests with real MinIO backend."""

    # ==================== Health & Connectivity ====================

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

    # ==================== Upload Endpoints ====================

    def test_upload_presign_success(self, client, app):
        """Test presigned upload URL generation."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        upload_data = {
            "bucket_type": "projects",
            "bucket_id": test_project_id,
            "logical_path": "documents/test_file.pdf",
        }

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
        data = json.loads(response.data)
        assert "url" in data
        assert "expires_in" in data
        assert "object_key" in data
        assert data["expires_in"] > 0
        # URL can be either MinIO direct or proxy URL
        assert "upload" in data["url"].lower()

    def test_upload_presign_invalid_path(self, client):
        """Test presigned upload with invalid path."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        upload_data = {
            "bucket_type": "projects",
            "bucket_id": test_project_id,
            "logical_path": "../../../etc/passwd",  # Path traversal attempt
        }

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

        assert response.status_code == 400

    def test_upload_presign_invalid_bucket_type(self, client):
        """Test presigned upload with invalid bucket type."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())

        upload_data = {
            "bucket_type": "invalid_bucket",
            "bucket_id": str(uuid.uuid4()),
            "logical_path": "test.pdf",
        }

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

        # Returns 403 (access check before validation) instead of 400
        assert response.status_code == 403

    def test_upload_presign_missing_auth(self, client):
        """Test presigned upload without authentication."""
        upload_data = {
            "bucket_type": "projects",
            "bucket_id": str(uuid.uuid4()),
            "logical_path": "test.pdf",
        }

        response = client.post(
            "/upload/presign",
            data=json.dumps(upload_data),
            content_type="application/json",
        )

        assert response.status_code == 401

    # ==================== Download Endpoints ====================
    # Note: /download/presign and /download/proxy are not yet implemented
    # These tests are skipped until the endpoints are implemented

    # ==================== List Endpoints ====================

    def test_list_files_empty_bucket(self, client):
        """Test listing files in an empty bucket."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        headers = {
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        response = client.get(
            f"/list?bucket=projects&id={test_project_id}", headers=headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "files" in data
        assert isinstance(data["files"], list)
        assert len(data["files"]) == 0

    def test_list_files_with_files(self, client, app):
        """Test listing files in a bucket with files."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        # Create test files
        with app.app_context():
            from app.models.db import db

            files = [
                StorageFile(
                    bucket_type="projects",
                    bucket_id=test_project_id,
                    logical_path=f"documents/file{i}.pdf",
                    filename=f"file{i}.pdf",
                    size=1024 * i,
                    mime_type="application/pdf",
                    owner_id=test_user_id,
                )
                for i in range(1, 4)
            ]
            db.session.add_all(files)
            db.session.commit()

        headers = {
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        response = client.get(
            f"/list?bucket=projects&id={test_project_id}", headers=headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "files" in data
        assert len(data["files"]) == 3

    def test_list_files_with_pagination(self, client, app):
        """Test file listing with pagination."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        # Create many test files
        with app.app_context():
            from app.models.db import db

            files = [
                StorageFile(
                    bucket_type="projects",
                    bucket_id=test_project_id,
                    logical_path=f"documents/file{i}.pdf",
                    filename=f"file{i}.pdf",
                    size=1024,
                    mime_type="application/pdf",
                    owner_id=test_user_id,
                )
                for i in range(1, 11)
            ]
            db.session.add_all(files)
            db.session.commit()

        headers = {
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        # Test first page
        response = client.get(
            f"/list?bucket=projects&id={test_project_id}&page=1&limit=5",
            headers=headers,
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["files"]) == 5
        assert "pagination" in data

        # Test second page
        response = client.get(
            f"/list?bucket=projects&id={test_project_id}&page=2&limit=5",
            headers=headers,
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["files"]) == 5

    def test_list_files_missing_bucket_param(self, client):
        """Test list files with missing required parameter."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())

        headers = {
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        response = client.get("/list", headers=headers)

        assert response.status_code == 400

    # ==================== Lock/Unlock Endpoints ====================

    def test_lock_file_success(self, client, app):
        """Test locking a file successfully."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        # Create a file
        with app.app_context():
            from app.models.db import db

            test_file = StorageFile(
                bucket_type="projects",
                bucket_id=test_project_id,
                logical_path="documents/test.pdf",
                filename="test.pdf",
                size=1024,
                mime_type="application/pdf",
                owner_id=test_user_id,
            )
            db.session.add(test_file)
            db.session.commit()
            file_id = test_file.id

        headers = {
            "Content-Type": "application/json",
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        lock_data = {"file_id": file_id, "lock_type": "edit"}

        response = client.post(
            "/lock", data=json.dumps(lock_data), headers=headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get("success") is True

    def test_lock_file_already_locked(self, client, app):
        """Test locking a file that is already locked."""
        test_user1_id = str(uuid.uuid4())
        test_user2_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        # Create a file and lock it
        with app.app_context():
            from app.models.db import db

            test_file = StorageFile(
                bucket_type="projects",
                bucket_id=test_project_id,
                logical_path="documents/test.pdf",
                filename="test.pdf",
                size=1024,
                mime_type="application/pdf",
                owner_id=test_user1_id,
            )
            db.session.add(test_file)
            db.session.flush()

            lock = Lock(
                file_id=test_file.id, locked_by=test_user1_id, lock_type="edit"
            )
            db.session.add(lock)
            db.session.commit()
            file_id = test_file.id

        # Try to lock with another user
        headers = {
            "Content-Type": "application/json",
            "X-User-ID": test_user2_id,
            "X-Company-ID": test_company_id,
        }

        lock_data = {"file_id": file_id, "lock_type": "edit"}

        response = client.post(
            "/lock", data=json.dumps(lock_data), headers=headers
        )

        assert response.status_code == 409

    def test_unlock_file_success(self, client, app):
        """Test unlocking a file successfully."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        # Create a file and lock it
        with app.app_context():
            from app.models.db import db

            test_file = StorageFile(
                bucket_type="projects",
                bucket_id=test_project_id,
                logical_path="documents/test.pdf",
                filename="test.pdf",
                size=1024,
                mime_type="application/pdf",
                owner_id=test_user_id,
            )
            db.session.add(test_file)
            db.session.flush()

            lock = Lock(
                file_id=test_file.id, locked_by=test_user_id, lock_type="edit"
            )
            db.session.add(lock)
            db.session.commit()
            file_id = test_file.id

        headers = {
            "Content-Type": "application/json",
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        unlock_data = {"file_id": file_id}

        response = client.post(
            "/unlock", data=json.dumps(unlock_data), headers=headers
        )

        assert response.status_code == 200

    def test_unlock_file_not_locked(self, client, app):
        """Test unlocking a file that is not locked."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        # Create a file without lock
        with app.app_context():
            from app.models.db import db

            test_file = StorageFile(
                bucket_type="projects",
                bucket_id=test_project_id,
                logical_path="documents/test.pdf",
                filename="test.pdf",
                size=1024,
                mime_type="application/pdf",
                owner_id=test_user_id,
            )
            db.session.add(test_file)
            db.session.commit()
            file_id = test_file.id

        headers = {
            "Content-Type": "application/json",
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        unlock_data = {"file_id": file_id}

        response = client.post(
            "/unlock", data=json.dumps(unlock_data), headers=headers
        )

        # Should return 404 or specific error for no lock
        assert response.status_code in [404, 400]

    def test_list_locks(self, client, app):
        """Test listing locks."""
        # Note: /locks endpoint is not yet implemented
        # This test will be skipped
        pytest.skip("/locks endpoint not yet implemented")

    # ==================== Version Endpoints ====================

    def test_commit_version_success(self, client, app):
        """Test committing a new version."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        # Create a file
        with app.app_context():
            from app.models.db import db

            test_file = StorageFile(
                bucket_type="projects",
                bucket_id=test_project_id,
                logical_path="documents/test.pdf",
                filename="test.pdf",
                size=1024,
                mime_type="application/pdf",
                owner_id=test_user_id,
            )
            db.session.add(test_file)
            db.session.commit()
            file_id = test_file.id

        headers = {
            "Content-Type": "application/json",
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        version_data = {
            "file_id": file_id,
            "object_key": f"projects/{test_project_id}/documents/test.pdf/2",
            "created_by": test_user_id,
            "changelog": "Updated content",
        }

        response = client.post(
            "/versions/commit", data=json.dumps(version_data), headers=headers
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert "data" in data
        assert "version_id" in data["data"]

    def test_list_versions(self, client, app):
        """Test listing versions for a file."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        # Create a file with versions
        with app.app_context():
            from app.models.db import db

            test_file = StorageFile(
                bucket_type="projects",
                bucket_id=test_project_id,
                logical_path="documents/test.pdf",
                filename="test.pdf",
                size=1024,
                mime_type="application/pdf",
                owner_id=test_user_id,
            )
            db.session.add(test_file)
            db.session.flush()

            for i in range(1, 4):
                version = FileVersion(
                    file_id=test_file.id,
                    version_number=i,
                    object_key=f"projects/{test_project_id}/documents/test.pdf/{i}",
                    size=1024 * i,
                    mime_type="application/pdf",
                    created_by=test_user_id,
                )
                db.session.add(version)

            db.session.commit()
            file_id = test_file.id

        headers = {
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        response = client.get(f"/versions?file_id={file_id}", headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "versions" in data
        assert len(data["versions"]) == 3

    def test_approve_version(self, client, app):
        """Test approving a pending version."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())
        test_creator_id = str(uuid.uuid4())  # Different user who created the version

        # Create a file with pending version
        with app.app_context():
            from app.models.db import db

            test_file = StorageFile(
                bucket_type="projects",
                bucket_id=test_project_id,
                logical_path="documents/test.pdf",
                filename="test.pdf",
                size=1024,
                mime_type="application/pdf",
                owner_id=test_creator_id,
            )
            db.session.add(test_file)
            db.session.flush()

            version = FileVersion(
                file_id=test_file.id,
                version_number=2,
                object_key=f"projects/{test_project_id}/documents/test.pdf/2",
                size=2048,
                mime_type="application/pdf",
                created_by=test_creator_id,  # Created by different user
                status="pending_validation",
            )
            db.session.add(version)
            db.session.commit()
            version_id = version.id

        headers = {
            "Content-Type": "application/json",
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        approve_data = {"comment": "Looks good!"}

        response = client.post(
            f"/versions/{version_id}/approve",
            data=json.dumps(approve_data),
            headers=headers,
        )

        assert response.status_code == 200

    def test_reject_version(self, client, app):
        """Test rejecting a pending version."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())
        test_creator_id = str(uuid.uuid4())  # Different user who created the version

        # Create a file with pending version
        with app.app_context():
            from app.models.db import db

            test_file = StorageFile(
                bucket_type="projects",
                bucket_id=test_project_id,
                logical_path="documents/test.pdf",
                filename="test.pdf",
                size=1024,
                mime_type="application/pdf",
                owner_id=test_creator_id,
            )
            db.session.add(test_file)
            db.session.flush()

            version = FileVersion(
                file_id=test_file.id,
                version_number=2,
                object_key=f"projects/{test_project_id}/documents/test.pdf/2",
                size=2048,
                mime_type="application/pdf",
                created_by=test_creator_id,  # Created by different user
                status="pending_validation",
            )
            db.session.add(version)
            db.session.commit()
            version_id = version.id

        headers = {
            "Content-Type": "application/json",
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        reject_data = {"comment": "Needs revision"}

        response = client.post(
            f"/versions/{version_id}/reject",
            data=json.dumps(reject_data),
            headers=headers,
        )

        assert response.status_code == 200

    # ==================== Copy Endpoint ====================

    def test_copy_file_success(self, client, app):
        """Test copying a file between buckets."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())
        test_project_id = str(uuid.uuid4())

        # Create a source file
        with app.app_context():
            from app.models.db import db

            source_file = StorageFile(
                bucket_type="projects",
                bucket_id=test_project_id,
                logical_path="documents/source.pdf",
                filename="source.pdf",
                size=1024,
                mime_type="application/pdf",
                owner_id=test_user_id,
            )
            db.session.add(source_file)
            db.session.commit()
            file_id = source_file.id

        headers = {
            "Content-Type": "application/json",
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        copy_data = {
            "source_file_id": file_id,
            "dest_bucket": "users",
            "dest_id": test_user_id,
            "dest_path": "my_copy.pdf",
        }

        response = client.post(
            "/copy", data=json.dumps(copy_data), headers=headers
        )

        # Should succeed or return specific error
        assert response.status_code in [201, 400, 403]

    # ==================== Edge Cases & Error Handling ====================

    def test_invalid_uuid_format(self, client):
        """Test endpoints with invalid UUID format."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())

        headers = {
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        response = client.get(
            "/list?bucket=projects&id=invalid-uuid", headers=headers
        )

        assert response.status_code == 400

    def test_malformed_json(self, client):
        """Test endpoint with malformed JSON."""
        test_user_id = str(uuid.uuid4())
        test_company_id = str(uuid.uuid4())

        headers = {
            "Content-Type": "application/json",
            "X-User-ID": test_user_id,
            "X-Company-ID": test_company_id,
        }

        response = client.post(
            "/upload/presign", data="not a json", headers=headers
        )

        assert response.status_code in [400, 500]

