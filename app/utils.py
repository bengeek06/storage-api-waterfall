"""Utility functions for the Identity Service API."""

import os
import re
import uuid
from functools import wraps
import jwt
from flask import request, g, current_app
import requests

from app.logger import logger


def camel_to_snake(name):
    """
    Convert a CamelCase or PascalCase string to snake_case.

    Args:
        name (str): The string to convert.

    Returns:
        str: The converted snake_case string.
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
    return re.sub(r"_+", "_", snake)


def extract_jwt_data():
    """
    Extract and decode JWT data from request cookies.

    Returns:
        dict: Dictionary containing user_id and company_id from JWT, or None if invalid/missing
    """
    jwt_token = request.cookies.get("access_token")
    if not jwt_token:
        logger.debug("JWT token not found in cookies")
        return None

    jwt_secret = os.environ.get("JWT_SECRET")
    if not jwt_secret:
        logger.warning("JWT_SECRET not found in environment variables")
        return None

    try:
        payload = jwt.decode(jwt_token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub") or payload.get("user_id")
        company_id = payload.get("company_id")

        logger.debug(
            f"JWT decoded successfully - user_id: {user_id}, company_id: {company_id}"
        )
        return {
            "user_id": user_id,
            "company_id": company_id,
            "payload": payload,
        }
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None
    except (ValueError, KeyError) as e:
        logger.warning(f"JWT decode failed: {e}")
        return None


def require_jwt_auth():
    """
    Decorator to require JWT authentication and extract JWT information.
    Requires a valid JWT token in cookies - no fallback to headers.

    Always extracts and stores user_id, company_id, and jwt_data in Flask's g object
    for use in view functions. This ensures the JWT is decoded only once per request.

    Returns:
        Decorated function or error response

    Stores in g:
        - g.user_id: User ID from JWT
        - g.company_id: Company ID from JWT
        - g.jwt_data: Complete JWT payload
        - g.json_data: Original request JSON data (unmodified)
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            # Try JWT authentication first
            jwt_data = extract_jwt_data()

            # Fallback to headers for testing environment
            if not jwt_data:
                user_id = request.headers.get("X-User-ID")
                company_id = request.headers.get("X-Company-ID")

                if user_id:
                    # Create mock JWT data from headers (for testing)
                    jwt_data = {"user_id": user_id, "company_id": company_id}
                    logger.debug(
                        "Using headers for authentication (testing mode)"
                    )
                else:
                    return {"message": "Missing or invalid JWT token"}, 401

            # Extract company_id and user_id from JWT data
            company_id = jwt_data.get("company_id")
            user_id = jwt_data.get("user_id")

            if not user_id:
                logger.error("user_id missing in JWT token")
                return {"message": "Invalid JWT token: missing user_id"}, 401

            if not company_id:
                logger.error("company_id missing in JWT token")
                return {
                    "message": "Invalid JWT token: missing company_id"
                }, 401

            # Validate UUID format for company_id
            try:
                uuid.UUID(company_id)
            except (ValueError, TypeError):
                logger.error(f"Invalid company_id format in JWT: {company_id}")
                return {
                    "message": "Invalid JWT token: company_id must be a valid UUID"
                }, 401

            # Store company_id, user_id and jwt_data in g for use in view functions
            g.company_id = company_id
            g.user_id = user_id
            g.jwt_data = jwt_data

            # Store original JSON data in g without modification
            try:
                if request.content_length and request.content_length > 0:
                    g.json_data = request.get_json()
                else:
                    g.json_data = None
            except (ValueError, TypeError, RuntimeError):
                g.json_data = None

            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def check_access_required(operation):
    """
    Decorator to check if the user has the required access for an operation.

    Args:
        operation (str): The operation to check access for.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            resource_name = kwargs.get("resource_name") or (
                request.view_args.get("resource_name")
                if request.view_args
                else None
            )
            # If not found, deduce from the resource class name
            if not resource_name:
                view_self = args[0] if args else None
                if view_self and hasattr(view_self, "__class__"):
                    class_name = view_self.__class__.__name__
                    if class_name.lower().endswith("resource"):
                        base_name = class_name[:-8]
                        resource_name = camel_to_snake(base_name)
            # Normalisation: si resource_name se termine par '_list', on retire ce suffixe
            if resource_name and resource_name.endswith("_list"):
                resource_name = resource_name[:-5]
            user_id = getattr(g, "user_id", None)

            # Essayer d'utiliser les données JWT déjà décodées si disponibles
            if not user_id and hasattr(g, "jwt_data") and g.jwt_data:
                user_id = g.jwt_data.get("user_id")
                logger.debug(
                    f"Using user_id from already decoded JWT: {user_id}"
                )
            # Sinon, extraire user_id du cookie JWT
            elif not user_id:
                logger.debug(
                    "User ID not found in g or headers, checking JWT cookie"
                )
                jwt_data = extract_jwt_data()
                if jwt_data:
                    user_id = jwt_data.get("user_id")
                    logger.debug(f"Extracted user_id from JWT: {user_id}")
                else:
                    logger.warning("JWT token not found or invalid")
            if not user_id or not resource_name:
                logger.warning(
                    "Missing user_id or resource_name for access check."
                )
                return {
                    "error": "Missing user_id or resource_name for access check."
                }, 400
            # Use CheckAccessResource logic
            access_granted, reason, status = check_access(
                user_id, resource_name, operation
            )
            if access_granted:
                return view_func(*args, **kwargs)
            return {"error": "Access denied", "reason": reason}, (
                status if isinstance(status, int) else 403
            )

        return wrapped

    return decorator


def check_access(user_id, resource_name, operation):
    """
    Check if the user has access to perform the operation on the resource.

    Args:
        user_id (str): The ID of the user.
        resource_name (str): The name of the resource.
        operation (str): The operation to check access for.
    Returns:
        tuple: (access_granted (bool), reason (str), status (int or str))
    """
    logger.debug(
        f"Checking access for user_id: {user_id}, "
        f"resource_name: {resource_name}, operation: {operation}"
    )

    flask_env = os.environ.get("FLASK_ENV", "production").lower()
    if flask_env in ["testing", "development"]:
        logger.debug("check_access: testing/development environment")
        return True, "Access granted in testing/development environment.", 200

    guardian_service_url = os.environ.get("GUARDIAN_SERVICE_URL")
    if not guardian_service_url:
        logger.error("GUARDIAN_SERVICE_URL not set")
        return False, "Internal server error", 500

    try:
        timeout = float(os.environ.get("GUARDIAN_SERVICE_TIMEOUT", "5"))

        # Get JWT token from cookies to forward to Guardian service (if in request context)
        headers = {}
        try:
            jwt_token = request.cookies.get("access_token")
            if jwt_token:
                headers["Cookie"] = f"access_token={jwt_token}"
                logger.debug("Forwarding JWT cookie to Guardian service")
        except RuntimeError:
            # No request context available (e.g., during testing without Flask app context)
            logger.debug(
                "No request context available, skipping JWT cookie forwarding"
            )

        response = requests.post(
            f"{guardian_service_url}/check-access",
            json={
                "user_id": user_id,
                "service": "identity",
                "resource_name": resource_name,
                "operation": operation,
            },
            headers=headers,
            timeout=timeout,
        )

        # Don't raise_for_status() immediately - check the response first
        if response.status_code == 200:
            response_data = response.json()
            logger.debug(f"Guardian service response: {response_data}")
            return (
                response_data.get("access_granted", False),
                response_data.get("reason", "Unknown error"),
                response_data.get("status", 200),
            )
        if response.status_code == 400:
            # Guardian service returned a 400 with detailed error message
            try:
                response_data = response.json()
                logger.warning(
                    f"Guardian service returned 400: {response_data}"
                )
                return (
                    response_data.get("access_granted", False),
                    response_data.get("reason", "Bad request"),
                    400,
                )
            except (ValueError, KeyError) as json_error:
                logger.error(
                    f"Failed to parse Guardian 400 response as JSON: {json_error}"
                )
                return False, f"Guardian service error: {response.text}", 400
        # Other error status codes
        logger.error(
            f"Guardian service returned status {response.status_code}: {response.text}"
        )
        return (
            False,
            f"Guardian service error (status {response.status_code})",
            response.status_code,
        )

    except requests.exceptions.Timeout:
        logger.error("Timeout when checking access with guardian service")
        return False, "Guardian service timeout", 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking access: {e}")
        return False, "Internal server error", 500
    except (ValueError, KeyError) as e:
        logger.error(f"Unexpected error checking access: {e}")
        return False, "Internal server error", 500


def check_bucket_access(bucket_type, bucket_id, action="read", file_id=None):
    """
    Verify user has access to a bucket based on bucket type.

    Args:
        bucket_type (str): Type of bucket ('users', 'companies', 'projects')
        bucket_id (str): ID of the bucket (user_id, company_id, or project_id)
        action (str): Action to perform ('read', 'write', 'delete', 'lock', 'validate')
        file_id (str, optional): File ID for audit logging

    Returns:
        tuple: (allowed (bool), error_message (str or None), status_code (int))
    """
    user_id = g.user_id
    company_id = g.company_id

    logger.debug(
        f"Checking bucket access - type: {bucket_type}, id: {bucket_id}, "
        f"action: {action}, user: {user_id}, company: {company_id}"
    )

    # Validate bucket_type
    if bucket_type not in ["users", "companies", "projects"]:
        return False, f"Invalid bucket_type: {bucket_type}", 400

    # Users bucket: user can only access their own directory
    if bucket_type == "users":
        allowed = bucket_id == user_id
        if not allowed:
            logger.warning(
                f"Access denied: user {user_id} tried to access users/{bucket_id}"
            )
            return (
                False,
                "Access denied: cannot access other users' files",
                403,
            )
        return True, None, 200

    # Companies bucket: user must belong to the company
    if bucket_type == "companies":
        allowed = bucket_id == company_id
        if not allowed:
            logger.warning(
                f"Access denied: user {user_id} (company {company_id}) "
                f"tried to access companies/{bucket_id}"
            )
            return (
                False,
                "Access denied: cannot access other companies' files",
                403,
            )
        return True, None, 200

    # Projects bucket: delegate to project service
    if bucket_type == "projects":
        return check_project_access(bucket_id, action, file_id)

    return False, "Unknown bucket type", 400


def check_project_access(project_id, action="read", file_id=None):
    """
    Call project service to verify user has access to a project.

    Args:
        project_id (str): UUID of the project
        action (str): Action to perform ('read', 'write', 'delete', 'lock', 'validate')
        file_id (str, optional): File ID for audit logging

    Returns:
        tuple: (allowed (bool), error_message (str or None), status_code (int))
    """
    project_service_url = current_app.config.get("PROJECT_SERVICE_URL")
    if not project_service_url:
        logger.error("PROJECT_SERVICE_URL not configured")
        return False, "Internal configuration error", 500

    # Prepare request payload
    payload = {"project_id": project_id, "action": action}
    if file_id:
        payload["file_id"] = file_id

    # Get JWT cookie to forward to project service
    headers = {}
    jwt_token = request.cookies.get("access_token")
    if jwt_token:
        headers["Cookie"] = f"access_token={jwt_token}"
        logger.debug("Forwarding JWT cookie to project service")
    else:
        logger.warning(
            "No JWT token found in cookies for project access check"
        )

    try:
        logger.debug(
            f"Calling project service: {project_service_url}/check-file-access "
            f"for project {project_id}, action {action}"
        )

        response = requests.post(
            f"{project_service_url}/check-file-access",
            json=payload,
            headers=headers,
            timeout=2.0,  # 2 second timeout as specified
        )

        if response.status_code == 200:
            data = response.json()
            allowed = data.get("allowed", False)

            if allowed:
                role = data.get("role", "unknown")
                logger.info(
                    f"Project access granted: user {g.user_id}, "
                    f"project {project_id}, action {action}, role {role}"
                )
                return True, None, 200

            reason = data.get("reason", "insufficient_permissions")
            logger.warning(
                f"Project access denied: user {g.user_id}, "
                f"project {project_id}, action {action}, reason: {reason}"
            )
            return False, f"Access denied: {reason}", 403

        logger.error(
            f"Project service returned {response.status_code}: {response.text}"
        )
        return (
            False,
            f"Project service error (status {response.status_code})",
            502,
        )

    except requests.exceptions.Timeout:
        logger.error(
            f"Timeout calling project service for project {project_id}"
        )
        return False, "Project service unavailable (timeout)", 504

    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling project service: {e}")
        return False, "Project service unavailable", 502

    except (ValueError, KeyError) as e:
        logger.error(f"Error parsing project service response: {e}")
        return False, "Invalid response from project service", 502


def check_project_access_batch(checks):
    """
    Call project service to verify access for multiple projects at once.

    Args:
        checks (list): List of dicts with keys: project_id, action, file_id (optional)
                      Example: [{"project_id": "uuid", "action": "read", "file_id": "uuid"}]

    Returns:
        tuple: (results (list), error_message (str or None), status_code (int))
               results format: [{"project_id": "uuid", "action": "read", "allowed": true}]
    """
    project_service_url = current_app.config.get("PROJECT_SERVICE_URL")
    if not project_service_url:
        logger.error("PROJECT_SERVICE_URL not configured")
        return None, "Internal configuration error", 500

    # Get JWT cookie
    headers = {}
    jwt_token = request.cookies.get("access_token")
    if jwt_token:
        headers["Cookie"] = f"access_token={jwt_token}"

    try:
        logger.debug(
            f"Calling project service batch endpoint for {len(checks)} checks"
        )

        response = requests.post(
            f"{project_service_url}/check-file-access/batch",
            json={"checks": checks},
            headers=headers,
            timeout=2.0,
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            logger.debug(
                f"Batch access check completed: {len(results)} results"
            )
            return results, None, 200

        logger.error(
            f"Project service batch returned {response.status_code}: {response.text}"
        )
        return (
            None,
            f"Project service error (status {response.status_code})",
            502,
        )

    except requests.exceptions.Timeout:
        logger.error("Timeout calling project service batch endpoint")
        return None, "Project service unavailable (timeout)", 504

    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling project service batch: {e}")
        return None, "Project service unavailable", 502

    except (ValueError, KeyError) as e:
        logger.error(f"Error parsing project service batch response: {e}")
        return None, "Invalid response from project service", 502


def log_access_denied(bucket_type, bucket_id, action, reason, file_id=None):
    """
    Log an access denial event to audit trail.

    Args:
        bucket_type (str): Type of bucket
        bucket_id (str): ID of the bucket
        action (str): Action that was denied
        reason (str): Reason for denial
        file_id (str, optional): File ID if applicable
    """
    # pylint: disable=import-outside-toplevel
    # Imports inside function to avoid circular dependency
    from app.models.storage import AuditLog
    from app.models.db import db

    try:
        user_id = getattr(g, "user_id", "unknown")
        ip_address = request.remote_addr if request else None
        user_agent = request.headers.get("User-Agent") if request else None

        details = {
            "bucket_type": bucket_type,
            "bucket_id": bucket_id,
            "action": action,
            "reason": reason,
            "access_denied": True,
        }

        audit_log = AuditLog(
            file_id=file_id,  # Can be None
            action="access_denied",
            user_id=user_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.session.add(audit_log)
        db.session.commit()

        logger.info(
            f"Access denied logged: user={user_id}, bucket={bucket_type}/{bucket_id}, "
            f"action={action}, reason={reason}"
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Catch all exceptions to prevent audit logging from breaking the request
        logger.error(f"Failed to log access denial: {e}")
        # Don't fail the request if audit logging fails
        db.session.rollback()


def require_bucket_access(action):
    """
    Decorator to verify bucket access based on request data.

    Expects request JSON to contain bucket_type and bucket_id (or project_id for projects).
    Optionally includes file_id for audit logging.

    Args:
        action (str): Action to verify ('read', 'write', 'delete', 'lock', 'validate')

    Usage:
        @require_bucket_access('write')
        def post(self):
            # bucket_type and bucket_id already verified
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            # Get request data (should be set by @require_jwt_auth)
            data = getattr(g, "json_data", None)
            if not data:
                try:
                    data = request.get_json()
                except Exception:  # pylint: disable=broad-exception-caught
                    # Catch all JSON parsing errors (ValueError, TypeError, etc.)
                    return {"error": "Invalid JSON data"}, 400

            # Extract bucket info
            bucket_type = data.get("bucket_type")
            bucket_id = data.get("bucket_id") or data.get("project_id")
            file_id = data.get("file_id")

            if not bucket_type:
                return {"error": "Missing bucket_type in request"}, 400
            if not bucket_id:
                return {"error": "Missing bucket_id in request"}, 400

            # Check access
            allowed, error_msg, status_code = check_bucket_access(
                bucket_type, bucket_id, action, file_id
            )

            if not allowed:
                # Log the denial
                log_access_denied(
                    bucket_type, bucket_id, action, error_msg, file_id
                )
                return {"error": error_msg}, status_code

            # Store bucket info in g for use in view
            g.bucket_type = bucket_type
            g.bucket_id = bucket_id

            return view_func(*args, **kwargs)

        return wrapped

    return decorator
