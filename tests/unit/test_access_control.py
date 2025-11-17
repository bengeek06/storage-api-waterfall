"""Unit tests for access control utilities."""

import pytest
from unittest.mock import patch, MagicMock
from flask import g
from app.utils import (
    check_bucket_access,
    check_project_access,
    check_project_access_batch,
)


class TestBucketAccess:
    """Test bucket access control logic."""

    def test_users_bucket_own_access(self, app):
        """Test user can access their own users bucket."""
        with app.test_request_context():
            g.user_id = "user-123"
            g.company_id = "company-456"

            allowed, error, status = check_bucket_access(
                "users", "user-123", "read"
            )

            assert allowed is True
            assert error is None
            assert status == 200

    def test_users_bucket_other_access_denied(self, app):
        """Test user cannot access other users' buckets."""
        with app.test_request_context():
            g.user_id = "user-123"
            g.company_id = "company-456"

            allowed, error, status = check_bucket_access(
                "users", "user-999", "read"
            )

            assert allowed is False
            assert "cannot access other users" in error
            assert status == 403

    def test_companies_bucket_own_access(self, app):
        """Test user can access their company bucket."""
        with app.test_request_context():
            g.user_id = "user-123"
            g.company_id = "company-456"

            allowed, error, status = check_bucket_access(
                "companies", "company-456", "write"
            )

            assert allowed is True
            assert error is None
            assert status == 200

    def test_companies_bucket_other_access_denied(self, app):
        """Test user cannot access other companies' buckets."""
        with app.test_request_context():
            g.user_id = "user-123"
            g.company_id = "company-456"

            allowed, error, status = check_bucket_access(
                "companies", "company-999", "write"
            )

            assert allowed is False
            assert "cannot access other companies" in error
            assert status == 403

    def test_invalid_bucket_type(self, app):
        """Test invalid bucket type returns error."""
        with app.test_request_context():
            g.user_id = "user-123"
            g.company_id = "company-456"

            allowed, error, status = check_bucket_access(
                "invalid", "bucket-id", "read"
            )

            assert allowed is False
            assert "Invalid bucket_type" in error
            assert status == 400

    @patch("app.utils.check_project_access")
    def test_projects_bucket_delegates_to_service(
        self, mock_check_project, app
    ):
        """Test projects bucket delegates to project service."""
        with app.test_request_context():
            g.user_id = "user-123"
            g.company_id = "company-456"

            mock_check_project.return_value = (True, None, 200)

            allowed, error, status = check_bucket_access(
                "projects", "project-789", "read", "file-abc"
            )

            mock_check_project.assert_called_once_with(
                "project-789", "read", "file-abc"
            )
            assert allowed is True


class TestProjectAccess:
    """Test project service access verification."""

    @patch("app.utils.requests.post")
    def test_project_access_allowed(self, mock_post, app):
        """Test successful project access check."""
        with app.test_request_context():
            # Enable project service for this test
            app.config["USE_PROJECT_SERVICE"] = True
            g.user_id = "user-123"

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "allowed": True,
                "role": "admin",
            }
            mock_post.return_value = mock_response

            allowed, error, status = check_project_access(
                "project-123", "write"
            )

            assert allowed is True
            assert error is None
            assert status == 200

            # Verify correct endpoint was called
            args, kwargs = mock_post.call_args
            assert "/check-file-access" in args[0]
            assert kwargs["json"]["project_id"] == "project-123"
            assert kwargs["json"]["action"] == "write"

    @patch("app.utils.requests.post")
    def test_project_access_denied(self, mock_post, app):
        """Test denied project access."""
        with app.test_request_context():
            app.config["USE_PROJECT_SERVICE"] = True
            g.user_id = "user-123"

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "allowed": False,
                "reason": "insufficient_permissions",
            }
            mock_post.return_value = mock_response

            allowed, error, status = check_project_access(
                "project-123", "delete"
            )

            assert allowed is False
            assert "insufficient_permissions" in error
            assert status == 403

    @patch("app.utils.requests.post")
    def test_project_access_with_file_id(self, mock_post, app):
        """Test project access check includes file_id for audit."""
        with app.test_request_context():
            app.config["USE_PROJECT_SERVICE"] = True
            g.user_id = "user-123"

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"allowed": True}
            mock_post.return_value = mock_response

            allowed, error, status = check_project_access(
                "project-123", "validate", "file-456"
            )

            # Verify file_id was included
            args, kwargs = mock_post.call_args
            assert kwargs["json"]["file_id"] == "file-456"

    @patch("app.utils.requests.post")
    def test_project_service_timeout(self, mock_post, app):
        """Test project service timeout handling."""
        with app.test_request_context():
            app.config["USE_PROJECT_SERVICE"] = True
            g.user_id = "user-123"

            import requests

            mock_post.side_effect = requests.exceptions.Timeout()

            allowed, error, status = check_project_access(
                "project-123", "read"
            )

            assert allowed is False
            assert "timeout" in error.lower()
            assert status == 504

    @patch("app.utils.requests.post")
    def test_project_service_unavailable(self, mock_post, app):
        """Test project service unavailable handling."""
        with app.test_request_context():
            app.config["USE_PROJECT_SERVICE"] = True
            g.user_id = "user-123"

            import requests

            mock_post.side_effect = requests.exceptions.ConnectionError()

            allowed, error, status = check_project_access(
                "project-123", "read"
            )

            assert allowed is False
            assert "unavailable" in error.lower()
            assert status == 502

    @patch("app.utils.requests.post")
    def test_project_service_error_response(self, mock_post, app):
        """Test project service error response."""
        with app.test_request_context():
            app.config["USE_PROJECT_SERVICE"] = True
            g.user_id = "user-123"

            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal server error"
            mock_post.return_value = mock_response

            allowed, error, status = check_project_access(
                "project-123", "read"
            )

            assert allowed is False
            assert "Project service error" in error
            assert status == 502


class TestProjectAccessBatch:
    """Test batch project access verification."""

    @patch("app.utils.requests.post")
    def test_batch_access_success(self, mock_post, app):
        """Test successful batch access check."""
        with app.test_request_context():
            app.config["USE_PROJECT_SERVICE"] = True
            g.user_id = "user-123"

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "results": [
                    {"project_id": "p1", "action": "read", "allowed": True},
                    {"project_id": "p2", "action": "write", "allowed": False},
                ]
            }
            mock_post.return_value = mock_response

            checks = [
                {"project_id": "p1", "action": "read"},
                {"project_id": "p2", "action": "write"},
            ]
            results, error, status = check_project_access_batch(checks)

            assert results is not None
            assert len(results) == 2
            assert results[0]["allowed"] is True
            assert results[1]["allowed"] is False
            assert error is None
            assert status == 200

    @patch("app.utils.requests.post")
    def test_batch_access_timeout(self, mock_post, app):
        """Test batch access timeout handling."""
        with app.test_request_context():
            app.config["USE_PROJECT_SERVICE"] = True
            g.user_id = "user-123"

            import requests

            mock_post.side_effect = requests.exceptions.Timeout()

            checks = [{"project_id": "p1", "action": "read"}]
            results, error, status = check_project_access_batch(checks)

            assert results is None
            assert "timeout" in error.lower()
            assert status == 504
