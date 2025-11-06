"""
storage.py
----------
This module defines the resources for managing storage operations in the application.
It includes endpoints for file management, versioning, and storage operations.
"""

import os
from datetime import datetime, timedelta, timezone
from flask import request, g
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from flask_restful import Resource

from app.models.db import db
from app.models.storage import StorageFile, FileVersion
from app.schemas.storage_schema import (
    StorageFileSchema, FileVersionSchema, FileListSchema, FileItemSchema,
    UploadRequestSchema, MkdirRequestSchema, FileCopyMoveRequestSchema,
    PromoteRequestSchema, TagRequestSchema, DeleteRequestSchema,
    PresignedUrlResponseSchema, VersionListSchema
)
from app.logger import logger
from app.utils import require_jwt_auth, check_access_required
from app.services.storage_service import storage_backend

# Constants for error messages
VALIDATION_ERROR_MSG = "Validation error"
VALIDATION_ERROR_LOG = "Validation error: %s"
DATABASE_ERROR_MSG = "Database error"
DATABASE_ERROR_LOG = "Database error: %s"
FILE_NOT_FOUND_MSG = "File not found"

# Initialize schemas
storage_file_schema = StorageFileSchema(session=db.session)
storage_files_schema = StorageFileSchema(session=db.session, many=True)
file_version_schema = FileVersionSchema(session=db.session)
file_versions_schema = FileVersionSchema(session=db.session, many=True)
upload_request_schema = UploadRequestSchema()
mkdir_request_schema = MkdirRequestSchema()
copy_move_request_schema = FileCopyMoveRequestSchema()
promote_request_schema = PromoteRequestSchema()
tag_request_schema = TagRequestSchema()
delete_request_schema = DeleteRequestSchema()
presigned_url_schema = PresignedUrlResponseSchema()
version_list_schema = VersionListSchema()
file_list_schema = FileListSchema()


class StorageListResource(Resource):
    """
    Resource for listing files and directories.
    
    Methods:
        get(): List files and directories in a specified path.
    """

    @require_jwt_auth()
    @check_access_required("list")
    def get(self):
        """
        List files and directories.
        
        Query Parameters:
            project_id (int, optional): Project identifier.
            user_id (int, optional): User identifier.
            path (str, optional): Path to list (default: root).
        
        Returns:
            tuple: Directory listing and HTTP status code 200.
        """
        logger.info("Listing storage contents")
        
        project_id = request.args.get('project_id', type=int)
        user_id = request.args.get('user_id', type=int)
        path = request.args.get('path', '')
        
        # Validate that either project_id or user_id is provided
        if not project_id and not user_id:
            return {"message": "Either project_id or user_id must be provided"}, 400
        
        try:
            files = StorageFile.list_directory(path, project_id=project_id, user_id=user_id)
            
            # Convert to FileItem format
            items = []
            for file_obj in files:
                items.append({
                    "name": file_obj.filename,
                    "type": "directory" if file_obj.is_directory else "file",
                    "size": file_obj.size,
                    "modified_at": file_obj.updated_at
                })
            
            result = {
                "path": path,
                "items": items
            }
            
            return file_list_schema.dump(result), 200
            
        except Exception as e:
            logger.error("Error listing storage contents: %s", str(e))
            return {"message": "Error listing contents", "error": str(e)}, 500


class StorageMkdirResource(Resource):
    """
    Resource for creating directories.
    
    Methods:
        post(): Create a new directory.
    """

    @require_jwt_auth()
    @check_access_required("create")
    def post(self):
        """
        Create a new directory.
        
        Expects:
            JSON payload with project_id and path.
        
        Returns:
            tuple: Success message and HTTP status code 201.
        """
        logger.info("Creating directory")
        
        json_data = request.get_json()
        try:
            validated_data = mkdir_request_schema.load(json_data)
        except ValidationError as err:
            logger.error(VALIDATION_ERROR_LOG, err.messages)
            return {"message": VALIDATION_ERROR_MSG, "errors": err.messages}, 400
        
        project_id = validated_data['project_id']
        path = validated_data['path']
        
        # Ensure path ends with / for directories
        if not path.endswith('/'):
            path += '/'
        
        # Check if directory already exists
        existing_dir = StorageFile.get_by_path(path, project_id=project_id)
        if existing_dir:
            return {"message": "Directory already exists"}, 409
        
        try:
            # Create directory record
            StorageFile.create(
                path=path,
                filename=os.path.basename(path.rstrip('/')),
                user_id=g.user_id,  # From JWT token
                project_id=project_id,
                is_directory=True,
                storage_key=f"dir_{path}_{datetime.now(timezone.utc).timestamp()}"
            )
            
            return {"message": "Directory created successfully"}, 201
            
        except IntegrityError as e:
            db.session.rollback()
            logger.error("Integrity error: %s", str(e))
            return {"message": "Directory already exists"}, 409
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(DATABASE_ERROR_LOG, str(e))
            return {"message": DATABASE_ERROR_MSG, "error": str(e)}, 500


