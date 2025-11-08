"""
Test suite for storage models.

Tests the StorageFile, FileVersion, Lock, and AuditLog models.
Focus on methods not covered by existing integration tests.
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import uuid

from app import create_app
from app.models.db import db
from app.models.storage import StorageFile, FileVersion, Lock, AuditLog


class TestStorageModels(unittest.TestCase):
    """Test cases for storage models."""

    def setUp(self):
        """Set up test fixtures."""
        # Set up test environment
        import os

        os.environ["TESTING"] = "true"
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        os.environ["MINIO_SERVICE_URL"] = "http://localhost:9000"

        self.app = create_app("app.config.TestingConfig")
        self.app.config.update(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            }
        )

        self.app_context = self.app.app_context()
        self.app_context.push()

        with self.app.app_context():
            db.create_all()

        self.user_id = str(uuid.uuid4())
        self.file_id = str(uuid.uuid4())

    def tearDown(self):
        """Tear down test fixtures."""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.app_context.pop()

    def test_storage_file_get_by_file_id_exists(self):
        """Test StorageFile.get_by_file_id for existing file."""
        file_obj = StorageFile(
            id=self.file_id,
            bucket_type="users",
            bucket_id=self.user_id,
            logical_path="test.txt",
            filename="test.txt",
            owner_id=self.user_id,
        )
        db.session.add(file_obj)
        db.session.commit()

        result = StorageFile.get_by_file_id(self.file_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.file_id)

    def test_storage_file_get_by_file_id_not_exists(self):
        """Test StorageFile.get_by_file_id for non-existent file."""
        non_existent_id = str(uuid.uuid4())
        result = StorageFile.get_by_file_id(non_existent_id)
        self.assertIsNone(result)

    def test_storage_file_get_by_path_exists(self):
        """Test StorageFile.get_by_path for existing file."""
        file_obj = StorageFile(
            bucket_type="users",
            bucket_id=self.user_id,
            logical_path="documents/test.txt",
            filename="test.txt",
            owner_id=self.user_id,
        )
        db.session.add(file_obj)
        db.session.commit()

        result = StorageFile.get_by_path(
            "users", self.user_id, "documents/test.txt"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.logical_path, "documents/test.txt")

    def test_storage_file_get_by_path_not_exists(self):
        """Test StorageFile.get_by_path for non-existent file."""
        result = StorageFile.get_by_path(
            "users", self.user_id, "nonexistent.txt"
        )
        self.assertIsNone(result)

    def test_storage_file_list_directory_empty(self):
        """Test StorageFile.list_directory for empty directory."""
        files, count = StorageFile.list_directory(
            bucket_type="users",
            bucket_id=self.user_id,
            path="empty",
            page=1,
            limit=10,
        )

        self.assertEqual(len(files), 0)
        self.assertEqual(count, 0)

    def test_storage_file_list_directory_with_files(self):
        """Test StorageFile.list_directory with files."""
        # Create files in directory
        for i in range(3):
            file_obj = StorageFile(
                bucket_type="users",
                bucket_id=self.user_id,
                logical_path=f"documents/file{i}.txt",
                filename=f"file{i}.txt",
                owner_id=self.user_id,
            )
            db.session.add(file_obj)

        db.session.commit()

        files, count = StorageFile.list_directory(
            bucket_type="users",
            bucket_id=self.user_id,
            path="documents",
            page=1,
            limit=10,
        )

        self.assertEqual(len(files), 3)
        self.assertEqual(count, 3)

    def test_storage_file_list_directory_pagination(self):
        """Test StorageFile.list_directory with pagination."""
        # Create 5 files
        for i in range(5):
            file_obj = StorageFile(
                bucket_type="users",
                bucket_id=self.user_id,
                logical_path=f"docs/file{i}.txt",
                filename=f"file{i}.txt",
                owner_id=self.user_id,
            )
            db.session.add(file_obj)

        db.session.commit()

        # Test first page
        files, count = StorageFile.list_directory(
            bucket_type="users",
            bucket_id=self.user_id,
            path="docs",
            page=1,
            limit=3,
        )

        self.assertEqual(len(files), 3)
        self.assertEqual(count, 5)

        # Test second page
        files, count = StorageFile.list_directory(
            bucket_type="users",
            bucket_id=self.user_id,
            path="docs",
            page=2,
            limit=3,
        )

        self.assertEqual(len(files), 2)
        self.assertEqual(count, 5)

    def test_storage_file_get_current_version_exists(self):
        """Test StorageFile.get_current_version when version exists."""
        file_obj = StorageFile(
            bucket_type="users",
            bucket_id=self.user_id,
            logical_path="test.txt",
            filename="test.txt",
            owner_id=self.user_id,
        )
        db.session.add(file_obj)
        db.session.flush()

        version = FileVersion(
            file_id=file_obj.id,
            version_number=1,
            object_key="test/key",
            created_by=self.user_id,
            status="validated",
        )
        db.session.add(version)
        db.session.flush()

        file_obj.current_version_id = version.id
        db.session.commit()

        current_version = file_obj.get_current_version()
        self.assertIsNotNone(current_version)
        self.assertEqual(current_version.id, version.id)

    def test_storage_file_get_current_version_none(self):
        """Test StorageFile.get_current_version when no version exists."""
        file_obj = StorageFile(
            bucket_type="users",
            bucket_id=self.user_id,
            logical_path="test.txt",
            filename="test.txt",
            owner_id=self.user_id,
        )

        current_version = file_obj.get_current_version()
        self.assertIsNone(current_version)

    def test_storage_file_get_next_version_number_no_versions(self):
        """Test StorageFile.get_next_version_number when no versions exist."""
        file_obj = StorageFile(
            bucket_type="users",
            bucket_id=self.user_id,
            logical_path="test.txt",
            filename="test.txt",
            owner_id=self.user_id,
        )
        db.session.add(file_obj)
        db.session.commit()

        next_version = file_obj.get_next_version_number()
        self.assertEqual(next_version, 1)

    def test_storage_file_get_next_version_number_with_versions(self):
        """Test StorageFile.get_next_version_number with existing versions."""
        file_obj = StorageFile(
            bucket_type="users",
            bucket_id=self.user_id,
            logical_path="test.txt",
            filename="test.txt",
            owner_id=self.user_id,
        )
        db.session.add(file_obj)
        db.session.flush()

        # Create versions 1 and 3 (skip 2 to test max logic)
        for version_num in [1, 3]:
            version = FileVersion(
                file_id=file_obj.id,
                version_number=version_num,
                object_key=f"test/key/{version_num}",
                created_by=self.user_id,
            )
            db.session.add(version)

        db.session.commit()

        next_version = file_obj.get_next_version_number()
        self.assertEqual(next_version, 4)  # Should be max + 1

    def test_file_version_methods_coverage(self):
        """Test FileVersion model methods for coverage."""
        file_obj = StorageFile(
            bucket_type="users",
            bucket_id=self.user_id,
            logical_path="test.txt",
            filename="test.txt",
            owner_id=self.user_id,
        )
        db.session.add(file_obj)
        db.session.flush()

        version = FileVersion(
            file_id=file_obj.id,
            version_number=1,
            object_key="test/key",
            created_by=self.user_id,
            status="pending_validation",
        )
        db.session.add(version)
        db.session.commit()

        # Test can_be_validated_by method
        other_user_id = str(uuid.uuid4())

        # Creator cannot validate their own version
        self.assertFalse(version.can_be_validated_by(self.user_id))

        # Other user can validate if status is pending
        self.assertTrue(version.can_be_validated_by(other_user_id))

        # Change status to draft
        version.status = "draft"
        self.assertFalse(version.can_be_validated_by(other_user_id))

    def test_file_version_submit_for_validation(self):
        """Test FileVersion.submit_for_validation method."""
        file_obj = StorageFile(
            bucket_type="users",
            bucket_id=self.user_id,
            logical_path="test.txt",
            filename="test.txt",
            owner_id=self.user_id,
        )
        db.session.add(file_obj)
        db.session.flush()

        version = FileVersion(
            file_id=file_obj.id,
            version_number=1,
            object_key="test/key",
            created_by=self.user_id,
            status="draft",
        )
        db.session.add(version)
        db.session.commit()

        version.submit_for_validation(self.user_id)

        self.assertEqual(version.status, "pending_validation")

    def test_file_version_approve(self):
        """Test FileVersion.approve method."""
        file_obj = StorageFile(
            bucket_type="users",
            bucket_id=self.user_id,
            logical_path="test.txt",
            filename="test.txt",
            owner_id=self.user_id,
        )
        db.session.add(file_obj)
        db.session.flush()

        version = FileVersion(
            file_id=file_obj.id,
            version_number=1,
            object_key="test/key",
            created_by=self.user_id,
            status="pending_validation",
        )
        db.session.add(version)
        db.session.commit()

        validator_id = str(uuid.uuid4())
        comment = "Approved for production"

        version.approve(validated_by=validator_id, comment=comment)

        self.assertEqual(version.status, "validated")
        self.assertEqual(version.validated_by, validator_id)
        self.assertEqual(version.validation_comment, comment)
        self.assertIsNotNone(version.validated_at)

        # Check that file's current_version_id is updated
        db.session.refresh(file_obj)
        self.assertEqual(file_obj.current_version_id, version.id)

    def test_file_version_reject(self):
        """Test FileVersion.reject method."""
        file_obj = StorageFile(
            bucket_type="users",
            bucket_id=self.user_id,
            logical_path="test.txt",
            filename="test.txt",
            owner_id=self.user_id,
        )
        db.session.add(file_obj)
        db.session.flush()

        version = FileVersion(
            file_id=file_obj.id,
            version_number=1,
            object_key="test/key",
            created_by=self.user_id,
            status="pending_validation",
        )
        db.session.add(version)
        db.session.commit()

        validator_id = str(uuid.uuid4())
        comment = "Needs more work"

        version.reject(validated_by=validator_id, comment=comment)

        self.assertEqual(version.status, "rejected")
        self.assertEqual(version.validated_by, validator_id)
        self.assertEqual(version.validation_comment, comment)
        self.assertIsNotNone(version.validated_at)

    def test_lock_create_lock(self):
        """Test Lock.create_lock class method."""
        lock = Lock.create(
            file_id=self.file_id,
            locked_by=self.user_id,
            lock_type="edit",
            reason="Testing lock creation",
        )

        self.assertEqual(lock.file_id, self.file_id)
        self.assertEqual(lock.locked_by, self.user_id)
        self.assertEqual(lock.lock_type, "edit")
        self.assertEqual(lock.reason, "Testing lock creation")
        self.assertTrue(lock.is_active)

    def test_lock_release(self):
        """Test Lock.release method."""
        lock = Lock(
            file_id=self.file_id,
            locked_by=self.user_id,
            lock_type="edit",
            is_active=True,
        )
        db.session.add(lock)
        db.session.commit()

        lock.release()

        self.assertFalse(lock.is_active)
        self.assertIsNotNone(lock.updated_at)

    def test_lock_is_expired_not_expired(self):
        """Test Lock.is_expired when lock is not expired."""
        lock = Lock(
            file_id=self.file_id,
            locked_by=self.user_id,
            lock_type="edit",
            expires_at=datetime.now(timezone.utc).replace(
                year=2030
            ),  # Far in future
        )

        self.assertFalse(lock.is_expired())

    def test_lock_is_expired_no_expiration(self):
        """Test Lock.is_expired when lock has no expiration."""
        lock = Lock(
            file_id=self.file_id,
            locked_by=self.user_id,
            lock_type="edit",
            expires_at=None,
        )

        self.assertFalse(lock.is_expired())

    def test_lock_is_expired_expired(self):
        """Test Lock.is_expired when lock is expired."""
        lock = Lock(
            file_id=self.file_id,
            locked_by=self.user_id,
            lock_type="edit",
            expires_at=datetime.now(timezone.utc).replace(
                year=2020
            ),  # In past
        )

        self.assertTrue(lock.is_expired())

    def test_audit_log_log_action(self):
        """Test AuditLog.log_action class method."""
        log_entry = AuditLog.log_action(
            file_id=self.file_id,
            action="upload",
            user_id=self.user_id,
            details={"filename": "test.txt", "size": 1024},
            ip_address="192.168.1.1",
            user_agent="Test Browser",
        )

        self.assertEqual(log_entry.file_id, self.file_id)
        self.assertEqual(log_entry.action, "upload")
        self.assertEqual(log_entry.user_id, self.user_id)
        self.assertEqual(
            log_entry.details, {"filename": "test.txt", "size": 1024}
        )
        self.assertEqual(log_entry.ip_address, "192.168.1.1")
        self.assertEqual(log_entry.user_agent, "Test Browser")

    def test_audit_log_get_file_history(self):
        """Test AuditLog.get_file_history class method."""
        # Create audit logs with valid enum values
        valid_actions = ["upload", "download", "copy", "move", "delete"]
        for i, action in enumerate(valid_actions):
            AuditLog.log_action(
                file_id=self.file_id,
                action=action,
                user_id=self.user_id,
                details={"step": i},
            )

        db.session.commit()

        # Get history with default limit
        history = AuditLog.get_file_history(self.file_id)
        self.assertEqual(len(history), 5)

        # Get history with custom limit
        history = AuditLog.get_file_history(self.file_id, limit=3)
        self.assertEqual(len(history), 3)

        # Verify ordering (should be newest first)
        self.assertEqual(history[0].details["step"], 4)
        self.assertEqual(history[1].details["step"], 3)


if __name__ == "__main__":
    unittest.main()
