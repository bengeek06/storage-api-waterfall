"""
identity_helper.py
==================

Helper pour le service Identity permettant d'uploader un avatar utilisateur
vers le Storage Service.

Usage:
    from identity_helper import upload_user_avatar
    
    result = upload_user_avatar(
        user_id="6f9b3a34-07e3-4c5d-8f3a-1acb6e08f2d1",
        company_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        file_data=avatar_bytes,
        content_type="image/jpeg",
        filename="avatar.jpg"
    )
    
    # Stocker en DB
    user.avatar_bucket_type = result['bucket_type']
    user.avatar_bucket_id = result['bucket_id']
    user.avatar_logical_path = result['logical_path']
    user.avatar_object_key = result['object_key']  # Alternative
"""

import os
import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime

# Configuration
STORAGE_SERVICE_URL = os.getenv("STORAGE_SERVICE_URL", "http://storage-service:5000")
REQUEST_TIMEOUT = int(os.getenv("STORAGE_REQUEST_TIMEOUT", "10"))
MAX_AVATAR_SIZE = int(os.getenv("MAX_AVATAR_SIZE_MB", "5")) * 1024 * 1024

# Allowed MIME types for avatars
ALLOWED_AVATAR_TYPES = {
    "image/jpeg",
    "image/jpg", 
    "image/png",
    "image/webp",
    "image/gif"
}

logger = logging.getLogger(__name__)


class StorageServiceError(Exception):
    """Exception levée lors d'erreurs du Storage Service."""
    pass


class AvatarValidationError(Exception):
    """Exception levée lors d'erreurs de validation d'avatar."""
    pass


def validate_avatar(
    file_data: bytes,
    content_type: str,
    max_size: int = MAX_AVATAR_SIZE
) -> None:
    """
    Valide un fichier avatar.
    
    Args:
        file_data: Données binaires du fichier
        content_type: Type MIME du fichier
        max_size: Taille maximale en octets
        
    Raises:
        AvatarValidationError: Si la validation échoue
    """
    if not file_data:
        raise AvatarValidationError("Avatar file is empty")
    
    if len(file_data) > max_size:
        raise AvatarValidationError(
            f"Avatar too large: {len(file_data)} bytes "
            f"(max: {max_size} bytes = {max_size // 1024 // 1024} MB)"
        )
    
    if content_type not in ALLOWED_AVATAR_TYPES:
        raise AvatarValidationError(
            f"Invalid content type: {content_type}. "
            f"Allowed: {', '.join(ALLOWED_AVATAR_TYPES)}"
        )


def get_presigned_upload_url(
    user_id: str,
    company_id: str,
    logical_path: str,
    expires_in: int = 3600
) -> Dict[str, Any]:
    """
    Obtient une URL pré-signée pour uploader un avatar.
    
    Args:
        user_id: UUID de l'utilisateur
        company_id: UUID de l'entreprise
        logical_path: Chemin logique (ex: "avatars/user.jpg")
        expires_in: Durée de validité en secondes
        
    Returns:
        Dict contenant 'url', 'object_key', 'expires_in', 'expires_at'
        
    Raises:
        StorageServiceError: Si la requête échoue
    """
    url = f"{STORAGE_SERVICE_URL}/upload/presign"
    
    headers = {
        "X-User-ID": user_id,
        "X-Company-ID": company_id,
        "Content-Type": "application/json"
    }
    
    payload = {
        "bucket_type": "users",
        "bucket_id": user_id,
        "logical_path": logical_path,
        "expires_in": expires_in
    }
    
    try:
        logger.info(
            f"Requesting presigned URL for user {user_id}, path: {logical_path}"
        )
        
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        
        response.raise_for_status()
        data = response.json()
        
        logger.info(f"Presigned URL obtained, expires in {data['expires_in']}s")
        return data
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout calling Storage Service at {url}")
        raise StorageServiceError("Storage Service timeout") from None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Storage Service: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                error_msg = error_data.get('message', str(e))
            except Exception:
                error_msg = str(e)
        else:
            error_msg = str(e)
        raise StorageServiceError(f"Storage Service error: {error_msg}") from e


def upload_to_minio(
    presigned_url: str,
    file_data: bytes,
    content_type: str
) -> None:
    """
    Upload un fichier directement sur MinIO via URL pré-signée.
    
    Args:
        presigned_url: URL pré-signée obtenue du Storage Service
        file_data: Données binaires du fichier
        content_type: Type MIME du fichier
        
    Raises:
        StorageServiceError: Si l'upload échoue
    """
    headers = {
        "Content-Type": content_type,
        "Content-Length": str(len(file_data))
    }
    
    try:
        logger.info(f"Uploading {len(file_data)} bytes to MinIO")
        
        response = requests.put(
            presigned_url,
            data=file_data,
            headers=headers,
            timeout=REQUEST_TIMEOUT * 2  # Upload peut être plus long
        )
        
        response.raise_for_status()
        logger.info("Upload to MinIO successful")
        
    except requests.exceptions.Timeout:
        logger.error("Timeout uploading to MinIO")
        raise StorageServiceError("MinIO upload timeout") from None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error uploading to MinIO: {e}")
        raise StorageServiceError(f"MinIO upload error: {e}") from e