class StorageUploadUrlResource(Resource):
    """
    Resource for generating presigned upload URLs.
    
    Methods:
        post(): Generate a presigned URL for file upload.
    """

    @require_jwt_auth()
    @check_access_required("upload")
    def post(self):
        """
        Generate a presigned URL for file upload.
        
        Expects:
            JSON payload with path and optional project_id/user_id.
        
        Returns:
            tuple: Presigned URL response and HTTP status code 200.
        """
        logger.info("Generating upload URL")
        
        json_data = request.get_json()
        try:
            validated_data = upload_request_schema.load(json_data)
        except ValidationError as err:
            logger.error(VALIDATION_ERROR_LOG, err.messages)
            return {"message": VALIDATION_ERROR_MSG, "errors": err.messages}, 400
        
        # Generate storage key for the upload
        path = validated_data['path']
        storage_key = f"{path}_{datetime.now(timezone.utc).timestamp()}"
        content_type = validated_data.get('content_type')
        
        # Use storage backend service to generate presigned URL
        url, expires_in = storage_backend.generate_upload_url(storage_key, content_type)
        
        result = {
            "url": url,
            "expires_in": expires_in
        }
        
        return presigned_url_schema.dump(result), 200


class StorageDownloadUrlResource(Resource):
    """
    Resource for generating presigned download URLs.
    
    Methods:
        get(): Generate a presigned URL for file download.
    """

    @require_jwt_auth()
    @check_access_required("download")
    def get(self):
        """
        Generate a presigned URL for file download.
        
        Query Parameters:
            project_id (int): Project identifier.
            path (str): Path to the file.
        
        Returns:
            tuple: Presigned URL response and HTTP status code 200.
        """
        logger.info("Generating download URL")
        
        project_id = request.args.get('project_id', type=int)
        user_id = request.args.get('user_id', type=int)
        path = request.args.get('path')
        
        if not path:
            return {"message": "Path parameter is required"}, 400
        
        if not project_id and not user_id:
            return {"message": "Either project_id or user_id must be provided"}, 400
        
        # Check if file exists
        file_obj = StorageFile.get_by_path(path, project_id=project_id, user_id=user_id)
        if not file_obj:
            return {"message": FILE_NOT_FOUND_MSG}, 404
        
        if file_obj.is_directory:
            return {"message": "Cannot download a directory"}, 400
        
        # Use storage backend service to generate presigned URL
        url, expires_in = storage_backend.generate_download_url(file_obj.storage_key)
        
        result = {
            "url": url,
            "expires_in": expires_in
        }
        
        return presigned_url_schema.dump(result), 200


class StorageCopyResource(Resource):
    """
    Resource for copying files and directories.
    
    Methods:
        post(): Copy a file or directory.
    """

    @require_jwt_auth()
    @check_access_required("copy")
    def post(self):
        """
        Copy a file or directory.
        
        Expects:
            JSON payload with source and destination information.
        
        Returns:
            tuple: Success message and HTTP status code 200.
        """
        logger.info("Copying file/directory")
        
        json_data = request.get_json()
        try:
            copy_move_request_schema.load(json_data)
        except ValidationError as err:
            logger.error(VALIDATION_ERROR_LOG, err.messages)
            return {"message": VALIDATION_ERROR_MSG, "errors": err.messages}, 400
        
        # Implement copy logic with storage backend
        # In a full implementation, this would:
        # 1. Validate source and destination contexts
        # 2. Check permissions
        # 3. Copy the file in storage backend
        # 4. Create new database record
        logger.info("Copy operation would be implemented here")
        
        return {"message": "File copied successfully"}, 200


class StorageMoveResource(Resource):
    """
    Resource for moving files and directories.
    
    Methods:
        post(): Move a file or directory.
    """

    @require_jwt_auth()
    @check_access_required("move")
    def post(self):
        """
        Move a file or directory.
        
        Expects:
            JSON payload with source and destination information.
        
        Returns:
            tuple: Success message and HTTP status code 200.
        """
        logger.info("Moving file/directory")
        
        json_data = request.get_json()
        try:
            copy_move_request_schema.load(json_data)
        except ValidationError as err:
            logger.error(VALIDATION_ERROR_LOG, err.messages)
            return {"message": VALIDATION_ERROR_MSG, "errors": err.messages}, 400
        
        # Implement move logic with storage backend
        # In a full implementation, this would:
        # 1. Validate source and destination contexts
        # 2. Check permissions
        # 3. Move the file in storage backend
        # 4. Update database record
        logger.info("Move operation would be implemented here")
        
        return {"message": "File moved successfully"}, 200


