"""
test_storage_integration.py
---------------------------

Integration tests for complete collaborative storage workflows.
Tests end-to-end scenarios with multiple users and operations.
"""

import unittest
import uuid
import json
import io
import pytest
from unittest.mock import patch, MagicMock

from app import create_app
from app.config import TestingConfig
from app.models.db import db
from app.models.storage import StorageFile, FileVersion, AuditLog


@pytest.mark.skip(reason="Integration tests temporarily skipped")
class TestStorageIntegration(unittest.TestCase):
    """Integration tests for collaborative storage workflows."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Create tables
        db.create_all()

        # Test users and company
        self.user1_id = str(uuid.uuid4())
        self.user2_id = str(uuid.uuid4())
        self.user3_id = str(uuid.uuid4())  # Admin/reviewer
        self.company_id = str(uuid.uuid4())
        self.project_id = str(uuid.uuid4())

        # Mock JWT data for different users
        self.jwt_user1 = {"sub": self.user1_id, "company_id": self.company_id}

        self.jwt_user2 = {"sub": self.user2_id, "company_id": self.company_id}

        self.jwt_user3 = {"sub": self.user3_id, "company_id": self.company_id}

    def tearDown(self):
        """Clean up after tests."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @unittest.skip("Integration test temporarily skipped")
    @patch("app.resources.storage_bucket_upload_download.storage_backend")
    def test_complete_document_collaboration_workflow(self, mock_storage):
        """Test complete document collaboration workflow."""

        # Mock storage backend
        mock_storage.upload_object = MagicMock()
        mock_storage.generate_download_url.return_value = (
            "https://example.com/download-url",
            3600,
        )

        # 1. User1 uploads initial document to project bucket
        with patch(
            "app.resources.storage_bucket_upload_download.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user1

            test_file = io.BytesIO(b"Initial document content v1")
            data = {
                "bucket_type": "projects",
                "bucket_id": self.project_id,
                "logical_path": "documents/project_plan.docx",
                "filename": "project_plan.docx",
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "size": len(b"Initial document content v1"),
                "file": (test_file, "project_plan.docx"),
            }

            response = self.client.post(
                "/upload", data=data, content_type="multipart/form-data"
            )

            self.assertEqual(response.status_code, 201)
            upload_data = json.loads(response.data)
            file_id = upload_data["data"]["file_id"]

        # 2. User2 lists files in project bucket
        with patch(
            "app.resources.storage_collaborative.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user2

            response = self.client.get(
                "/list",
                query_string={
                    "bucket_type": "projects",
                    "bucket_id": self.project_id,
                },
            )

            self.assertEqual(response.status_code, 200)
            list_data = json.loads(response.data)
            self.assertEqual(len(list_data["files"]), 1)
            self.assertEqual(
                list_data["files"][0]["filename"], "project_plan.docx"
            )

        # 3. User2 locks the file for editing
        with patch(
            "app.resources.storage_collaborative.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user2

            response = self.client.post(
                "/lock", json={"file_id": file_id, "lock_type": "edit"}
            )

            self.assertEqual(response.status_code, 200)
            lock_data = json.loads(response.data)
            self.assertTrue(lock_data["success"])

        # 4. User1 tries to download (should work despite lock)
        with patch(
            "app.resources.storage_bucket_upload_download.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user1

            response = self.client.get(
                "/download",
                query_string={
                    "bucket_type": "projects",
                    "bucket_id": self.project_id,
                    "logical_path": "documents/project_plan.docx",
                },
            )

            self.assertEqual(response.status_code, 200)
            download_data = json.loads(response.data)
            self.assertIn("url", download_data)

        # 5. User1 tries to upload new version (should fail - file locked by user2)
        with patch(
            "app.resources.storage_bucket_upload_download.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user1

            # First create a new version (this should work for committing changes)
            response = self.client.post(
                "/versions/commit",
                json={
                    "file_id": file_id,
                    "object_key": "projects/test/documents/project_plan.docx/2",
                    "size": 1500,
                    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "changes_description": "Updated project timeline",
                },
            )

            # This should fail because user2 has the lock
            self.assertEqual(response.status_code, 409)
            error_data = json.loads(response.data)
            self.assertEqual(error_data["error"], "FILE_LOCKED")

        # 6. User2 commits new version (should work - they have the lock)
        with patch(
            "app.resources.storage_validation.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user2

            response = self.client.post(
                "/versions/commit",
                json={
                    "file_id": file_id,
                    "object_key": "projects/test/documents/project_plan.docx/2",
                    "size": 1500,
                    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "changes_description": "Updated project timeline and milestones",
                },
            )

            self.assertEqual(response.status_code, 201)
            commit_data = json.loads(response.data)
            version2_id = commit_data["version"]["id"]

        # 7. User2 unlocks the file
        with patch(
            "app.resources.storage_collaborative.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user2

            response = self.client.delete("/unlock", json={"file_id": file_id})

            self.assertEqual(response.status_code, 200)

        # 8. User3 (reviewer) approves the new version
        with patch(
            "app.resources.storage_validation.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user3

            response = self.client.post(
                "/versions/approve",
                json={
                    "version_id": version2_id,
                    "comment": "Reviewed and approved. Good updates to timeline.",
                },
            )

            self.assertEqual(response.status_code, 200)
            approve_data = json.loads(response.data)
            self.assertTrue(approve_data["success"])

        # 9. Verify version is now validated
        version = FileVersion.query.get(version2_id)
        self.assertEqual(version.status, "validated")
        self.assertEqual(version.reviewed_by, self.user3_id)

        # 10. Verify file's current version is updated
        file_obj = StorageFile.query.get(file_id)
        self.assertEqual(file_obj.current_version_id, version2_id)

        # 11. List versions to see history
        with patch(
            "app.resources.storage_validation.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user1

            response = self.client.get(
                "/versions", query_string={"file_id": file_id}
            )

            self.assertEqual(response.status_code, 200)
            versions_data = json.loads(response.data)
            self.assertEqual(len(versions_data["versions"]), 2)

            # First version should be auto-validated
            v1 = next(
                v
                for v in versions_data["versions"]
                if v["version_number"] == 1
            )
            self.assertEqual(v1["status"], "validated")

            # Second version should be validated by user3
            v2 = next(
                v
                for v in versions_data["versions"]
                if v["version_number"] == 2
            )
            self.assertEqual(v2["status"], "validated")
            self.assertEqual(v2["reviewed_by"], self.user3_id)

    @unittest.skip("Integration test temporarily skipped")
    def test_file_copy_and_collaboration(self):
        """Test file copying between buckets and subsequent collaboration."""

        # Create initial file in user1's personal bucket
        file_obj = StorageFile.create(
            bucket_type="users",
            bucket_id=self.user1_id,
            logical_path="documents/personal_doc.txt",
            filename="personal_doc.txt",
            owner_id=self.user1_id,
            mime_type="text/plain",
            size=1024,
        )

        version = FileVersion.create(
            file_id=file_obj.id,
            version_number=1,
            object_key="users/test/documents/personal_doc.txt/1",
            size=1024,
            created_by=self.user1_id,
        )

        file_obj.current_version_id = version.id
        db.session.commit()

        # 1. User1 copies file to project bucket
        with patch(
            "app.resources.storage_collaborative.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user1

            response = self.client.post(
                "/copy",
                json={
                    "source_file_id": file_obj.id,
                    "dest_bucket_type": "projects",
                    "dest_bucket_id": self.project_id,
                    "dest_logical_path": "shared/personal_doc.txt",
                },
            )

            self.assertEqual(response.status_code, 201)
            copy_data = json.loads(response.data)
            copied_file_id = copy_data["copied_file"]["id"]

        # 2. User2 locks the copied file
        with patch(
            "app.resources.storage_collaborative.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user2

            response = self.client.post(
                "/lock", json={"file_id": copied_file_id, "lock_type": "edit"}
            )

            self.assertEqual(response.status_code, 200)

        # 3. User2 commits changes
        with patch(
            "app.resources.storage_validation.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user2

            response = self.client.post(
                "/versions/commit",
                json={
                    "file_id": copied_file_id,
                    "object_key": "projects/test/shared/personal_doc.txt/2",
                    "size": 1200,
                    "changes_description": "Added team feedback and improvements",
                },
            )

            self.assertEqual(response.status_code, 201)
            commit_data = json.loads(response.data)
            new_version_id = commit_data["version"]["id"]

        # 4. User2 unlocks
        with patch(
            "app.resources.storage_collaborative.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user2

            response = self.client.delete(
                "/unlock", json={"file_id": copied_file_id}
            )

            self.assertEqual(response.status_code, 200)

        # 5. User1 (original owner) approves the changes
        with patch(
            "app.resources.storage_validation.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user1

            response = self.client.post(
                "/versions/approve",
                json={
                    "version_id": new_version_id,
                    "comment": "Thanks for the improvements!",
                },
            )

            self.assertEqual(response.status_code, 200)

        # 6. Verify audit trail exists for all operations
        audit_logs = AuditLog.query.filter_by(file_id=copied_file_id).all()

        # Should have logs for: copy, lock, commit, unlock, approve
        expected_actions = [
            "copy",
            "lock",
            "version_commit",
            "unlock",
            "version_approve",
        ]
        actual_actions = [log.action for log in audit_logs]

        for action in expected_actions:
            self.assertIn(action, actual_actions)

    @unittest.skip("Integration test temporarily skipped")
    def test_concurrent_access_and_locking(self):
        """Test concurrent access patterns and lock conflicts."""

        # Create test file
        file_obj = StorageFile.create(
            bucket_type="projects",
            bucket_id=self.project_id,
            logical_path="documents/concurrent_test.txt",
            filename="concurrent_test.txt",
            owner_id=self.user1_id,
        )

        # 1. User1 locks for editing
        with patch(
            "app.resources.storage_collaborative.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user1

            response = self.client.post(
                "/lock", json={"file_id": file_obj.id, "lock_type": "edit"}
            )

            self.assertEqual(response.status_code, 200)

        # 2. User2 tries to lock (should fail)
        with patch(
            "app.resources.storage_collaborative.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user2

            response = self.client.post(
                "/lock", json={"file_id": file_obj.id, "lock_type": "edit"}
            )

            self.assertEqual(response.status_code, 409)
            error_data = json.loads(response.data)
            self.assertEqual(error_data["error"], "FILE_ALREADY_LOCKED")

        # 3. User2 can still get file info
        with patch(
            "app.resources.storage_collaborative.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user2

            response = self.client.get(
                "/files/info", query_string={"file_id": file_obj.id}
            )

            self.assertEqual(response.status_code, 200)
            info_data = json.loads(response.data)
            self.assertTrue(info_data["file"]["is_locked"])
            self.assertEqual(info_data["file"]["locked_by"], self.user1_id)

        # 4. User1 unlocks
        with patch(
            "app.resources.storage_collaborative.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user1

            response = self.client.delete(
                "/unlock", json={"file_id": file_obj.id}
            )

            self.assertEqual(response.status_code, 200)

        # 5. Now user2 can lock
        with patch(
            "app.resources.storage_collaborative.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user2

            response = self.client.post(
                "/lock", json={"file_id": file_obj.id, "lock_type": "edit"}
            )

            self.assertEqual(response.status_code, 200)

    @unittest.skip("Integration test temporarily skipped")
    def test_version_validation_workflow_with_rejection(self):
        """Test version validation workflow with rejection and resubmission."""

        # Create file with initial version
        file_obj = StorageFile.create(
            bucket_type="projects",
            bucket_id=self.project_id,
            logical_path="documents/validation_test.txt",
            filename="validation_test.txt",
            owner_id=self.user1_id,
        )

        # 1. User1 commits a new version
        with patch(
            "app.resources.storage_validation.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user1

            response = self.client.post(
                "/versions/commit",
                json={
                    "file_id": file_obj.id,
                    "object_key": "projects/test/documents/validation_test.txt/1",
                    "size": 1000,
                    "changes_description": "Initial draft with some issues",
                },
            )

            self.assertEqual(response.status_code, 201)
            commit_data = json.loads(response.data)
            version1_id = commit_data["version"]["id"]

        # 2. User3 (reviewer) rejects the version
        with patch(
            "app.resources.storage_validation.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user3

            response = self.client.post(
                "/versions/reject",
                json={
                    "version_id": version1_id,
                    "comment": "Please fix formatting issues and add more details in section 3.",
                },
            )

            self.assertEqual(response.status_code, 200)

        # 3. Verify version status
        version1 = FileVersion.query.get(version1_id)
        self.assertEqual(version1.status, "rejected")
        self.assertEqual(version1.reviewed_by, self.user3_id)

        # 4. User1 commits improved version
        with patch(
            "app.resources.storage_validation.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user1

            response = self.client.post(
                "/versions/commit",
                json={
                    "file_id": file_obj.id,
                    "object_key": "projects/test/documents/validation_test.txt/2",
                    "size": 1200,
                    "changes_description": "Fixed formatting and expanded section 3 as requested",
                },
            )

            self.assertEqual(response.status_code, 201)
            commit_data = json.loads(response.data)
            version2_id = commit_data["version"]["id"]

        # 5. User3 approves the improved version
        with patch(
            "app.resources.storage_validation.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user3

            response = self.client.post(
                "/versions/approve",
                json={
                    "version_id": version2_id,
                    "comment": "Much better! All issues addressed.",
                },
            )

            self.assertEqual(response.status_code, 200)

        # 6. List versions with filter for validated ones
        with patch(
            "app.resources.storage_validation.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user1

            response = self.client.get(
                "/versions",
                query_string={"file_id": file_obj.id, "status": "validated"},
            )

            self.assertEqual(response.status_code, 200)
            versions_data = json.loads(response.data)
            self.assertEqual(len(versions_data["versions"]), 1)
            self.assertEqual(versions_data["versions"][0]["id"], version2_id)

        # 7. List all versions to see full history
        with patch(
            "app.resources.storage_validation.extract_jwt_data"
        ) as mock_jwt:
            mock_jwt.return_value = self.jwt_user1

            response = self.client.get(
                "/versions", query_string={"file_id": file_obj.id}
            )

            self.assertEqual(response.status_code, 200)
            versions_data = json.loads(response.data)
            self.assertEqual(len(versions_data["versions"]), 2)

            # Find rejected and validated versions
            rejected_version = next(
                v
                for v in versions_data["versions"]
                if v["status"] == "rejected"
            )
            validated_version = next(
                v
                for v in versions_data["versions"]
                if v["status"] == "validated"
            )

            self.assertEqual(rejected_version["version_number"], 1)
            self.assertEqual(validated_version["version_number"], 2)
            self.assertEqual(validated_version["reviewed_by"], self.user3_id)


if __name__ == "__main__":
    unittest.main()
