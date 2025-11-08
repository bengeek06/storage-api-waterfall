# US-STORE-010 — Lister et naviguer

## Description

**En tant que** utilisateur du frontend  
**Je veux** pouvoir afficher l'arborescence et la liste de fichiers d'un bucket (users/company/project) avec pagination  
**Afin de** naviguer facilement dans les fichiers et voir leur statut (locked, dernière version).

## Critères d'acceptation

### 1. Endpoint de listing
- [ ] Endpoint `GET /storage/list` disponible
- [ ] Paramètres supportés :
  - `bucket` : type de bucket (users/companies/projects)
  - `id` : identifiant du bucket (user_id/company_id/project_id)
  - `path` : chemin dans l'arborescence
  - `page` : numéro de page (défaut: 1)
  - `limit` : nombre d'éléments par page (défaut: 50, max: 200)

### 2. Données retournées
- [ ] Métadonnées complètes pour chaque fichier :
  - Nom, taille, type MIME, dates
  - Propriétaire, tags
- [ ] Flags d'état :
  - `locked` : booléen indiquant si le fichier est verrouillé
  - `latest_version` : booléen indiquant s'il s'agit de la dernière version
  - `status` : statut du fichier (draft, pending_validation, approved, rejected)

### 3. Structure de réponse
```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "uuid",
        "name": "document.pdf",
        "path": "/projects/123/docs/document.pdf",
        "size": 1024000,
        "mime_type": "application/pdf",
        "created_at": "2025-01-01T10:00:00Z",
        "updated_at": "2025-01-01T12:00:00Z",
        "owner_id": "user-uuid",
        "tags": ["important", "draft"],
        "locked": false,
        "latest_version": true,
        "status": "approved"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 50,
      "total": 150,
      "total_pages": 3
    }
  }
}
```

### 4. Filtres et tri
- [ ] Support du filtrage par :
  - Type de fichier (extension/mime_type)
  - Statut (locked/unlocked, approved/pending/rejected)
  - Tags
- [ ] Support du tri par :
  - Nom (alphabétique)
  - Date de création/modification
  - Taille

### 5. Performance
- [ ] Réponse en moins de 500ms pour 50 éléments
- [ ] Support de la pagination efficace (pas de OFFSET coûteux)

### 6. Autorisation
- [ ] Vérification des droits d'accès au bucket demandé
- [ ] Retour 403 si l'utilisateur n'a pas accès au bucket/path

## Priorité
**HIGH** - Fonctionnalité de base

## Estimation
**3 points**

## Dépendances
- US-STORE-001 (structure de base)
- Authentification JWT fonctionnelle

## Tâches techniques
- [ ] Implémenter l'endpoint GET /storage/list
- [ ] Optimiser les requêtes DB avec index sur path, bucket_type, owner_id
- [ ] Ajouter tests unitaires et d'intégration
- [ ] Documenter dans OpenAPI