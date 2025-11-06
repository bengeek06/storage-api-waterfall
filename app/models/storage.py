"""
storage.py
----------

This module defines the SQLAlchemy database models for the storage system.
It includes models for files, versions, and metadata management.
"""

from datetime import datetime, timezone
from app.models.db import db


class StorageFile(db.Model):
    """
    Data model for a file in the storage system.

    Attributes:
        id (int): Unique identifier for the file entity.
        project_id (int): ID of the project this file belongs to (nullable for personal files).
        user_id (int): ID of the user who owns/uploaded this file.
        path (str): Full path of the file in the storage system.
        filename (str): Name of the file.
        size (int): Size of the file in bytes.
        content_type (str): MIME type of the file.
        storage_key (str): Unique key used for storage backend (S3/MinIO).
        is_directory (bool): Whether this entry represents a directory.
        created_at (datetime): Timestamp when the file was created.
        updated_at (datetime): Timestamp when the file was last updated.
        is_deleted (bool): Soft delete flag.
    """

    __tablename__ = "storage_files"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, nullable=True, index=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    path = db.Column(db.String(1000), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    size = db.Column(db.BigInteger, default=0)
    content_type = db.Column(db.String(255), nullable=True)
    storage_key = db.Column(db.String(500), nullable=False, unique=True)
    is_directory = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    versions = db.relationship('FileVersion', backref='file', lazy='dynamic', cascade='all, delete-orphan')

    # Composite index for efficient queries
    __table_args__ = (
        db.Index('idx_storage_files_project_path', 'project_id', 'path'),
        db.Index('idx_storage_files_user_path', 'user_id', 'path'),
        db.Index('idx_storage_files_active', 'is_deleted', 'project_id', 'user_id'),
    )

    def __repr__(self):
        return f"<StorageFile {self.path} (ID: {self.id}, Project: {self.project_id}, User: {self.user_id})>"

    @classmethod
    def get_by_path(cls, path, project_id=None, user_id=None):
        """
        Retrieve a file by its path and context.

        Args:
            path (str): Path of the file.
            project_id (int, optional): ID of the project.
            user_id (int, optional): ID of the user.

        Returns:
            StorageFile: The file object if found, None otherwise.
        """
        query = cls.query.filter_by(path=path, is_deleted=False)
        if project_id is not None:
            query = query.filter_by(project_id=project_id)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.first()

    @classmethod
    def list_directory(cls, path, project_id=None, user_id=None):
        """
        List files and directories in a given path.

        Args:
            path (str): Directory path to list.
            project_id (int, optional): ID of the project.
            user_id (int, optional): ID of the user.

        Returns:
            list: List of StorageFile objects in the directory.
        """
        # Ensure path ends with / for directory listing
        if not path.endswith('/'):
            path += '/'
        
        query = cls.query.filter(
            cls.path.like(f"{path}%"),
            cls.is_deleted == False
        )
        
        if project_id is not None:
            query = query.filter_by(project_id=project_id)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        
        # Only get direct children (not nested subdirectories)
        results = []
        for file in query.all():
            relative_path = file.path[len(path):]
            # If there's no more '/' or only one at the end, it's a direct child
            if '/' not in relative_path or (relative_path.endswith('/') and relative_path.count('/') == 1):
                results.append(file)
        
        return results

    @classmethod
    def create(cls, path, filename, user_id, project_id=None, size=0, content_type=None, 
               storage_key=None, is_directory=False):
        """
        Create a new file record.

        Args:
            path (str): Path of the file.
            filename (str): Name of the file.
            user_id (int): ID of the user.
            project_id (int, optional): ID of the project.
            size (int): Size of the file in bytes.
            content_type (str, optional): MIME type of the file.
            storage_key (str, optional): Storage backend key.
            is_directory (bool): Whether this is a directory.

        Returns:
            StorageFile: The created file object.
        """
        if storage_key is None:
            # Generate storage key based on path and timestamp
            storage_key = f"{path}_{datetime.now(timezone.utc).timestamp()}"
        
        file_obj = cls(
            path=path,
            filename=filename,
            user_id=user_id,
            project_id=project_id,
            size=size,
            content_type=content_type,
            storage_key=storage_key,
            is_directory=is_directory
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

    def create_version(self, comment=None, tag=None):
        """
        Create a new version of this file.

        Args:
            comment (str, optional): Comment for this version.
            tag (str, optional): Tag for this version.

        Returns:
            FileVersion: The created version object.
        """
        return FileVersion.create(
            file_id=self.id,
            version_number=self.get_next_version_number(),
            storage_key=self.storage_key,
            size=self.size,
            comment=comment,
            tag=tag,
            created_by=self.user_id
        )

    def get_next_version_number(self):
        """
        Get the next version number for this file.

        Returns:
            int: Next version number.
        """
        latest_version = self.versions.order_by(FileVersion.version_number.desc()).first()
        return (latest_version.version_number + 1) if latest_version else 1

    def get_latest_version(self):
        """
        Get the latest version of this file.

        Returns:
            FileVersion: Latest version object or None.
        """
        return self.versions.order_by(FileVersion.version_number.desc()).first()


class FileVersion(db.Model):
    """
    Data model for file versions.

    Attributes:
        id (int): Unique identifier for the version.
        file_id (int): Foreign key to the parent file.
        version_number (int): Version number (1, 2, 3, ...).
        storage_key (str): Storage backend key for this version.
        size (int): Size of this version in bytes.
        comment (str): Optional comment for this version.
        tag (str): Optional tag (draft, approved, archived, etc.).
        created_at (datetime): Timestamp when the version was created.
        created_by (int): ID of the user who created this version.
    """

    __tablename__ = "file_versions"

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('storage_files.id'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    storage_key = db.Column(db.String(500), nullable=False)
    size = db.Column(db.BigInteger, default=0)
    comment = db.Column(db.Text, nullable=True)
    tag = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = db.Column(db.Integer, nullable=False)

    # Composite unique constraint
    __table_args__ = (
        db.UniqueConstraint('file_id', 'version_number'),
        db.Index('idx_file_versions_file_id', 'file_id'),
        db.Index('idx_file_versions_tag', 'tag'),
    )

    def __repr__(self):
        return f"<FileVersion {self.version_number} for File {self.file_id} (Tag: {self.tag})>"

    @classmethod
    def create(cls, file_id, version_number, storage_key, size=0, comment=None, tag=None, created_by=None):
        """
        Create a new file version.

        Args:
            file_id (int): ID of the parent file.
            version_number (int): Version number.
            storage_key (str): Storage backend key.
            size (int): Size in bytes.
            comment (str, optional): Version comment.
            tag (str, optional): Version tag.
            created_by (int, optional): ID of the creator.

        Returns:
            FileVersion: The created version object.
        """
        version = cls(
            file_id=file_id,
            version_number=version_number,
            storage_key=storage_key,
            size=size,
            comment=comment,
            tag=tag,
            created_by=created_by
        )
        db.session.add(version)
        db.session.commit()
        return version

    @classmethod
    def get_by_file_and_version(cls, file_id, version_number):
        """
        Get a specific version of a file.

        Args:
            file_id (int): ID of the file.
            version_number (int): Version number.

        Returns:
            FileVersion: Version object if found, None otherwise.
        """
        return cls.query.filter_by(file_id=file_id, version_number=version_number).first()

    @classmethod
    def get_versions_by_file(cls, file_id):
        """
        Get all versions of a file.

        Args:
            file_id (int): ID of the file.

        Returns:
            list: List of FileVersion objects ordered by version number.
        """
        return cls.query.filter_by(file_id=file_id).order_by(cls.version_number.desc()).all()

    def update_tag(self, tag, comment=None):
        """
        Update the tag of this version.

        Args:
            tag (str): New tag.
            comment (str, optional): Updated comment.
        """
        self.tag = tag
        if comment is not None:
            self.comment = comment
        db.session.commit()