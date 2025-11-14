"""
storage_base.py
---------------

Base classes and common utilities for storage resources.
"""


class BaseStorageResource:
    """Base class with common functionality for storage resources."""

    def _check_bucket_access(self, bucket, bucket_id, user_id, company_id):
        """
        Check if user has access to the bucket.

        Args:
            bucket (str): Type of bucket (users/companies/projects)
            bucket_id (str): Bucket ID
            user_id (str): Current user ID
            company_id (str): Current user's company ID

        Returns:
            bool: True if access allowed
        """
        if bucket == "users":
            # User can only access their own bucket
            return bucket_id == user_id
        if bucket == "companies":
            # User can access their company's bucket
            return bucket_id == company_id
        if bucket == "projects":
            # Project access control is delegated to the project service
            # via check_bucket_access() in app.utils
            return True
        return False
