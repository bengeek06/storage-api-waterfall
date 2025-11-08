# Flask API Template

![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Flask](https://img.shields.io/badge/flask-%3E=2.0-green.svg)
![License](https://img.shields.io/badge/license-AGPLv3-blue.svg)
![CI](https://img.shields.io/github/actions/workflow/status/<your-username>/flask_api_template/ci.yml?branch=main)
![Coverage](https://img.shields.io/badge/coverage-pytest-yellow.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)

Le service **`storage_service`** fournit une API REST sécurisée pour la **gestion documentaire** de l’application.  
Il permet de stocker, versionner et verrouiller des fichiers liés à des utilisateurs, des entreprises et des projets, tout en assurant un suivi via des **métadonnées stockées dans PostgreSQL** et des fichiers hébergés dans **MinIO**.


---

## Features

- Centraliser le stockage de tous les fichiers utilisateurs et projets.  
- Gérer les **versions**, **locks** et **métadonnées**.  
- Permettre un **workflow de validation** (soumission → relecture → approbation).  
- Fournir une **API simple** utilisable directement depuis le frontend.  
- Déléguer les permissions aux services **RBAC** (endpoint access) et **Projects** (contexte projet).

---

## Environments

The application behavior is controlled by the `FLASK_ENV` environment variable.  
Depending on its value, different configuration classes and `.env` files are loaded:

- **development** (default):  
  Loads `.env.development` and uses `app.config.DevelopmentConfig`.  
  Debug mode is enabled.

- **testing**:  
  Loads `.env.test` and uses `app.config.TestingConfig`.  
  Testing mode is enabled.

- **staging**:  
  Loads `.env.staging` and uses `app.config.StagingConfig`.  
  Debug mode is enabled.

- **production**:  
  Loads `.env.production` and uses `app.config.ProductionConfig`.  
  Debug mode is disabled.

See `app/config.py` for details.  
You can use `env.example` as a template for your environment files.

---



---

## 🔌 Intégrations

### Service Identity - Upload Avatar

Le service Identity peut utiliser le Storage Service pour gérer les avatars utilisateur.

📖 **Documentation complète :** [`docs/IDENTITY_INTEGRATION.md`](docs/IDENTITY_INTEGRATION.md)

**Quick Start :**
```python
# Helper prêt à l'emploi dans docs/identity_helper.py
from identity_helper import upload_user_avatar

result = upload_user_avatar(
    user_id="uuid",
    company_id="uuid", 
    file_data=avatar_bytes,
    content_type="image/jpeg",
    filename="avatar.jpg"
)

# Stocker en DB
user.avatar_object_key = result['object_key']
```

**Workflow :**
1. POST `/upload/presign` → obtenir URL pré-signée
2. PUT sur MinIO → upload direct du binaire
3. Stocker `object_key` ou triplet `(bucket_type, bucket_id, logical_path)` en DB

---

## 🧩 Architecture

```
┌────────────────────────────────────────────┐
│                Frontend                    │
│  (Appels API avec cookie JWT sécurisé)     │
└────────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────┐
│            storage_service (Python)        │
│ - API REST /storage                        │
│ - Gestion métadonnées (PostgreSQL)         │
│ - Accès fichiers (MinIO)                   │
│ - Versioning / Locks / Validation           │
│ - Vérification JWT et RBAC                 │
└────────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────┐    ┌─────────────────────┐
│     MinIO (S3)     │    │  PostgreSQL Metadata │
│  users_files/       │    │  → files, versions   │
│  company_files/     │    │  → locks, status     │
│  project_files/     │    │  → audit logs        │
└────────────────────┘    └─────────────────────┘
```

## 🪣 Buckets et Arborescence

Trois buckets principaux existent :

| Bucket | Usage | Exemple de chemin |
|--------|--------|------------------|
| `users` | fichiers personnels | `/users/<user_id>/notes/todo.txt` |
| `companies` | documents d'entreprise | `/companies/<company_id>/policies/hr.pdf` |
| `projects` | fichiers liés à un projet | `/projects/<project_id>/designs/cad/part.sldprt` |

Chaque fichier est identifié par un **chemin logique** et possède des **métadonnées** versionnées.

---

## 🧱 Métadonnées stockées

Exemple de structure :

| Champ | Type | Description |
|-------|------|-------------|
| `id` | UUID | identifiant du fichier |
| `bucket` | enum(users/companies/projects) | bucket concerné |
| `path` | text | chemin logique du fichier |
| `version` | int | version courante |
| `owner_id` | UUID | utilisateur créateur |
| `locked_by` | UUID nullable | utilisateur ayant locké |
| `status` | enum(draft, pending_validation, validated, archived) | état du fichier |
| `tags` | jsonb | données additionnelles |
| `created_at` | timestamp | date création |
| `updated_at` | timestamp | dernière modification |

## API Endpoints

| Fonction | Endpoint | Description |
|-----------|-----------|-------------|
| **Système** | | |
| Santé du service | `GET /health` | Vérifie l'état du service |
| Version | `GET /version` | Retourne la version de l'API |
| Configuration | `GET /config` | Configuration publique |
| **Fichiers** | | |
| Lister les fichiers | `GET /list` | Parcourt un répertoire |
| Métadonnées | `GET /metadata` | Informations complètes du fichier |
| **Upload** | | |
| URL pré-signée upload | `POST /upload/presign` | Génère une URL pour upload direct |
| Upload via proxy | `POST /upload/proxy` | Upload via le service (multipart) |
| **Download** | | |
| URL pré-signée download | `GET /download/presign` | Génère une URL pour download direct |
| Download via proxy | `GET /download/proxy` | Download via le service |
| **Collaboration** | | |
| Copier un fichier | `POST /copy` | Copie vers workspace utilisateur |
| Verrouiller | `POST /lock` | Verrouille un fichier |
| Déverrouiller | `POST /unlock` | Libère un verrou |
| Lister les verrous | `GET /locks` | Liste des fichiers verrouillés |
| **Versioning** | | |
| Lister les versions | `GET /versions` | Historique des versions |
| Créer nouvelle version | `POST /versions/commit` | Soumet une nouvelle version |
| Approuver version | `POST /versions/{version_id}/approve` | Valide une version |
| Rejeter version | `POST /versions/{version_id}/reject` | Rejette une version |
| **Administration** | | |
| Supprimer fichier | `DELETE /delete` | Supprime définitivement |

See [`openapi.yml`](openapi.yml) for full documentation and schema details.

### Détails des endpoints Upload/Download

#### POST `/upload/presign` - Obtenir une URL pré-signée pour upload

**Description** : Génère une URL pré-signée MinIO pour permettre un upload direct depuis le client (évite de passer par le proxy du service).

**Requête** :
```http
POST /upload/presign
Content-Type: application/json
Cookie: <JWT token>

{
  "bucket_type": "users|companies|projects",
  "bucket_id": "uuid",
  "logical_path": "/documents/report.pdf",
  "content_type": "application/pdf"  // optionnel
}
```

**Réponse succès (200)** :
```json
{
  "status": "success",
  "upload_url": "https://minio:9000/users-files/uuid/documents/report.pdf?X-Amz-Signature=...",
  "expires_in": 900,
  "object_key": "uuid/documents/report.pdf",
  "file_id": "uuid-of-file-record"
}
```

**Erreurs** :
- `400` : Paramètres manquants ou invalides
- `401` : JWT manquant ou invalide
- `403` : Accès refusé au bucket (permissions insuffisantes)
- `500` : Erreur MinIO

**Utilisation** :
```bash
# 1. Obtenir l'URL pré-signée
curl -X POST http://localhost:5000/upload/presign \
  -H "Content-Type: application/json" \
  -H "Cookie: jwt_token=..." \
  -d '{"bucket_type":"users","bucket_id":"uuid","logical_path":"/docs/file.pdf"}'

# 2. Uploader directement sur MinIO
curl -X PUT "<upload_url>" \
  -H "Content-Type: application/pdf" \
  --data-binary @file.pdf
```

---

#### POST `/upload/proxy` - Upload via le service

**Description** : Upload un fichier en passant par le service (multipart/form-data). Le service transfère le fichier vers MinIO et crée les métadonnées.

**Requête** :
```http
POST /upload/proxy
Content-Type: multipart/form-data
Cookie: <JWT token>

bucket_type=users
bucket_id=uuid
logical_path=/documents/report.pdf
file=@report.pdf
```

**Réponse succès (200)** :
```json
{
  "status": "success",
  "message": "File uploaded successfully",
  "file_id": "uuid",
  "object_key": "uuid/documents/report.pdf",
  "version_id": "uuid-version",
  "size": 524288
}
```

**Erreurs** :
- `400` : Fichier manquant, paramètres invalides
- `401` : JWT manquant ou invalide
- `403` : Accès refusé au bucket
- `413` : Fichier trop volumineux
- `500` : Erreur MinIO ou base de données

**Utilisation** :
```bash
curl -X POST http://localhost:5000/upload/proxy \
  -H "Cookie: jwt_token=..." \
  -F "bucket_type=users" \
  -F "bucket_id=uuid" \
  -F "logical_path=/docs/file.pdf" \
  -F "file=@file.pdf"
```

---

#### GET `/download/presign` - Obtenir une URL pré-signée pour download

**Description** : Génère une URL pré-signée MinIO pour permettre un téléchargement direct depuis le client.

**Requête** :
```http
GET /download/presign?bucket_type=users&bucket_id=uuid&logical_path=/documents/report.pdf
Cookie: <JWT token>
```

**Paramètres query** :
- `bucket_type` (requis) : `users`, `companies`, ou `projects`
- `bucket_id` (requis) : UUID du propriétaire
- `logical_path` (requis) : Chemin du fichier
- `version_id` (optionnel) : UUID d'une version spécifique

**Réponse succès (200)** :
```json
{
  "status": "success",
  "download_url": "https://minio:9000/users-files/uuid/documents/report.pdf?X-Amz-Signature=...",
  "expires_in": 900,
  "file_id": "uuid",
  "filename": "report.pdf",
  "size": 524288
}
```

**Erreurs** :
- `400` : Paramètres manquants
- `401` : JWT manquant ou invalide
- `403` : Accès refusé au fichier
- `404` : Fichier introuvable
- `500` : Erreur MinIO

**Utilisation** :
```bash
# 1. Obtenir l'URL pré-signée
curl -X GET "http://localhost:5000/download/presign?bucket_type=users&bucket_id=uuid&logical_path=/docs/file.pdf" \
  -H "Cookie: jwt_token=..."

# 2. Télécharger directement depuis MinIO
curl -X GET "<download_url>" -o file.pdf
```

---

#### GET `/download/proxy` - Télécharger via le service

**Description** : Télécharge un fichier en passant par le service (streaming). Le service récupère le fichier depuis MinIO et le transmet au client.

**Requête** :
```http
GET /download/proxy?bucket_type=users&bucket_id=uuid&logical_path=/documents/report.pdf
Cookie: <JWT token>
```

**Paramètres query** :
- `bucket_type` (requis) : `users`, `companies`, ou `projects`
- `bucket_id` (requis) : UUID du propriétaire
- `logical_path` (requis) : Chemin du fichier
- `version_id` (optionnel) : UUID d'une version spécifique

**Réponse succès (200)** :
```http
Content-Type: application/pdf
Content-Disposition: attachment; filename="report.pdf"
Content-Length: 524288

<binary data>
```

**Erreurs** :
- `400` : Paramètres manquants
- `401` : JWT manquant ou invalide
- `403` : Accès refusé au fichier
- `404` : Fichier introuvable
- `500` : Erreur MinIO

**Utilisation** :
```bash
curl -X GET "http://localhost:5000/download/proxy?bucket_type=users&bucket_id=uuid&logical_path=/docs/file.pdf" \
  -H "Cookie: jwt_token=..." \
  -o file.pdf
```

---

#### DELETE `/delete` - Supprimer un fichier

**Description** : Supprime définitivement un fichier (métadonnées + binaire MinIO). Effectue d'abord une suppression logique (status='archived'), puis suppression physique si demandée.

**Requête** :
```http
DELETE /delete
Content-Type: application/json
Cookie: <JWT token>

{
  "bucket_type": "users|companies|projects",
  "bucket_id": "uuid",
  "logical_path": "/documents/report.pdf",
  "force": false,  // optionnel, défaut: false
  "physical": false  // optionnel, défaut: false
}
```

**Paramètres** :
- `force` : Si `true`, supprime même si le fichier est verrouillé
- `physical` : Si `true`, supprime aussi le binaire de MinIO (irréversible)

**Réponse succès (200)** :
```json
{
  "status": "success",
  "message": "File archived successfully",
  "file_id": "uuid",
  "archived": true,
  "physical_deletion": false
}
```

**Avec `physical=true`** :
```json
{
  "status": "success",
  "message": "File permanently deleted",
  "file_id": "uuid",
  "archived": true,
  "physical_deletion": true,
  "versions_deleted": 3
}
```

**Erreurs** :
- `400` : Paramètres manquants
- `401` : JWT manquant ou invalide
- `403` : Accès refusé (permissions insuffisantes ou fichier verrouillé sans `force`)
- `404` : Fichier introuvable
- `500` : Erreur MinIO ou base de données

**Utilisation** :
```bash
# Suppression logique (archive)
curl -X DELETE http://localhost:5000/delete \
  -H "Content-Type: application/json" \
  -H "Cookie: jwt_token=..." \
  -d '{"bucket_type":"users","bucket_id":"uuid","logical_path":"/docs/file.pdf"}'

# Suppression physique définitive
curl -X DELETE http://localhost:5000/delete \
  -H "Content-Type: application/json" \
  -H "Cookie: jwt_token=..." \
  -d '{"bucket_type":"users","bucket_id":"uuid","logical_path":"/docs/file.pdf","physical":true}'
```

---

#### GET `/locks` - Lister les fichiers verrouillés

**Description** : Liste tous les fichiers verrouillés dans un bucket, avec possibilité de filtrage par chemin.

**Requête** :
```http
GET /locks?bucket_type=users&bucket_id=uuid&path_prefix=/documents/
Cookie: <JWT token>
```

**Paramètres query** :
- `bucket_type` (requis) : `users`, `companies`, ou `projects`
- `bucket_id` (requis) : UUID du propriétaire
- `path_prefix` (optionnel) : Filtre les fichiers par préfixe de chemin

**Réponse succès (200)** :
```json
{
  "status": "success",
  "locks": [
    {
      "file_id": "uuid1",
      "logical_path": "/documents/report.pdf",
      "locked_by": "uuid-user",
      "locked_by_username": "john.doe@example.com",
      "locked_at": "2024-01-15T10:30:00Z",
      "current_version_id": "uuid-version"
    },
    {
      "file_id": "uuid2",
      "logical_path": "/documents/specs.docx",
      "locked_by": "uuid-user2",
      "locked_by_username": "jane.smith@example.com",
      "locked_at": "2024-01-16T14:20:00Z",
      "current_version_id": "uuid-version2"
    }
  ],
  "total": 2
}
```

**Erreurs** :
- `400` : Paramètres manquants
- `401` : JWT manquant ou invalide
- `403` : Accès refusé au bucket
- `500` : Erreur base de données

**Utilisation** :
```bash
# Lister tous les fichiers verrouillés dans un bucket
curl -X GET "http://localhost:5000/locks?bucket_type=projects&bucket_id=uuid" \
  -H "Cookie: jwt_token=..."

# Lister les fichiers verrouillés dans un sous-dossier
curl -X GET "http://localhost:5000/locks?bucket_type=projects&bucket_id=uuid&path_prefix=/designs/" \
  -H "Cookie: jwt_token=..."
```

---

## 🔄 Workflows typiques

### 📁 1. Upload direct avec URL pré-signée

```bash
# Étape 1 : Obtenir URL pré-signée
curl -X POST http://localhost:5000/upload/presign \
  -H "Content-Type: application/json" \
  -H "Cookie: jwt_token=..." \
  -d '{
    "bucket_type": "projects",
    "bucket_id": "5678",
    "logical_path": "/docs/specifications_v1.pdf",
    "content_type": "application/pdf"
  }'

# Réponse
{
  "status": "success",
  "upload_url": "https://minio:9000/projects-files/5678/docs/specifications_v1.pdf?X-Amz-Signature=...",
  "expires_in": 900,
  "object_key": "5678/docs/specifications_v1.pdf",
  "file_id": "uuid"
}

# Étape 2 : Upload direct sur MinIO
curl -X PUT "<upload_url>" \
  -H "Content-Type: application/pdf" \
  --data-binary @specifications_v1.pdf
```

### 📁 2. Upload via proxy (plus simple, mais plus lent)

```bash
curl -X POST http://localhost:5000/upload/proxy \
  -H "Cookie: jwt_token=..." \
  -F "bucket_type=projects" \
  -F "bucket_id=5678" \
  -F "logical_path=/docs/specifications_v1.pdf" \
  -F "file=@specifications_v1.pdf"

# Réponse
{
  "status": "success",
  "message": "File uploaded successfully",
  "file_id": "uuid",
  "object_key": "5678/docs/specifications_v1.pdf",
  "version_id": "uuid-version",
  "size": 524288
}
```

### 📥 3. Téléchargement direct avec URL pré-signée

```bash
# Étape 1 : Obtenir URL pré-signée
curl -X GET "http://localhost:5000/download/presign?bucket_type=projects&bucket_id=5678&logical_path=/docs/specifications_v1.pdf" \
  -H "Cookie: jwt_token=..."

# Réponse
{
  "status": "success",
  "download_url": "https://minio:9000/projects-files/5678/docs/specifications_v1.pdf?X-Amz-Signature=...",
  "expires_in": 900,
  "file_id": "uuid",
  "filename": "specifications_v1.pdf",
  "size": 524288
}

# Étape 2 : Télécharger depuis MinIO
curl -X GET "<download_url>" -o specifications_v1.pdf
```

### 📥 4. Téléchargement via proxy

```bash
curl -X GET "http://localhost:5000/download/proxy?bucket_type=projects&bucket_id=5678&logical_path=/docs/specifications_v1.pdf" \
  -H "Cookie: jwt_token=..." \
  -o specifications_v1.pdf
```

### 🔒 5. Copier un fichier projet vers le répertoire personnel (lock automatique)

```http
POST /copy
Content-Type: application/json
Cookie: <JWT token>

{
  "source_bucket": "projects",
  "source_path": "/projects/5678/docs/specifications_v1.pdf",
  "target_bucket": "users",
  "target_path": "/users/1234/work/specifications_v1.pdf"
}
```

### ✏️ 6. Modifier le fichier localement et créer une nouvelle version

```http
POST /versions/commit
Content-Type: application/json
Cookie: <JWT token>

{
  "source_bucket": "users",
  "source_path": "/users/1234/work/specifications_v1.pdf",
  "target_bucket": "projects", 
  "target_path": "/projects/5678/docs/specifications_v1.pdf",
  "message": "Updated specifications with new requirements"
}
```

### ✅ 7. Approuver une version

```http
POST /versions/{version_id}/approve
Content-Type: application/json
Cookie: <JWT token>

{
  "comment": "Changes approved by team lead"
}
```

### 🗑️ 8. Supprimer un fichier

```bash
# Suppression logique (archive)
curl -X DELETE http://localhost:5000/delete \
  -H "Content-Type: application/json" \
  -H "Cookie: jwt_token=..." \
  -d '{
    "bucket_type": "projects",
    "bucket_id": "5678",
    "logical_path": "/docs/old_file.pdf"
  }'

# Suppression physique définitive (irréversible)
curl -X DELETE http://localhost:5000/delete \
  -H "Content-Type: application/json" \
  -H "Cookie: jwt_token=..." \
  -d '{
    "bucket_type": "projects",
    "bucket_id": "5678",
    "logical_path": "/docs/old_file.pdf",
    "physical": true
  }'
```

### 🗝️ 9. Gérer les verrous

```bash
# Lister les fichiers verrouillés
curl -X GET "http://localhost:5000/locks?bucket_type=projects&bucket_id=5678" \
  -H "Cookie: jwt_token=..."

# Réponse
{
  "status": "success",
  "locks": [
    {
      "file_id": "uuid",
      "logical_path": "/docs/specifications_v1.pdf",
      "locked_by": "uuid-user",
      "locked_by_username": "john.doe@example.com",
      "locked_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}

# Forcer un unlock
curl -X POST http://localhost:5000/unlock \
  -H "Content-Type: application/json" \
  -H "Cookie: jwt_token=..." \
  -d '{
    "bucket": "projects",
    "path": "/projects/5678/docs/specifications_v1.pdf",
    "force": true
  }'
```

---

## Project Structure

```
.
├── app
│   ├── config.py
│   ├── __init__.py
│   ├── logger.py
│   ├── models.py
│   ├── resources
│   │   ├── config.py
│   │   ├── dummy.py
│   │   ├── export_to.py
│   │   ├── import_from.py
│   │   ├── __init__.py
│   │   └── version.py
│   ├── routes.py
│   └── schemas.py
├── CODE_OF_CONDUCT.md
├── Dockerfile
├── env.example
├── LICENSE
├── migrations
│   ├── alembic.ini
│   ├── env.py
│   ├── README
│   └── script.py.mako
├── openapi.yml
├── pytest.ini
├── README.md
├── requirements-dev.txt
├── requirements.txt
├── run.py
├── tests
│   ├── conftest.py
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_init.py
│   ├── test_run.py
│   └── test_wsgi.py
├── TODO
├── wait-for-it.sh
└── wsgi.py
```

---

## Usage

### Local Development

1. Copy `env.example` to `.env.development` and set your variables.
2. Install dependencies:
   ```
   pip install -r requirements-dev.txt
   ```
3. Run database migrations:
   ```
   flask db upgrade
   ```
4. Start the server:
   ```
   FLASK_ENV=development python run.py
   ```

### Docker

Build and run the container:
```
docker build -t flask-api-template .
docker run --env-file .env.development -p 5000:5000 flask-api-template
```

### Testing

### Testing

#### Tests unitaires (rapides)
```bash
# Avec pytest directement
pytest tests/unit/ -v

# Ou avec le Makefile
make test-unit
```

#### Tests d'intégration (avec services Docker)
```bash
# Méthode recommandée avec le script automatique
./scripts/run_integration_tests.sh

# Ou avec le Makefile
make test-integration-script

# Ou étape par étape
make test-integration-setup  # Démarre Docker
make test-integration        # Lance les tests
make test-integration-teardown  # Nettoie
```

#### Tests complets
```bash
# Tous les tests (unitaires + intégration)
make test-all

# Tests avec couverture
make test-unit-coverage
```

#### Développement
```bash
# Démarrer l'environnement de développement complet
./scripts/start_dev.sh
# ou
make dev

# Tests en continu (watch mode)
make test-watch
```

### Scripts utiles

- `scripts/run_integration_tests.sh` : Lance les tests d'intégration complets
- `scripts/start_dev.sh` : Démarre l'environnement de développement
- `Makefile` : Commandes make pour toutes les tâches courantes

Run all tests with:
```
pytest
```

---

## � Contrôle d'accès et dépendances externes

Le service `storage_service` délègue les vérifications d'accès selon le type de bucket :

### Buckets `users` et `companies`
Vérification **locale** basée sur le JWT :
- **users** : `user_id` du token doit correspondre à `bucket_id`
- **companies** : `company_id` du token doit correspondre à `bucket_id`

### Bucket `projects`
Vérification **déléguée** au service `project` via API.

---

## 📡 Endpoints requis du service Project

Le service `project` doit exposer les endpoints suivants pour permettre au `storage_service` de vérifier les permissions :

### 1. Vérification d'accès unique

```http
POST /check-file-access
Content-Type: application/json
Cookie: <JWT token>

{
  "project_id": "uuid",
  "action": "read|write|delete|lock|validate",
  "file_id": "uuid"  // optionnel, pour audit logs
}
```

**Réponse succès (200)** :
```json
{
  "allowed": true,
  "role": "owner|admin|member|viewer"  // optionnel
}
```

**Réponse refusée (200)** :
```json
{
  "allowed": false,
  "reason": "insufficient_permissions"  // optionnel
}
```

**Actions supportées** :
- `read` : télécharger, lister fichiers
- `write` : uploader, copier fichiers
- `delete` : supprimer définitivement
- `lock` : verrouiller/déverrouiller
- `validate` : approuver/rejeter versions

### 2. Vérification d'accès batch (optimisation)

```http
POST /check-file-access/batch
Content-Type: application/json
Cookie: <JWT token>

{
  "checks": [
    {"project_id": "uuid1", "action": "read"},
    {"project_id": "uuid2", "action": "write"},
    {"project_id": "uuid1", "action": "delete", "file_id": "uuid3"}
  ]
}
```

**Réponse (200)** :
```json
{
  "results": [
    {"project_id": "uuid1", "action": "read", "allowed": true},
    {"project_id": "uuid2", "action": "write", "allowed": false},
    {"project_id": "uuid1", "action": "delete", "allowed": true}
  ]
}
```

### Politique de timeout

- **Timeout** : 2 secondes max
- **Fail-safe** : Si le service `project` est indisponible → **deny** (403)
- **Réponse API** : Message explicite `"project_service_unavailable"`

### Cache

Le service `project` **doit implémenter son propre cache** (Redis recommandé) pour les vérifications d'accès.  
Le `storage_service` ne cache pas ces réponses.

---

## �🔄 Workflows typiques

### 📁 1. Obtenir une URL pré-signée pour upload

```http
POST /upload/presign
Content-Type: application/json

{
  "bucket": "projects",
  "path": "/projects/5678/docs/specifications_v1.pdf",
  "content_type": "application/pdf"
}
```

### 📁 2. Upload direct via proxy

```http
POST /upload/proxy
Content-Type: multipart/form-data

bucket=projects
path=/projects/5678/docs/specifications_v1.pdf
file=@specifications_v1.pdf
```

### 🔒 3. Copier un fichier projet vers le répertoire personnel (lock automatique)

```http
POST /copy
Content-Type: application/json

{
  "source_bucket": "projects",
  "source_path": "/projects/5678/docs/specifications_v1.pdf",
  "target_bucket": "users",
  "target_path": "/users/1234/work/specifications_v1.pdf"
}
```

### ✏️ 4. Modifier le fichier localement et créer une nouvelle version

```http
POST /versions/commit
Content-Type: application/json

{
  "source_bucket": "users",
  "source_path": "/users/1234/work/specifications_v1.pdf",
  "target_bucket": "projects", 
  "target_path": "/projects/5678/docs/specifications_v1.pdf",
  "message": "Updated specifications with new requirements"
}
```

### ✅ 5. Approuver une version

```http
POST /versions/{version_id}/approve
Content-Type: application/json

{
  "comment": "Changes approved by team lead"
}
```

### 🗝️ 6. Forcer un unlock

```http
POST /unlock
Content-Type: application/json

{
  "bucket": "projects",
  "path": "/projects/5678/docs/specifications_v1.pdf",
  "force": true
}
```

### 🕵️ 7. Lister les fichiers verrouillés

```http
GET /locks?bucket=projects&path=/projects/5678/
```

---
## 🧾 Politique d'erreur

Toutes les erreurs suivent ce format :

```json
{
  "status": "error",
  "message": "project service unreachable"
}
```

Autres cas possibles :
- `missing_jwt_token`
- `unauthorized`
- `file_locked`
- `version_conflict`
- `bucket_not_found`
- `minio_unreachable`
- `project_service_unavailable` (timeout ou service down)
- `access_denied` (permissions insuffisantes)

---

## 🔗 Variables d'environnement

### Services externes

| Variable | Description | Exemple |
|----------|-------------|---------|
| `PROJECT_SERVICE_URL` | URL du service project pour vérification d'accès | `http://project-service:5001` |
| `MINIO_ENDPOINT` | Endpoint MinIO | `localhost:9000` |
| `MINIO_ACCESS_KEY` | Clé d'accès MinIO | `minioadmin` |
| `MINIO_SECRET_KEY` | Clé secrète MinIO | `minioadmin` |
| `DATABASE_URL` | URL PostgreSQL | `postgresql://user:pass@localhost/storage` |

Voir `env.example` pour la liste complète.

---


## License

This project is licensed under the GNU AGPLv3.

---

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
