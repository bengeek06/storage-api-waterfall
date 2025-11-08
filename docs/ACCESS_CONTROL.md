# Système de Contrôle d'Accès

## Vue d'ensemble

Le service `storage_service` implémente un système de contrôle d'accès basé sur les buckets avec trois stratégies différentes :

1. **Buckets `users`** : Vérification locale (l'utilisateur ne peut accéder qu'à son propre répertoire)
2. **Buckets `companies`** : Vérification locale (l'utilisateur ne peut accéder qu'au répertoire de sa compagnie)
3. **Buckets `projects`** : Vérification déléguée au service `project`

## Architecture

```
┌─────────────────────────────────────────────┐
│         Client Request                      │
│  (Cookie JWT + bucket_type + bucket_id)     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│     @require_jwt_auth decorator             │
│  - Vérifie JWT (ou headers X-User-ID)       │
│  - Extrait user_id, company_id              │
│  - Stocke dans g.user_id, g.company_id      │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  @require_bucket_access('action') decorator │
│  - Extrait bucket_type, bucket_id           │
│  - Appelle check_bucket_access()            │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
┌──────────────┐    ┌────────────────────┐
│ users/       │    │ companies/         │
│ companies/   │    │                    │
│              │    │                    │
│ Vérification │    │ Vérification       │
│ locale :     │    │ locale :           │
│ bucket_id == │    │ bucket_id ==       │
│ user_id      │    │ company_id         │
└──────────────┘    └────────────────────┘
                   
                   ▼
        ┌──────────────────────┐
        │ projects/            │
        │                      │
        │ check_project_access()│
        │ ↓                    │
        │ HTTP POST →          │
        │ project-service      │
        │ /check-file-access   │
        └──────────────────────┘
```

## Fonctions Utilitaires

### `check_bucket_access(bucket_type, bucket_id, action, file_id=None)`

Fonction principale de vérification d'accès aux buckets.

**Paramètres:**
- `bucket_type` (str): Type de bucket ('users', 'companies', 'projects')
- `bucket_id` (str): ID du bucket (user_id, company_id, ou project_id)
- `action` (str): Action à effectuer ('read', 'write', 'delete', 'lock', 'validate')
- `file_id` (str, optional): ID du fichier pour logging d'audit

**Retourne:**
- `tuple`: (allowed (bool), error_message (str or None), status_code (int))

**Exemple:**
```python
from flask import g
from app.utils import check_bucket_access

# Dans une ressource Flask-RESTful
allowed, error, status = check_bucket_access('projects', project_id, 'write', file_id)
if not allowed:
    return {"error": error}, status
```

### `check_project_access(project_id, action, file_id=None)`

Délègue la vérification d'accès au service `project`.

**Paramètres:**
- `project_id` (str): UUID du projet
- `action` (str): Action ('read', 'write', 'delete', 'lock', 'validate')
- `file_id` (str, optional): ID du fichier pour audit

**Retourne:**
- `tuple`: (allowed (bool), error_message (str or None), status_code (int))

**Gestion des erreurs:**
- **Timeout (2s)**: Retourne `(False, "Project service unavailable (timeout)", 504)`
- **Service down**: Retourne `(False, "Project service unavailable", 502)`
- **Accès refusé**: Retourne `(False, "Access denied: {reason}", 403)`

### `check_project_access_batch(checks)`

Vérifie l'accès à plusieurs projets en une seule requête (optimisation).

**Paramètres:**
- `checks` (list): Liste de dicts `[{"project_id": "uuid", "action": "read", "file_id": "uuid"}]`

**Retourne:**
- `tuple`: (results (list), error_message (str or None), status_code (int))

**Exemple:**
```python
checks = [
    {"project_id": "proj-1", "action": "read"},
    {"project_id": "proj-2", "action": "write"}
]
results, error, status = check_project_access_batch(checks)
# results = [{"project_id": "proj-1", "action": "read", "allowed": True}, ...]
```

### `log_access_denied(bucket_type, bucket_id, action, reason, file_id=None)`

Enregistre un refus d'accès dans l'audit trail.

**Paramètres:**
- `bucket_type` (str): Type de bucket
- `bucket_id` (str): ID du bucket  
- `action` (str): Action refusée
- `reason` (str): Raison du refus
- `file_id` (str, optional): ID du fichier

**Note:** Cette fonction ne lève jamais d'exception. Si le logging échoue, l'erreur est simplement loggée.

## Décorateurs

### `@require_bucket_access('action')`

Décorateur pour protéger automatiquement les endpoints.

**Utilisation:**
```python
from flask_restful import Resource
from app.utils import require_jwt_auth, require_bucket_access

class FileUploadResource(Resource):
    @require_jwt_auth()
    @require_bucket_access('write')
    def post(self):
        # bucket_type et bucket_id déjà vérifiés
        # Disponibles dans g.bucket_type et g.bucket_id
        data = g.json_data
        # ... implémentation
```

**Ce que fait le décorateur:**
1. Extrait `bucket_type`, `bucket_id` (ou `project_id`), `file_id` du JSON
2. Appelle `check_bucket_access()`
3. Si refusé: log l'événement et retourne erreur 403
4. Si autorisé: stocke `g.bucket_type` et `g.bucket_id` et continue

**Attend dans le JSON:**
```json
{
  "bucket_type": "projects",
  "bucket_id": "uuid",  // ou "project_id": "uuid"
  "file_id": "uuid"     // optionnel
}
```

## Actions Supportées