def upload_user_avatar(
    user_id: str,
    company_id: str,
    file_data: bytes,
    content_type: str,
    filename: str,
    validate: bool = True
) -> Dict[str, str]:
    """
    Upload complet d'un avatar utilisateur.
    
    Cette fonction effectue :
    1. Validation du fichier (optionnel)
    2. Demande d'URL pré-signée au Storage Service
    3. Upload direct sur MinIO
    4. Retour des métadonnées à stocker en DB
    
    Args:
        user_id: UUID de l'utilisateur
        company_id: UUID de l'entreprise
        file_data: Données binaires du fichier
        content_type: Type MIME (ex: "image/jpeg")
        filename: Nom du fichier original
        validate: Si True, valide le fichier avant upload
        
    Returns:
        Dict avec les clés suivantes à stocker en DB:
        {
            'bucket_type': 'users',
            'bucket_id': '<user_id>',
            'logical_path': 'avatars/<filename>',
            'object_key': 'users/<user_id>/avatars/<filename>/1',
            'uploaded_at': '2025-11-08T10:30:00Z'
        }
        
    Raises:
        AvatarValidationError: Si la validation échoue
        StorageServiceError: Si l'upload échoue
        
    Example:
        >>> result = upload_user_avatar(
        ...     user_id="abc-123",
        ...     company_id="def-456",
        ...     file_data=b"...",
        ...     content_type="image/jpeg",
        ...     filename="avatar.jpg"
        ... )
        >>> 
        >>> # Stocker en DB (Option 1: triplet)
        >>> user.avatar_bucket_type = result['bucket_type']
        >>> user.avatar_bucket_id = result['bucket_id']
        >>> user.avatar_logical_path = result['logical_path']
        >>> 
        >>> # Ou (Option 2: object_key)
        >>> user.avatar_object_key = result['object_key']
    """
    # 1. Validation
    if validate:
        validate_avatar(file_data, content_type)
    
    # 2. Construire le chemin logique
    # Format recommandé: avatars/{user_id}.{extension}
    extension = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    logical_path = f"avatars/{user_id}.{extension}"
    
    # 3. Obtenir URL pré-signée
    presigned_data = get_presigned_upload_url(
        user_id=user_id,
        company_id=company_id,
        logical_path=logical_path
    )
    
    # 4. Upload sur MinIO
    upload_to_minio(
        presigned_url=presigned_data['url'],
        file_data=file_data,
        content_type=content_type
    )
    
    # 5. Retourner les métadonnées
    return {
        'bucket_type': 'users',
        'bucket_id': user_id,
        'logical_path': logical_path,
        'object_key': presigned_data['object_key'],
        'uploaded_at': datetime.utcnow().isoformat() + 'Z'
    }


def delete_user_avatar(
    user_id: str,
    company_id: str,
    object_key: str
) -> None:
    """
    Supprime un avatar utilisateur (endpoint à implémenter côté Storage).
    
    Args:
        user_id: UUID de l'utilisateur
        company_id: UUID de l'entreprise
        object_key: Clé de l'objet à supprimer
        
    Raises:
        StorageServiceError: Si la suppression échoue
        NotImplementedError: Si l'endpoint n'est pas encore disponible
    """
    # TODO: À implémenter quand l'endpoint /delete sera disponible
    raise NotImplementedError(
        "L'endpoint DELETE /delete n'est pas encore implémenté dans Storage Service"
    )


# ============================================================================
# EXEMPLE D'INTÉGRATION DANS LE SERVICE IDENTITY
# ============================================================================

"""
# Dans app/resources/users.py du service Identity:

from identity_helper import upload_user_avatar, AvatarValidationError, StorageServiceError
from flask import request, g
from flask_restful import Resource

class UserResource(Resource):
    
    @require_jwt_auth()
    def patch(self, user_id):
        '''Update user profile, including avatar.'''
        
        # Vérifier que l'utilisateur modifie son propre profil
        if g.user_id != user_id:
            return {'error': 'Forbidden'}, 403
        
        user = User.query.get(user_id)
        if not user:
            return {'error': 'User not found'}, 404
        
        # Gérer l'upload d'avatar
        if 'avatar' in request.files:
            avatar_file = request.files['avatar']
            
            try:
                # Lire le fichier
                file_data = avatar_file.read()
                content_type = avatar_file.content_type or 'image/jpeg'
                filename = avatar_file.filename or 'avatar.jpg'
                
                # Upload vers Storage Service
                result = upload_user_avatar(
                    user_id=user_id,
                    company_id=g.company_id,
                    file_data=file_data,
                    content_type=content_type,
                    filename=filename
                )
                
                # Stocker en DB (choisir une des deux options)
                
                # Option 1: Triplet (recommandé)
                user.avatar_bucket_type = result['bucket_type']
                user.avatar_bucket_id = result['bucket_id']
                user.avatar_logical_path = result['logical_path']
                
                # Option 2: Object key (alternative)
                # user.avatar_object_key = result['object_key']
                
                user.avatar_uploaded_at = result['uploaded_at']
                db.session.commit()
                
                logger.info(f"Avatar uploaded for user {user_id}")
                
            except AvatarValidationError as e:
                logger.warning(f"Avatar validation failed: {e}")
                return {'error': str(e)}, 400
                
            except StorageServiceError as e:
                logger.error(f"Storage service error: {e}")
                return {'error': 'Failed to upload avatar'}, 500
        
        # Gérer les autres champs du PATCH...
        
        return {
            'id': user.id,
            'email': user.email,
            'avatar_url': f'/users/{user_id}/avatar',  # Endpoint à créer
            # ... autres champs
        }, 200


class UserAvatarResource(Resource):
    '''Endpoint pour servir l'avatar (proxy ou redirect).'''
    
    def get(self, user_id):
        user = User.query.get(user_id)
        if not user or not user.avatar_logical_path:
            return {'error': 'Avatar not found'}, 404
        
        # TODO: Appeler Storage Service pour obtenir une URL pré-signée
        # Puis faire un redirect 302 vers cette URL
        # Ou streamer le fichier directement
        
        # Temporaire: retourner les métadonnées
        return {
            'bucket_type': user.avatar_bucket_type,
            'bucket_id': user.avatar_bucket_id,
            'logical_path': user.avatar_logical_path
        }, 200
"""
