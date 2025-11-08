# US-STORE-020 — Obtenir presigned URL pour upload

## Description

**En tant que** utilisateur du frontend  
**Je veux** pouvoir demander une URL présignée pour envoyer un fichier directement à MinIO  
**Afin de** uploader des fichiers de manière sécurisée sans transiter par le serveur d'API.

## Critères d'acceptation

### 1. Endpoint de demande d'URL
- [ ] Endpoint `POST /storage/upload-url` disponible
- [ ] Paramètres requis :
  - `bucket_type` : type de bucket (users/companies/projects)
  - `bucket_id` : identifiant du bucket
  - `path` : chemin de destination du fichier
  - `filename` : nom du fichier
  - `size` : taille du fichier en bytes
  - `mime_type` : type MIME du fichier

### 2. Validation de taille
- [ ] Validation taille ≤ 100 MiB (104,857,600 bytes)
- [ ] Retour d'erreur explicite si dépassement :
```json
{
  "status": "error",
  "message": "File size exceeds maximum allowed (100 MiB)",
  "details": {
    "max_size": 104857600,
    "provided_size": 150000000
  }
}
```

### 3. Création des métadonnées
- [ ] Création d'une entrée de métadonnées avec statut `draft` ou `upload_pending`
- [ ] Génération d'un `file_id` UUID pour référence future
- [ ] Stockage des métadonnées de base :
  - bucket_type, bucket_id, logical_path
  - filename, size, mime_type
  - owner_id (depuis JWT)
  - status: "upload_pending"

### 4. Génération URL présignée
- [ ] Génération d'une URL présignée PUT valide 15 minutes
- [ ] URL pointant vers l'objet MinIO avec clé unique
- [ ] Include des headers requis (Content-Type, Content-Length)

### 5. Structure de réponse
```json
{
  "status": "success",
  "data": {
    "file_id": "uuid",
    "upload_url": "https://minio.example.com/bucket/object-key?X-Amz-...",
    "expires_in": 900,
    "headers": {
      "Content-Type": "application/pdf",
      "Content-Length": "1024000"
    },
    "object_key": "projects/123/docs/document_20250101_uuid.pdf"
  }
}
```

### 6. Gestion des conflits
- [ ] Vérification que le fichier n'existe pas déjà au même path
- [ ] Option `overwrite=true/false` pour gérer l'écrasement
- [ ] Si le fichier existe et overwrite=false → retour 409 Conflict

### 7. Callback post-upload
- [ ] Endpoint `POST /storage/upload-confirm` pour confirmer l'upload
- [ ] Mise à jour du statut : `upload_pending` → `draft`
- [ ] Vérification que l'objet existe bien dans MinIO
- [ ] Mise à jour des métadonnées réelles (taille, checksum si disponible)

### 8. Nettoyage automatique
- [ ] Job de nettoyage des uploads non confirmés après 24h
- [ ] Suppression de l'objet MinIO et des métadonnées

## Priorité
**HIGH** - Fonctionnalité core

## Estimation
**5 points**

## Dépendances
- US-STORE-001 (structure de base)
- MinIO configuré avec presigned URLs
- Service Project pour validation des droits

## Tâches techniques
- [ ] Implémenter POST /storage/upload-url
- [ ] Implémenter POST /storage/upload-confirm  
- [ ] Ajouter validation de taille et type MIME
- [ ] Créer job de nettoyage des uploads orphelins
- [ ] Tests d'intégration avec MinIO réel
- [ ] Gérer l'expiration des URLs présignées