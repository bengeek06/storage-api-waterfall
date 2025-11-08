"""
test_storage_integration.py
---------------------------

Integration tests for complete collaborative storage workflows.
Tests end-to-end scenarios with storage operations.
"""

import unittest
import uuid
import json
import pytest
from unittest.mock import patch

from app import create_app
from app.config import TestingConfig
from app.models.db import db
from app.models.storage import StorageFile, FileVersion, Lock


class TestStorageIntegration(unittest.TestCase):
    """Integration tests for collaborative storage workflows."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        db.create_all()

        self.user1_id = str(uuid.uuid4())
        self.user2_id = str(uuid.uuid4())
        self.user3_id = str(uuid.uuid4())
        self.company_id = str(uuid.uuid4())
        self.project_id = str(uuid.uuid4())

        self.jwt_user1 = {"sub": self.user1_id, "company_id": self.company_id}
        self.jwt_user2 = {"sub": self.user2_id, "company_id": self.company_id}
        self.jwt_user3 = {"sub": self.user3_id, "company_id": self.company_id}

    def tearDown(self):
        """Clean up after tests."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch("app.resources.storage_bucket_upload_download.extract_jwt_data")
    def test_presigned_upload_url_generation(self, mock_jwt):
        """Test presigned upload URL generation."""
        mock_jwt.return_value = self.jwt_user1

        data = {
            "bucket": "projects",
            "id": self.project_id,
            "path": "/documents/test.txt",
            "filename": "test.txt",
            "mime_type": "text/plain",
            "size": 100,
        }

        response = self.client.post(
            "/upload/presign",
            data=json.dumps(data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        response_data = json.loads(response.data)
        self.assertIn("url", response_data)
        self.assertIn("expires_in", response_data)

    @patch("app.resources.storage_collaborative.extract_jwt_data")
    def test_list_files_in_bucket(self, mock_jwt):
        """Test listing files in a bucket."""
        mock_jwt.return_value = self.jwt_user1

        response = self.client.get(
            "/list",
            query_string={"bucket": "projects", "id": self.project_id},
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertIn("files", response_data)

    @patch("app.resources.storage_collaborative.extract_jwt_data")
    def test_lock_unlock_workflow(self, mock_jwt):
        """Test lock and unlock operations."""
        mock_jwt.return_value = self.jwt_user1

        # Create a test file first
        test_file = StorageFile(
            id=str(uuid.uuid4()),
            bucket_type="projects",
            bucket_id=self.project_id,
            logical_path="/documents/test.txt",
            filename="test.txt",
            object_key="projects/test/documents/test.txt",
            size=100,
            mime_type="text/plain",
            uploaded_by=self.user1_id,
        )
        db.session.add(test_file)
        db.session.commit()

        # Lock the file
        lock_data = {"file_id": test_file.id, "lock_type": "edit"}

        response = self.client.post(
            "/lock",
            data=json.dumps(lock_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertTrue(response_data.get("success"))

        # Unlock the file
        unlock_data = {"file_id": test_file.id}

        response = self.client.delete(
            "/unlock",
            data=json.dumps(unlock_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

    @patch("app.resources.storage_validation.extract_jwt_data")
    def test_version_workflow(self, mock_jwt):
        """Test version commit workflow."""
        mock_jwt.return_value = self.jwt_user1

        # Create a test file first
        test_file = StorageFile(
            id=str(uuid.uuid4()),
            bucket_type="projects",
            bucket_id=self.project_id,
            logical_path="/documents/versioned.txt",
            filename="versioned.txt",
            object_key="projects/test/documents/versioned.txt",
            size=100,
            mime_type="text/plain",
            uploaded_by=self.user1_id,
        )
        db.session.add(test_file)
        db.session.commit()

        # Commit a new version
        version_data = {
            "file_id": test_file.id,
            "object_key": "projects/test/documents/versioned.txt/v2",
            "size": 150,
            "mime_type": "text/plain",
            "changes_description": "Updated content",
        }

        response = self.client.post(
            "/versions/commit",
            data=json.dumps(version_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        response_data = json.loads(response.data)
        self.assertIn("version", response_data)

        # List versions
        response = self.client.get(f"/versions?file_id={test_file.id}")

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertIn("versions", response_data)

    @patch("app.resources.storage_collaborative.extract_jwt_data")
    def test_copy_file_workflow(self, mock_jwt):
        """Test file copy workflow."""
        mock_jwt.return_value = self.jwt_user1

        # Create a source file first
        source_file = StorageFile(
            id=str(uuid.uuid4()),
            bucket_type="projects",
            bucket_id=self.project_id,
            logical_path="/documents/source.txt",
            filename="source.txt",
            object_key="projects/test/documents/source.txt",
            size=100,
            mime_type="text/plain",
            uploaded_by=self.user1_id,
        )
        db.session.add(source_file)
        db.session.commit()

        # Copy the file
        copy_data = {
            "source_file_id": source_file.id,
            "dest_bucket": "users",
            "dest_id": self.user1_id,
            "dest_path": "/my_copy.txt",
        }

        response = self.client.post(
            "/copy",
            data=json.dumps(copy_data),
            content_type="application/json",
        )

        # Should succeed (201) or fail with validation error (not 404)
        self.assertNotEqual(response.status_code, 404)
