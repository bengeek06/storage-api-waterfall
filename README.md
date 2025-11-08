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
| URL pré-signée download | `POST /download/presign` | Génère une URL pour download direct |
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

## 🔄 Workflows typiques

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

---


## License

This project is licensed under the GNU AGPLv3.

---

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
