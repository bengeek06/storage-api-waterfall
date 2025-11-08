"""
storage.py
----------

This module defines the SQLAlchemy database models for the storage system.
It includes models for files, versions, locks, validations, and audit management.
"""

import uuid
from datetime import datetime, timezone
from app.models.db import db


class StorageFile(db.Model):
    """
    Data model for a file in the storage system.

    Attributes:
        id (str): UUID identifier for the file entity.
        bucket_type (str): Type of bucket (users, companies, projects).
        bucket_id (str): ID of the bucket (user_id/company_id/project_id).
        logical_path (str): Full logical path of the file in the storage system.
        filename (str): Name of the file.
        current_version_id (str): UUID of the current active version.
        source_file_id (str): UUID of source file (for copies/drafts).
        owner_id (str): UUID of the user who owns this file.
        created_at (datetime): Timestamp when the file was created.
        updated_at (datetime): Timestamp when the file was last updated.
        tags (dict): JSON tags for the file.
        mime_type (str): MIME type of the file.
        size (int): Size of the current version in bytes.
        status (str): Current status of the file.
        is_deleted (bool): Soft delete flag.
    """

    __tablename__ = "files"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    bucket_type = db.Column(
        db.String(20), nullable=False, index=True
    )  # users, companies, projects
    bucket_id = db.Column(db.String(255), nullable=False, index=True)
    logical_path = db.Column(db.Text, nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    current_version_id = db.Column(db.String(36), nullable=True)
    source_file_id = db.Column(
        db.String(36), db.ForeignKey("files.id"), nullable=True
    )
    owner_id = db.Column(db.String(36), nullable=False, index=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    tags = db.Column(db.JSON, default=dict)
    mime_type = db.Column(db.String(255), nullable=True)
    size = db.Column(db.BigInteger, default=0)
    status = db.Column(
        db.String(50), default="draft", nullable=False
    )  # draft, upload_pending, pending_validation, approved, rejected, requires_revision, archived
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    versions = db.relationship(
        "FileVersion",
        back_populates="file",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    locks = db.relationship(
        "Lock",
        back_populates="file",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    copies = db.relationship("StorageFile", remote_side=[id])

    # Constraints and indexes
    __table_args__ = (
        db.CheckConstraint(
            "bucket_type IN ('users', 'companies', 'projects')",
            name="check_bucket_type",
        ),
        db.CheckConstraint(
            "status IN ('draft', 'upload_pending', 'pending_validation', 'approved', 'rejected', 'requires_revision', 'archived')",
            name="check_status",
        ),
        db.UniqueConstraint(
            "bucket_type", "bucket_id", "logical_path", name="unique_file_path"
        ),
        db.Index("idx_files_bucket", "bucket_type", "bucket_id"),
        db.Index("idx_files_owner", "owner_id"),
        db.Index("idx_files_status", "status"),
        db.Index("idx_files_updated", "updated_at"),
    )

    def __repr__(self):
        return f"<StorageFile {self.logical_path} (ID: {self.id}, Bucket: {self.bucket_type}/{self.bucket_id})>"

    @classmethod
    def get_by_path(cls, bucket_type, bucket_id, logical_path):
        """
        Retrieve a file by its path and bucket context.

        Args:
            bucket_type (str): Type of bucket (users/companies/projects).
            bucket_id (str): ID of the bucket.
            logical_path (str): Logical path of the file.

        Returns:
            StorageFile: The file object if found, None otherwise.
        """
        return cls.query.filter_by(
            bucket_type=bucket_type,
            bucket_id=bucket_id,
            logical_path=logical_path,
            is_deleted=False,
        ).first()

    @classmethod
    def get_by_file_id(cls, file_id):
        """
        Retrieve a file by its ID.

        Args:
            file_id (str): UUID of the file.

        Returns:
            StorageFile: The file object if found, None otherwise.
        """
        return cls.query.filter_by(id=file_id, is_deleted=False).first()

    @classmethod
    def list_directory(cls, bucket_type, bucket_id, path="", page=1, limit=50):
        """
        List files in a given directory path.

        Args:
            bucket_type (str): Type of bucket.
            bucket_id (str): ID of the bucket.
            path (str): Directory path to list.
            page (int): Page number for pagination.
            limit (int): Number of items per page.

        Returns:
            tuple: (files_list, total_count)
        """
        # Normalize path
        if path and not path.endswith("/"):
            path += "/"

        query = cls.query.filter(
            cls.bucket_type == bucket_type,
            cls.bucket_id == bucket_id,
            cls.logical_path.like(f"{path}%"),
            cls.is_deleted == False,
        )

        total_count = query.count()
        files = query.offset((page - 1) * limit).limit(limit).all()

        return files, total_count

    @classmethod
    def create(
        cls,
        bucket_type,
        bucket_id,
        logical_path,
        filename,
        owner_id,
        mime_type=None,
        size=0,
        status="draft",
        tags=None,
        source_file_id=None,
    ):
        """
        Create a new file record.

        Args:
            bucket_type (str): Type of bucket.
            bucket_id (str): ID of the bucket.
            logical_path (str): Logical path of the file.
            filename (str): Name of the file.
            owner_id (str): UUID of the owner.
            mime_type (str, optional): MIME type of the file.
            size (int): Size of the file in bytes.
            status (str): Initial status.
            tags (dict, optional): Tags for the file.
            source_file_id (str, optional): UUID of source file for copies.

        Returns:
            StorageFile: The created file object.
        """
        file_obj = cls(
            bucket_type=bucket_type,
            bucket_id=bucket_id,
            logical_path=logical_path,
            filename=filename,
            owner_id=owner_id,
            mime_type=mime_type,
            size=size,
            status=status,
            tags=tags or {},
            source_file_id=source_file_id,
        )
        db.session.add(file_obj)
        db.session.commit()
        return file_obj

    def update(self, **kwargs):
        """
        Update file attributes.

        Args:
            **kwargs: Attributes to update.
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    def soft_delete(self):
        """
        Soft delete the file (mark as deleted instead of removing).
        """
        self.is_deleted = True
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    def is_locked(self):
        """
        Check if the file is currently locked.

        Returns:
            Lock: Lock object if file is locked, None otherwise.
        """
        return self.locks.filter_by().first()

    def get_current_version(self):
        """
        Get the current version of this file.

        Returns:
            FileVersion: Current version object or None.
        """
        if self.current_version_id:
            return FileVersion.query.get(self.current_version_id)
        return None

    def create_version(
        self, object_key, created_by, size=0, mime_type=None, changelog=None
    ):
        """
        Create a new version of this file.

        Args:
            object_key (str): MinIO object key for this version.
            created_by (str): UUID of the creator.
            size (int): Size of this version in bytes.
            mime_type (str, optional): MIME type.
            changelog (str, optional): Description of changes.

        Returns:
            FileVersion: The created version object.
        """
        version_number = self.get_next_version_number()
        return FileVersion.create(
            file_id=self.id,
            version_number=version_number,
            object_key=object_key,
            size=size,
            mime_type=mime_type,
            created_by=created_by,
            changelog=changelog,
        )

    def get_next_version_number(self):
        """
        Get the next version number for this file.

        Returns:
            int: Next version number.
        """
        latest_version = self.versions.order_by(
            FileVersion.version_number.desc()
        ).first()
        return (latest_version.version_number + 1) if latest_version else 1


class FileVersion(db.Model):
    """
    Data model for file versions with validation workflow.

    Attributes:
        id (str): UUID identifier for the version.
        file_id (str): Foreign key to the parent file.
        version_number (int): Version number (1, 2, 3, ...).
        object_key (str): MinIO object key for this version.
        size (int): Size of this version in bytes.
        mime_type (str): MIME type of the version.
        checksum (str): SHA-256 checksum.
        changelog (str): Description of changes in this version.
        status (str): Validation status (draft, pending_validation, validated, rejected).
        validation_comment (str): Comment from validator.
        validated_by (str): UUID of user who validated.
        validated_at (datetime): Timestamp when validated.
        created_at (datetime): Timestamp when the version was created.
        created_by (str): UUID of the user who created this version.
    """

    __tablename__ = "file_versions"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    file_id = db.Column(
        db.String(36),
        db.ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number = db.Column(db.Integer, nullable=False)
    object_key = db.Column(db.String(500), nullable=False, index=True)
    size = db.Column(db.BigInteger, default=0)
    mime_type = db.Column(db.String(255))
    checksum = db.Column(db.String(64))  # SHA-256
    changelog = db.Column(db.Text)

    # Validation workflow
    status = db.Column(
        db.Enum(
            "draft",
            "pending_validation",
            "validated",
            "rejected",
            name="version_status",
        ),
        nullable=False,
        default="draft",
    )
    validation_comment = db.Column(db.Text)
    validated_by = db.Column(db.String(36))  # User UUID
    validated_at = db.Column(db.DateTime)

    # Metadata
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_by = db.Column(db.String(36), nullable=False)  # User UUID

    # Relationships
    file = db.relationship("StorageFile", back_populates="versions")

    # Composite unique constraint and indexes
    __table_args__ = (
        db.UniqueConstraint(
            "file_id", "version_number", name="_file_version_uc"
        ),
        db.Index("idx_file_versions_file_id", "file_id"),
        db.Index("idx_file_versions_status", "status"),
        db.Index("idx_file_versions_created_at", "created_at"),
        db.Index("idx_file_versions_object_key", "object_key"),
    )

    def __repr__(self):
        return f"<FileVersion {self.version_number} for File {self.file_id} (Status: {self.status})>"

    @classmethod
    def create(
        cls,
        file_id,
        version_number,
        object_key,
        size=0,
        mime_type=None,
        changelog=None,
        created_by=None,
        checksum=None,
    ):
        """
        Create a new file version.

        Args:
            file_id (str): UUID of the parent file.
            version_number (int): Version number.
            object_key (str): MinIO object key.
            size (int): Size in bytes.
            mime_type (str): MIME type.
            changelog (str): Description of changes.
            created_by (str): UUID of the creator.
            checksum (str): SHA-256 checksum.

        Returns:
            FileVersion: The created version object.
        """
        version = cls(
            file_id=file_id,
            version_number=version_number,
            object_key=object_key,
            size=size,
            mime_type=mime_type,
            changelog=changelog,
            created_by=created_by,
            checksum=checksum,
        )
        db.session.add(version)
        db.session.commit()
        return version

    @classmethod
    def get_by_file_and_version(cls, file_id, version_number):
        """
        Get a specific version of a file.

        Args:
            file_id (str): UUID of the file.
            version_number (int): Version number.

        Returns:
            FileVersion: Version object if found, None otherwise.
        """
        return cls.query.filter_by(
            file_id=file_id, version_number=version_number
        ).first()

    @classmethod
    def get_versions_by_file(cls, file_id):
        """
        Get all versions of a file.

        Args:
            file_id (str): UUID of the file.

        Returns:
            list: List of FileVersion objects ordered by version number.
        """
        return (
            cls.query.filter_by(file_id=file_id)
            .order_by(cls.version_number.desc())
            .all()
        )

    @classmethod
    def get_latest_for_file(cls, file_id):
        """
        Get the latest version for a file.

        Args:
            file_id (str): UUID of the file.

        Returns:
            FileVersion: Latest version or None.
        """
        return (
            cls.query.filter_by(file_id=file_id)
            .order_by(cls.version_number.desc())
            .first()
        )

    def submit_for_validation(self, submitted_by):
        """
        Submit this version for validation.

        Args:
            submitted_by (str): UUID of user submitting for validation.
        """
        self.status = "pending_validation"
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    def approve(self, validated_by, comment=None):
        """
        Approve this version.

        Args:
            validated_by (str): UUID of validator.
            comment (str): Validation comment.
        """
        self.status = "validated"
        self.validated_by = validated_by
        self.validated_at = datetime.now(timezone.utc)
        self.validation_comment = comment
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        # Set this as the current version of the file
        self.file.current_version_id = self.id
        self.file.status = "approved"
        db.session.commit()

    def reject(self, validated_by, comment=None):
        """
        Reject this version.

        Args:
            validated_by (str): UUID of validator.
            comment (str): Rejection reason.
        """
        self.status = "rejected"
        self.validated_by = validated_by
        self.validated_at = datetime.now(timezone.utc)
        self.validation_comment = comment
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    def is_latest(self):
        """
        Check if this is the latest version of the file.

        Returns:
            bool: True if latest version.
        """
        latest = self.__class__.get_latest_for_file(self.file_id)
        return latest and latest.id == self.id

    def can_be_validated_by(self, user_id):
        """
        Check if a user can validate this version.

        Args:
            user_id (str): UUID of the user.

        Returns:
            bool: True if user can validate.
        """
        # Cannot validate own work
        if self.created_by == user_id:
            return False

        # Can only validate pending versions
        return self.status == "pending_validation"


class Lock(db.Model):
    """Model for file locks."""

    __tablename__ = "locks"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    file_id = db.Column(
        db.String(36),
        db.ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    locked_by = db.Column(
        db.String(36), nullable=False
    )  # User UUID who locked the file
    lock_type = db.Column(
        db.Enum("edit", "review", "admin", name="lock_type"),
        nullable=False,
        default="edit",
    )
    reason = db.Column(db.Text)
    expires_at = db.Column(db.DateTime)  # Optional expiration
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Metadata
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    file = db.relationship("StorageFile", back_populates="locks")

    # Indexes
    __table_args__ = (
        db.Index("idx_locks_file_id", "file_id"),
        db.Index("idx_locks_locked_by", "locked_by"),
        db.Index("idx_locks_is_active", "is_active"),
        db.Index("idx_locks_expires_at", "expires_at"),
    )

    def __repr__(self):
        return f"<Lock on File {self.file_id} by {self.locked_by} ({self.lock_type})>"

    @classmethod
    def create(
        cls, file_id, locked_by, lock_type="edit", reason=None, expires_at=None
    ):
        """
        Create a new lock.

        Args:
            file_id (str): UUID of the file to lock.
            locked_by (str): UUID of the user creating the lock.
            lock_type (str): Type of lock (edit, review, admin).
            reason (str): Reason for the lock.
            expires_at (datetime): Expiration time.

        Returns:
            Lock: The created lock object.
        """
        lock = cls(
            file_id=file_id,
            locked_by=locked_by,
            lock_type=lock_type,
            reason=reason,
            expires_at=expires_at,
        )
        db.session.add(lock)
        db.session.commit()
        return lock

    @classmethod
    def get_active_lock(cls, file_id):
        """
        Get the active lock for a file.

        Args:
            file_id (str): UUID of the file.

        Returns:
            Lock: Active lock or None.
        """
        now = datetime.now(timezone.utc)
        return cls.query.filter(
            cls.file_id == file_id,
            cls.is_active == True,
            db.or_(cls.expires_at.is_(None), cls.expires_at > now),
        ).first()

    @classmethod
    def get_locks_by_user(cls, user_id, active_only=True):
        """
        Get locks created by a user.

        Args:
            user_id (str): UUID of the user.
            active_only (bool): Only return active locks.

        Returns:
            list: List of Lock objects.
        """
        query = cls.query.filter_by(locked_by=user_id)
        if active_only:
            now = datetime.now(timezone.utc)
            query = query.filter(
                cls.is_active == True,
                db.or_(cls.expires_at.is_(None), cls.expires_at > now),
            )
        return query.all()

    def release(self, released_by=None):
        """
        Release this lock.

        Args:
            released_by (str): UUID of user releasing the lock.
        """
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    def is_expired(self):
        """
        Check if the lock has expired.

        Returns:
            bool: True if lock has expired.
        """
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def can_be_released_by(self, user_id):
        """
        Check if a user can release this lock.

        Args:
            user_id (str): UUID of the user.

        Returns:
            bool: True if user can release the lock.
        """
        # Owner can always release their own lock
        if self.locked_by == user_id:
            return True

        # Add additional logic here for admin users
        # For now, only the lock owner can release it
        return False


class AuditLog(db.Model):
    """Model for audit trail of file operations."""

    __tablename__ = "audit_logs"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    file_id = db.Column(
        db.String(36),
        db.ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_id = db.Column(
        db.String(36),
        db.ForeignKey("file_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    action = db.Column(
        db.Enum(
            "upload",
            "download",
            "copy",
            "move",
            "delete",
            "lock",
            "unlock",
            "validate",
            "approve",
            "reject",
            "restore",
            name="audit_action",
        ),
        nullable=False,
    )
    user_id = db.Column(
        db.String(36), nullable=False
    )  # User who performed the action
    details = db.Column(db.JSON)  # Additional details about the action
    ip_address = db.Column(db.String(45))  # IPv4 or IPv6
    user_agent = db.Column(db.Text)

    # Metadata
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    file = db.relationship("StorageFile")
    version = db.relationship("FileVersion")

    # Indexes
    __table_args__ = (
        db.Index("idx_audit_logs_file_id", "file_id"),
        db.Index("idx_audit_logs_user_id", "user_id"),
        db.Index("idx_audit_logs_action", "action"),
        db.Index("idx_audit_logs_created_at", "created_at"),
        db.Index("idx_audit_logs_file_user", "file_id", "user_id"),
    )

    def __repr__(self):
        return f"<AuditLog {self.action} on File {self.file_id} by {self.user_id}>"

    @classmethod
    def log_action(
        cls,
        file_id,
        action,
        user_id,
        version_id=None,
        details=None,
        ip_address=None,
        user_agent=None,
    ):
        """
        Log an action in the audit trail.

        Args:
            file_id (str): UUID of the file.
            action (str): Action performed.
            user_id (str): UUID of the user.
            version_id (str): UUID of the version (if applicable).
            details (dict): Additional details.
            ip_address (str): IP address of the user.
            user_agent (str): User agent string.

        Returns:
            AuditLog: The created log entry.
        """
        log_entry = cls(
            file_id=file_id,
            action=action,
            user_id=user_id,
            version_id=version_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.session.add(log_entry)
        db.session.commit()
        return log_entry

    @classmethod
    def get_file_history(cls, file_id, limit=50, offset=0):
        """
        Get audit history for a file.

        Args:
            file_id (str): UUID of the file.
            limit (int): Number of entries to return.
            offset (int): Offset for pagination.

        Returns:
            list: List of AuditLog objects.
        """
        return (
            cls.query.filter_by(file_id=file_id)
            .order_by(cls.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @classmethod
    def get_user_activity(cls, user_id, limit=50, offset=0):
        """
        Get activity history for a user.

        Args:
            user_id (str): UUID of the user.
            limit (int): Number of entries to return.
            offset (int): Offset for pagination.

        Returns:
            list: List of AuditLog objects.
        """
        return (
            cls.query.filter_by(user_id=user_id)
            .order_by(cls.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @classmethod
    def get_recent_activity(cls, bucket_type=None, bucket_id=None, limit=50):
        """
        Get recent activity across files.

        Args:
            bucket_type (str): Filter by bucket type.
            bucket_id (str): Filter by bucket ID.
            limit (int): Number of entries to return.

        Returns:
            list: List of AuditLog objects.
        """
        query = cls.query.join(StorageFile)

        if bucket_type and bucket_id:
            query = query.filter(
                StorageFile.bucket_type == bucket_type,
                StorageFile.bucket_id == bucket_id,
            )

        return query.order_by(cls.created_at.desc()).limit(limit).all()