| Action | Description | Exemples d'usage |
|--------|-------------|------------------|
| `read` | Lire, télécharger, lister | GET /list, GET /download |
| `write` | Créer, uploader, modifier | POST /upload, POST /copy |
| `delete` | Supprimer définitivement | DELETE /delete |
| `lock` | Verrouiller/déverrouiller | POST /lock, POST /unlock |
| `validate` | Approuver/rejeter versions | POST /versions/{id}/approve |

## Stratégies par Bucket

### Bucket `users`

```python
# Règle simple
allowed = (bucket_id == g.user_id)
```

**Exemple:**
- ✅ user-123 accède à `users/user-123/file.txt`
- ❌ user-123 accède à `users/user-456/file.txt`

### Bucket `companies`

```python
# Règle simple
allowed = (bucket_id == g.company_id)
```

**Exemple:**
- ✅ user-123 (company-abc) accède à `companies/company-abc/doc.pdf`
- ❌ user-123 (company-abc) accède à `companies/company-xyz/doc.pdf`

### Bucket `projects`

```python
# Délégation au service project
POST {PROJECT_SERVICE_URL}/check-file-access
{
  "project_id": "uuid",
  "action": "write",
  "file_id": "uuid"  // optionnel
}
```

**Réponse attendue:**
```json
{
  "allowed": true,
  "role": "admin"  // optionnel
}
```

## Gestion des Erreurs

### Codes de statut

| Code | Signification | Quand |
|------|---------------|-------|
| 200 | Accès autorisé | Toutes vérifications passées |
| 400 | Requête invalide | bucket_type ou bucket_id manquant |
| 403 | Accès refusé | Permissions insuffisantes |
| 502 | Service unavailable | Erreur du service project |
| 504 | Gateway timeout | Timeout du service project (>2s) |

### Messages d'erreur

```json
// Accès refusé - users
{
  "error": "Access denied: cannot access other users' files"
}

// Accès refusé - companies
{
  "error": "Access denied: cannot access other companies' files"
}

// Accès refusé - projects
{
  "error": "Access denied: insufficient_permissions"
}

// Service project indisponible
{
  "error": "Project service unavailable (timeout)"
}

// Bucket invalide
{
  "error": "Invalid bucket_type: invalid"
}
```

## Audit Trail

Tous les refus d'accès sont automatiquement enregistrés dans la table `audit_logs` :

```python
{
  "action": "access_denied",
  "user_id": "user-123",
  "file_id": "file-456",  // si fourni
  "details": {
    "bucket_type": "projects",
    "bucket_id": "proj-789",
    "action": "write",
    "reason": "insufficient_permissions",
    "access_denied": True
  },
  "ip_address": "192.168.1.10",
  "user_agent": "Mozilla/5.0...",
  "created_at": "2025-11-08T10:42:00Z"
}
```

## Configuration

### Variables d'environnement

```bash
# URL du service project
PROJECT_SERVICE_URL=http://project-service:5001

# Secret JWT pour décodage
JWT_SECRET=your-jwt-secret
```

### Timeout

Le timeout pour les appels au service project est fixé à **2 secondes**.

## Tests

### Tests unitaires

```bash
pytest tests/unit/test_access_control.py -v
```

**14 tests couvrent:**
- ✅ Accès users bucket (propre vs autre)
- ✅ Accès companies bucket (propre vs autre)
- ✅ Délégation projects bucket
- ✅ Appels au service project (succès, refus, timeout, erreur)
- ✅ Batch access checks

### Tests d'intégration

Les tests d'intégration utilisent le fallback headers (`X-User-ID`, `X-Company-ID`) en environnement testing.

## Exemple Complet

```python
from flask import g
from flask_restful import Resource
from app.utils import require_jwt_auth, require_bucket_access
from app.models.storage import StorageFile
from app.models.db import db

class FileUploadResource(Resource):
    """Upload a file to a bucket."""

    @require_jwt_auth()
    @require_bucket_access('write')
    def post(self):
        """
        POST /upload
        {
          "bucket_type": "projects",
          "bucket_id": "proj-123",
          "filename": "design.pdf"
        }
        """
        # Access already verified by decorator
        data = g.json_data
        bucket_type = g.bucket_type  # Set by decorator
        bucket_id = g.bucket_id      # Set by decorator
        
        # Create file record
        file = StorageFile(
            bucket_type=bucket_type,
            bucket_id=bucket_id,
            filename=data['filename'],
            owner_id=g.user_id,
            # ...
        )
        db.session.add(file)
        db.session.commit()
        
        return {"file_id": str(file.id)}, 201
```

## Performance

### Cache

Le service `storage` **ne cache pas** les résultats de vérification d'accès projet.  
Le service `project` **doit implémenter son propre cache** (Redis recommandé).

### Optimisation

Pour lister des fichiers dans plusieurs projets, utilisez `check_project_access_batch()` :

```python
# Au lieu de N appels
for file in files:
    allowed, _, _ = check_project_access(file.bucket_id, 'read')
    
# Un seul appel
checks = [{"project_id": f.bucket_id, "action": "read"} for f in files]
results, _, _ = check_project_access_batch(checks)
```

## Politique Fail-Safe

En cas d'indisponibilité du service project:

- ❌ **DENY** (refus par défaut)
- 🔒 Sécurité privilégiée sur disponibilité
- 📝 Erreur explicite retournée au client

**Rationale:** Mieux vaut refuser temporairement l'accès que risquer une fuite de données.
