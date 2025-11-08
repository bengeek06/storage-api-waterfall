"""
test_integration_upload_download.py
====================================

Tests d'intégration pour les endpoints d'upload et download.
Teste les nouveaux endpoints /upload/proxy, /download/presign, /download/proxy.

Nécessite MinIO en cours d'exécution sur localhost:9000.
"""

import io
import uuid
import pytest
from werkzeug.datastructures import FileStorage
from app.models.storage import StorageFile, FileVersion


class TestUploadProxy:
    """Tests pour l'endpoint POST /upload/proxy."""

    def test_upload_proxy_success(self, client, db, test_user_id, test_company_id):
        """Test upload multipart via proxy."""
        # Données du fichier
        file_content = b"Test file content for upload proxy"
        filename = "test_proxy.txt"
        
        # Préparer le multipart avec FileStorage
        data = {
            'bucket_type': 'users',
            'bucket_id': test_user_id,
            'logical_path': 'uploads/test_proxy.txt',
            'file': FileStorage(
                stream=io.BytesIO(file_content),
                filename=filename,
                content_type='text/plain'
            )
        }
        
        # Upload via proxy
        response = client.post(
            '/upload/proxy',
            data=data,
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data['success'] is True
        assert 'file_id' in json_data['data']
        assert 'version_id' in json_data['data']
        assert json_data['data']['size'] == len(file_content)
        assert json_data['data']['filename'] == filename

    def test_upload_proxy_no_file(self, client, test_user_id, test_company_id):
        """Test upload sans fichier."""
        data = {
            'bucket_type': 'users',
            'bucket_id': test_user_id,
            'logical_path': 'uploads/test.txt'
        }
        
        response = client.post(
            '/upload/proxy',
            data=data,
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['error'] == 'NO_FILE'

    def test_upload_proxy_missing_fields(self, client, test_user_id, test_company_id):
        """Test upload avec champs manquants."""
        file_content = b"Test content"
        
        data = {
            'bucket_type': 'users',
            # bucket_id manquant
            'logical_path': 'uploads/test.txt',
            'file': FileStorage(stream=io.BytesIO(file_content), filename='test.txt', content_type='text/plain')
        }
        
        response = client.post(
            '/upload/proxy',
            data=data,
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['error'] == 'MISSING_FIELDS'

    def test_upload_proxy_wrong_bucket(self, client, test_user_id, test_company_id):
        """Test upload dans un bucket non autorisé."""
        file_content = b"Test content"
        wrong_user_id = str(uuid.uuid4())
        
        data = {
            'bucket_type': 'users',
            'bucket_id': wrong_user_id,  # Différent de test_user_id
            'logical_path': 'uploads/test.txt',
            'file': FileStorage(stream=io.BytesIO(file_content), filename='test.txt', content_type='text/plain')
        }
        
        response = client.post(
            '/upload/proxy',
            data=data,
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert response.status_code == 403

    def test_upload_proxy_companies_bucket(self, client, test_user_id, test_company_id):
        """Test upload dans le bucket companies."""
        file_content = b"Company file content"
        
        data = {
            'bucket_type': 'companies',
            'bucket_id': test_company_id,
            'logical_path': 'docs/company_doc.pdf',
            'file': FileStorage(stream=io.BytesIO(file_content), filename='company_doc.pdf', content_type='application/pdf')
        }
        
        response = client.post(
            '/upload/proxy',
            data=data,
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data['data']['size'] == len(file_content)


class TestDownloadPresign:
    """Tests pour l'endpoint GET /download/presign."""

    def test_download_presign_success(self, client, db, test_user_id, test_company_id, sample_file):
        """Test génération URL pré-signée pour download."""
        response = client.get(
            '/download/presign',
            query_string={
                'bucket_type': 'users',
                'bucket_id': test_user_id,
                'logical_path': sample_file.logical_path
            },
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert response.status_code == 200
        json_data = response.get_json()
        assert 'url' in json_data
        assert 'object_key' in json_data
        assert 'expires_in' in json_data
        assert 'expires_at' in json_data
        
        # Vérifier que l'URL contient le bucket MinIO
        assert 'localhost:9000' in json_data['url'] or 'minio' in json_data['url']

    def test_download_presign_file_not_found(self, client, test_user_id, test_company_id):
        """Test download d'un fichier inexistant."""
        response = client.get(
            '/download/presign',
            query_string={
                'bucket_type': 'users',
                'bucket_id': test_user_id,
                'logical_path': 'nonexistent/file.txt'
            },
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data['error'] == 'FILE_NOT_FOUND'

    def test_download_presign_no_permission(self, client, db, test_user_id, test_company_id, sample_file):
        """Test download sans permission."""
        wrong_user_id = str(uuid.uuid4())
        
        response = client.get(
            '/download/presign',
            query_string={
                'bucket_type': 'users',
                'bucket_id': test_user_id,  # Bucket d'un autre user
                'logical_path': sample_file.logical_path
            },
            headers={
                'X-User-ID': wrong_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert response.status_code == 403

    def test_download_presign_custom_expiry(self, client, db, test_user_id, test_company_id, sample_file):
        """Test download avec expiration personnalisée."""
        response = client.get(
            '/download/presign',
            query_string={
                'bucket_type': 'users',
                'bucket_id': test_user_id,
                'logical_path': sample_file.logical_path,
                'expires_in': 7200  # 2 heures
            },
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['expires_in'] == 7200


class TestDownloadProxy:
    """Tests pour l'endpoint GET /download/proxy."""

    def test_download_proxy_success(self, client, db, test_user_id, test_company_id, sample_file_with_content):
        """Test download via proxy (streaming)."""
        file_obj, original_content = sample_file_with_content
        
        response = client.get(
            '/download/proxy',
            query_string={
                'bucket_type': 'users',
                'bucket_id': test_user_id,
                'logical_path': file_obj.logical_path
            },
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert response.status_code == 200
        assert response.data == original_content
        assert 'Content-Disposition' in response.headers
        assert file_obj.filename in response.headers['Content-Disposition']

    def test_download_proxy_file_not_found(self, client, test_user_id, test_company_id):
        """Test download proxy d'un fichier inexistant."""
        response = client.get(
            '/download/proxy',
            query_string={
                'bucket_type': 'users',
                'bucket_id': test_user_id,
                'logical_path': 'nonexistent/file.txt'
            },
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert response.status_code == 404

    def test_download_proxy_no_permission(self, client, db, test_user_id, test_company_id, sample_file):
        """Test download proxy sans permission."""
        wrong_user_id = str(uuid.uuid4())
        
        response = client.get(
            '/download/proxy',
            query_string={
                'bucket_type': 'users',
                'bucket_id': test_user_id,
                'logical_path': sample_file.logical_path
            },
            headers={
                'X-User-ID': wrong_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert response.status_code == 403


class TestUploadDownloadFlow:
    """Tests du flux complet upload -> download."""

    def test_full_upload_download_flow(self, client, db, test_user_id, test_company_id):
        """Test flux complet: upload proxy -> download presign -> download proxy."""
        # 1. Upload via proxy
        original_content = b"Full flow test content with special chars: \xc3\xa9\xc3\xa0\xc3\xbc"
        filename = "full_flow_test.txt"
        
        upload_data = {
            'bucket_type': 'users',
            'bucket_id': test_user_id,
            'logical_path': 'tests/full_flow.txt',
            'file': FileStorage(stream=io.BytesIO(original_content), filename=filename, content_type='text/plain')
        }
        
        upload_response = client.post(
            '/upload/proxy',
            data=upload_data,
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert upload_response.status_code == 201
        upload_data = upload_response.get_json()
        file_id = upload_data['data']['file_id']
        
        # 2. Obtenir URL pré-signée
        presign_response = client.get(
            '/download/presign',
            query_string={
                'bucket_type': 'users',
                'bucket_id': test_user_id,
                'logical_path': 'tests/full_flow.txt'
            },
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert presign_response.status_code == 200
        presign_data = presign_response.get_json()
        assert 'url' in presign_data
        
        # 3. Download via proxy
        download_response = client.get(
            '/download/proxy',
            query_string={
                'bucket_type': 'users',
                'bucket_id': test_user_id,
                'logical_path': 'tests/full_flow.txt'
            },
            headers={
                'X-User-ID': test_user_id,
                'X-Company-ID': test_company_id
            }
        )
        
        assert download_response.status_code == 200
        assert download_response.data == original_content