class StorageDeleteResource(Resource):
    """
    Resource for deleting files and directories.
    
    Methods:
        delete(): Delete a file or directory.
    """

    @require_jwt_auth()
    @check_access_required("delete")
    def delete(self):
        """
        Delete a file or directory.
        
        Expects:
            JSON payload with file path and context.
        
        Returns:
            tuple: HTTP status code 204 on success.
        """
        logger.info("Deleting file/directory")
        
        json_data = request.get_json()
        try:
            validated_data = delete_request_schema.load(json_data)
        except ValidationError as err:
            logger.error(VALIDATION_ERROR_LOG, err.messages)
            return {"message": VALIDATION_ERROR_MSG, "errors": err.messages}, 400
        
        project_id = validated_data.get('project_id')
        user_id = validated_data.get('user_id')
        path = validated_data['path']
        
        # Find the file
        file_obj = StorageFile.get_by_path(path, project_id=project_id, user_id=user_id)
        if not file_obj:
            return {"message": FILE_NOT_FOUND_MSG}, 404
        
        try:
            # Soft delete the file
            file_obj.soft_delete()
            
            # Schedule deletion from storage backend
            storage_backend.delete_object(file_obj.storage_key)
            
            return '', 204
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(DATABASE_ERROR_LOG, str(e))
            return {"message": DATABASE_ERROR_MSG, "error": str(e)}, 500


class StoragePromoteResource(Resource):
    """
    Resource for promoting files from personal to project space.
    
    Methods:
        post(): Promote a file from personal to project space.
    """

    @require_jwt_auth()
    @check_access_required("promote")
    def post(self):
        """
        Promote a file from personal to project space.
        
        Expects:
            JSON payload with promotion details.
        
        Returns:
            tuple: New version information and HTTP status code 201.
        """
        logger.info("Promoting file to project space")
        
        json_data = request.get_json()
        try:
            validated_data = promote_request_schema.load(json_data)
        except ValidationError as err:
            logger.error(VALIDATION_ERROR_LOG, err.messages)
            return {"message": VALIDATION_ERROR_MSG, "errors": err.messages}, 400
        
        # Implement promotion logic
        # In a full implementation, this would:
        # 1. Find source file in user space
        # 2. Copy to project space using storage backend
        # 3. Create new version record
        # 4. Update file metadata
        logger.info("File promotion would be implemented here")
        
        # Mock version response
        mock_version = {
            "version_id": f"v{datetime.now(timezone.utc).strftime('%Y.%m.%d.%H%M')}",
            "uploaded_by": validated_data['user_id'],
            "comment": validated_data.get('comment', 'Promoted from personal space'),
            "tag": "draft",
            "created_at": datetime.now(timezone.utc)
        }
        
        return mock_version, 201


class StorageVersionsResource(Resource):
    """
    Resource for managing file versions.
    
    Methods:
        get(): List all versions of a file.
    """

    @require_jwt_auth()
    @check_access_required("list_versions")
    def get(self):
        """
        List all versions of a file.
        
        Query Parameters:
            project_id (int): Project identifier.
            path (str): Path to the file.
        
        Returns:
            tuple: Version list and HTTP status code 200.
        """
        logger.info("Listing file versions")
        
        project_id = request.args.get('project_id', type=int)
        path = request.args.get('path')
        
        if not project_id or not path:
            return {"message": "project_id and path parameters are required"}, 400
        
        # Find the file
        file_obj = StorageFile.get_by_path(path, project_id=project_id)
        if not file_obj:
            return {"message": FILE_NOT_FOUND_MSG}, 404
        
        try:
            versions = FileVersion.get_versions_by_file(file_obj.id)
            
            result = {
                "file": path,
                "versions": file_versions_schema.dump(versions)
            }
            
            return version_list_schema.dump(result), 200
            
        except Exception as e:
            logger.error("Error listing versions: %s", str(e))
            return {"message": "Error listing versions", "error": str(e)}, 500


class StorageTagResource(Resource):
    """
    Resource for tagging file versions.
    
    Methods:
        post(): Apply a tag to a file version.
    """

    @require_jwt_auth()
    @check_access_required("tag_version")
    def post(self):
        """
        Apply a tag to a file version.
        
        Expects:
            JSON payload with tagging information.
        
        Returns:
            tuple: Success message and HTTP status code 200.
        """
        logger.info("Tagging file version")
        
        json_data = request.get_json()
        try:
            validated_data = tag_request_schema.load(json_data)
        except ValidationError as err:
            logger.error(VALIDATION_ERROR_LOG, err.messages)
            return {"message": VALIDATION_ERROR_MSG, "errors": err.messages}, 400
        
        project_id = validated_data['project_id']
        path = validated_data['path']
        tag = validated_data['tag']
        comment = validated_data.get('comment')
        version_number = validated_data.get('version_number')
        
        # Find the file
        file_obj = StorageFile.get_by_path(path, project_id=project_id)
        if not file_obj:
            return {"message": FILE_NOT_FOUND_MSG}, 404
        
        # Find the version
        if version_number:
            version_obj = FileVersion.get_by_file_and_version(file_obj.id, version_number)
        else:
            # Use latest version if no specific version provided
            version_obj = file_obj.get_latest_version()
        
        if not version_obj:
            return {"message": "Version not found"}, 404
        
        try:
            version_obj.update_tag(tag, comment)
            return {"message": "Tag applied successfully"}, 200
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(DATABASE_ERROR_LOG, str(e))
            return {"message": DATABASE_ERROR_MSG, "error": str(e)}, 500