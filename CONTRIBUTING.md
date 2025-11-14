# Contributing to Storage Service

Thank you for your interest in contributing to the **Storage Service**!

> **Note**: This service is part of the larger [Waterfall](../../README.md) project. For the overall development workflow, branch strategy, and contribution guidelines, please refer to the [main CONTRIBUTING.md](../../CONTRIBUTING.md) in the root repository.

## Table of Contents

- [Service Overview](#service-overview)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [API Development](#api-development)
- [S3/MinIO Integration](#s3minio-integration)
- [Common Tasks](#common-tasks)

## Service Overview

The **Storage Service** provides file storage and management with S3-compatible MinIO backend:

- **Technology Stack**: Python 3.13+, Flask 3.1+, MinIO (S3), PostgreSQL
- **Port**: 5005 (containerized) / 5000 (standalone)
- **Responsibilities**:
  - File upload and download
  - S3-compatible object storage via MinIO
  - File metadata management
  - Access control integration
  - Multi-tenant file isolation
  - Presigned URL generation

**Key Dependencies:**
- Flask 3.1+ for REST API
- Boto3 for S3/MinIO interaction
- SQLAlchemy for metadata storage
- PostgreSQL for metadata database
- MinIO for object storage

## Development Setup

### Prerequisites

- Python 3.13+
- PostgreSQL 16+ (for metadata)
- MinIO server (or use Docker)
- pip and virtualenv

### Local Setup

```bash
# Navigate to service directory
cd services/storage_service

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment configuration
cp env.example .env.development
```

### Environment Configuration

```bash
# Flask environment
FLASK_ENV=development
LOG_LEVEL=DEBUG

# Database (for metadata)
DATABASE_URL=postgresql://storage_user:storage_pass@localhost:5432/storage_dev

# MinIO/S3 configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false  # true for HTTPS
MINIO_REGION=us-east-1
DEFAULT_BUCKET=waterfall-files

# External services
GUARDIAN_SERVICE_URL=http://localhost:5003
INTERNAL_AUTH_TOKEN=dev-internal-secret

# Security
JWT_SECRET=dev-jwt-secret
MAX_UPLOAD_SIZE=104857600  # 100MB
```

### MinIO Setup

```bash
# Run MinIO with Docker
docker run -d \
  --name minio_dev \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# Access MinIO Console at http://localhost:9001
# API endpoint at http://localhost:9000
```

### Running the Service

```bash
# Development mode
python run.py

# Production-style
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

## Coding Standards

### Python Style Guide

Follow **PEP 8** with Black formatting:

```bash
# Format code
black app/ tests/

# Check quality
pylint app/ tests/

# Sort imports
isort app/ tests/
```

### Storage-Specific Conventions

**File Paths:**
```python
# Use consistent path structure: company_id/entity_type/entity_id/filename
def generate_object_key(company_id: int, entity_type: str, entity_id: int, filename: str) -> str:
    """Generate S3 object key with multi-tenant isolation.
    
    Args:
        company_id: Company ID for isolation
        entity_type: Type of entity (e.g., 'projects', 'users')
        entity_id: Entity's database ID
        filename: Original filename
    
    Returns:
        S3 object key path
    
    Example:
        >>> generate_object_key(5, 'projects', 123, 'document.pdf')
        '5/projects/123/document.pdf'
    """
    # Sanitize filename
    safe_filename = secure_filename(filename)
    return f"{company_id}/{entity_type}/{entity_id}/{safe_filename}"
```

**Content Type Detection:**
```python
import mimetypes

def detect_content_type(filename: str) -> str:
    """Detect content type from filename.
    
    Args:
        filename: Name of the file
    
    Returns:
        MIME type string
    """
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or 'application/octet-stream'
```

### Type Hints

```python
from typing import BinaryIO, Optional, Dict, Any
from datetime import datetime, timedelta

def upload_file(
    file_obj: BinaryIO,
    filename: str,
    company_id: int,
    entity_type: str,
    entity_id: int,
    metadata: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Upload file to MinIO storage.
    
    Args:
        file_obj: File-like object to upload
        filename: Original filename
        company_id: Company ID for multi-tenant isolation
        entity_type: Entity type (e.g., 'projects')
        entity_id: Entity's ID
        metadata: Optional metadata dictionary
    
    Returns:
        Dictionary with upload result including:
        - object_key: S3 object key
        - size: File size in bytes
        - content_type: MIME type
        - etag: S3 ETag
    """
    # Implementation
    pass
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific tests
pytest tests/test_upload.py -v
pytest tests/test_download.py -v
```

### Test Structure

```python
import pytest
from io import BytesIO
from app.services.storage_service import StorageService

class TestFileUpload:
    """Test suite for file upload functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self, minio_client):
        """Setup test bucket."""
        bucket_name = 'test-bucket'
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
        
        self.bucket = bucket_name
        
        yield
        
        # Cleanup: remove test objects
        objects = minio_client.list_objects(bucket_name, recursive=True)
        for obj in objects:
            minio_client.remove_object(bucket_name, obj.object_name)
    
    def test_upload_file_success(self, client):
        """Test successful file upload."""
        file_data = b"Test file content"
        file = BytesIO(file_data)
        
        response = client.post('/files/upload', data={
            'file': (file, 'test.txt'),
            'company_id': 1,
            'entity_type': 'projects',
            'entity_id': 123
        })
        
        assert response.status_code == 201
        data = response.json
        assert 'object_key' in data
        assert 'url' in data
        assert data['size'] == len(file_data)
    
    def test_upload_file_size_limit(self, client):
        """Test file size limit enforcement."""
        large_file = BytesIO(b"x" * (101 * 1024 * 1024))  # 101MB
        
        response = client.post('/files/upload', data={
            'file': (large_file, 'large.bin'),
            'company_id': 1,
            'entity_type': 'projects',
            'entity_id': 123
        })
        
        assert response.status_code == 413  # Payload Too Large
```

## API Development

### Upload Endpoint

```python
# app/resources/files.py
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from app.services.storage_service import StorageService
from app.logger import logger

files_bp = Blueprint('files', __name__)

@files_bp.route('/files/upload', methods=['POST'])
def upload_file():
    """Upload a file to storage.
    
    Form Data:
        file: File to upload
        company_id: Company ID
        entity_type: Entity type (e.g., 'projects')
        entity_id: Entity ID
        metadata: Optional JSON metadata
    
    Response:
        {
            "object_key": "5/projects/123/document.pdf",
            "url": "http://minio:9000/...",
            "size": 1024,
            "content_type": "application/pdf",
            "etag": "..."
        }
    """
    try:
        # Validate request
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Empty filename"}), 400
        
        # Get parameters
        company_id = int(request.form['company_id'])
        entity_type = request.form['entity_type']
        entity_id = int(request.form['entity_id'])
        
        # Upload file
        storage = StorageService()
        result = storage.upload_file(
            file_obj=file.stream,
            filename=file.filename,
            company_id=company_id,
            entity_type=entity_type,
            entity_id=entity_id
        )
        
        return jsonify(result), 201
        
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
```

### Download Endpoint

```python
@files_bp.route('/files/download/<path:object_key>', methods=['GET'])
def download_file(object_key):
    """Download a file from storage.
    
    URL Parameters:
        object_key: S3 object key
    
    Query Parameters:
        presigned: If true, return presigned URL instead of file
    
    Response:
        File content with appropriate headers
        OR
        { "url": "https://..." } if presigned=true
    """
    try:
        storage = StorageService()
        
        # Generate presigned URL if requested
        if request.args.get('presigned') == 'true':
            url = storage.get_presigned_url(object_key)
            return jsonify({"url": url}), 200
        
        # Stream file directly
        file_data, content_type = storage.download_file(object_key)
        
        return Response(
            file_data,
            mimetype=content_type,
            headers={
                'Content-Disposition': f'attachment; filename="{os.path.basename(object_key)}"'
            }
        )
        
    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 404
```

## S3/MinIO Integration

### MinIO Client Setup

```python
# app/services/storage_service.py
from minio import Minio
from flask import current_app

class StorageService:
    """Service for MinIO/S3 storage operations."""
    
    def __init__(self):
        """Initialize MinIO client."""
        self.client = Minio(
            endpoint=current_app.config['MINIO_ENDPOINT'],
            access_key=current_app.config['MINIO_ACCESS_KEY'],
            secret_key=current_app.config['MINIO_SECRET_KEY'],
            secure=current_app.config.get('MINIO_SECURE', False),
            region=current_app.config.get('MINIO_REGION', 'us-east-1')
        )
        self.bucket = current_app.config.get('DEFAULT_BUCKET', 'waterfall-files')
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist."""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
```

### Presigned URLs

```python
from datetime import timedelta

def get_presigned_url(
    self,
    object_key: str,
    expires: timedelta = timedelta(hours=1)
) -> str:
    """Generate presigned URL for temporary access.
    
    Args:
        object_key: S3 object key
        expires: URL expiration time
    
    Returns:
        Presigned URL string
    """
    url = self.client.presigned_get_object(
        bucket_name=self.bucket,
        object_name=object_key,
        expires=expires
    )
    return url
```

### File Metadata

```python
def get_object_metadata(self, object_key: str) -> Dict[str, Any]:
    """Get metadata for stored object.
    
    Returns:
        Dictionary with:
        - size: File size in bytes
        - last_modified: Last modification timestamp
        - content_type: MIME type
        - etag: S3 ETag
        - metadata: Custom metadata
    """
    stat = self.client.stat_object(self.bucket, object_key)
    return {
        'size': stat.size,
        'last_modified': stat.last_modified,
        'content_type': stat.content_type,
        'etag': stat.etag,
        'metadata': stat.metadata
    }
```

## Common Tasks

### Multi-tenant File Isolation

```python
def list_company_files(company_id: int, entity_type: Optional[str] = None) -> List[str]:
    """List all files for a company.
    
    Args:
        company_id: Company ID
        entity_type: Optional filter by entity type
    
    Returns:
        List of object keys
    """
    prefix = f"{company_id}/"
    if entity_type:
        prefix += f"{entity_type}/"
    
    objects = self.client.list_objects(
        bucket_name=self.bucket,
        prefix=prefix,
        recursive=True
    )
    
    return [obj.object_name for obj in objects]
```

### File Deletion

```python
def delete_file(self, object_key: str) -> bool:
    """Delete a file from storage.
    
    Args:
        object_key: S3 object key
    
    Returns:
        True if successful
    """
    try:
        self.client.remove_object(self.bucket, object_key)
        return True
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return False
```

## Service-Specific Guidelines

### Security Considerations

1. **Always validate company_id** from authenticated context
2. **Sanitize filenames** to prevent path traversal
3. **Enforce file size limits** to prevent abuse
4. **Scan files for malware** (future enhancement)
5. **Use presigned URLs** for temporary access

### Performance Optimization

1. **Stream large files** instead of loading into memory
2. **Use multipart uploads** for files > 5MB
3. **Implement caching** for frequently accessed files
4. **Consider CDN** for static assets

## Getting Help

- **Main Project**: See [root CONTRIBUTING.md](../../CONTRIBUTING.md)
- **Issues**: Use GitHub issues with `service:storage` label
- **Code of Conduct**: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- **Documentation**: [README.md](README.md)

---

**Remember**: Always refer to the [main CONTRIBUTING.md](../../CONTRIBUTING.md) for branch strategy, commit conventions, and pull request process!
