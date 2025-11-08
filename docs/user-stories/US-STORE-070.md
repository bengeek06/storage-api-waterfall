# US-STORE-070 — Versions et historique

## Description

**En tant qu'** utilisateur  
**Je veux** pouvoir consulter toutes les versions d'un fichier et leur historique  
**Afin de** comprendre l'évolution du fichier, comparer les versions, et télécharger des versions spécifiques.

## Critères d'acceptation

### 1. Endpoint de listing des versions
- [ ] Endpoint `GET /storage/versions` disponible
- [ ] Paramètre requis : `file_id`
- [ ] Paramètres optionnels :
  - `include_drafts` : inclure les versions draft/rejected
  - `page`, `limit` : pagination
  - `sort` : tri par date (desc par défaut)

### 2. Informations complètes des versions
```json
{
  "status": "success",
  "data": {
    "file_id": "uuid",
    "file_path": "/projects/123/docs/document.pdf",
    "current_version_id": "uuid",
    "versions": [
      {
        "version_id": "uuid",
        "version_number": 3,
        "status": "approved",
        "size": 1024000,
        "mime_type": "application/pdf",
        "created_by": "user-uuid",
        "created_by_name": "John Doe", 
        "created_at": "2025-01-01T10:00:00Z",
        "changelog": "Updated financial projections",
        "is_current": true,
        "validation": {
          "state": "approved",
          "reviewed_by": "reviewer-uuid",
          "reviewed_by_name": "Jane Smith",
          "reviewed_at": "2025-01-01T11:00:00Z",
          "comment": "Approved after review"
        },
        "download_url": "https://api.example.com/storage/download/version/uuid?token=..."
      }
    ],
    "pagination": {...}
  }
}
```

### 3. Liens de téléchargement présignés
- [ ] Génération automatique d'URLs présignées pour chaque version
- [ ] URLs valides 15 minutes
- [ ] Possibilité de télécharger n'importe quelle version (si droits)
- [ ] Endpoint dédié : `GET /storage/download/version/{version_id}`

### 4. Comparaison de versions
- [ ] Endpoint `GET /storage/versions/compare` 
- [ ] Paramètres : `version_1`, `version_2`
- [ ] Réponse avec :
  - Métadonnées des deux versions
  - Différences de taille, date, auteur
  - Liens de téléchargement pour les deux versions

### 5. Métadonnées enrichies
- [ ] Pour chaque version, inclure :
  - Informations de validation (qui, quand, commentaire)
  - Tags appliqués à cette version
  - Changelog/description des modifications
  - Statistiques (taille, checksum si disponible)
  - Statut (draft, pending, approved, rejected, archived)

### 6. Historique des actions
- [ ] Endpoint `GET /storage/audit/{file_id}`
- [ ] Timeline complète des actions sur le fichier :
  - Création, modifications, locks, validations
  - Qui a fait quoi et quand
  - Commentaires associés

### 7. Gestion des versions archivées
- [ ] Possibilité de marquer des anciennes versions comme "archived"
- [ ] Les versions archivées restent accessibles mais séparées
- [ ] Politique de rétention configurable par projet

### 8. Endpoint de restauration
- [ ] Endpoint `POST /storage/versions/{version_id}/restore`
- [ ] Créer une nouvelle version basée sur une version antérieure
- [ ] Nécessite validation si configuré
- [ ] Audit trail complet de la restauration

### 9. Performance et optimisation
- [ ] Pagination efficace pour les fichiers avec beaucoup de versions
- [ ] Cache des métadonnées fréquemment consultées
- [ ] Réponse en moins de 300ms pour l'historique standard

### 10. Filtres avancés
- [ ] Filtrage par :
  - Auteur de la version
  - Période de création
  - Statut de validation
  - Présence de tags spécifiques
- [ ] Recherche dans les changelogs

### 11. Export de l'historique
- [ ] Endpoint `GET /storage/history/{file_id}/export`
- [ ] Format CSV ou JSON
- [ ] Historique complet avec audit trail
- [ ] Utile pour compliance/archivage

## Priorité
**MEDIUM** - Fonctionnalité avancée

## Estimation
**5 points**

## Dépendances
- US-STORE-040 (système de versions)
- US-STORE-050 (validation workflow)
- Tables file_versions, validations, audit_logs
- Presigned URLs configurés

## Tâches techniques
- [ ] Implémenter GET /storage/versions avec pagination
- [ ] Implémenter GET /storage/versions/compare
- [ ] Implémenter GET /storage/audit/{file_id}
- [ ] Implémenter POST /storage/versions/{id}/restore
- [ ] Optimiser les requêtes avec jointures complexes
- [ ] Cache pour métadonnées fréquentes
- [ ] Tests de performance avec historiques volumineux
- [ ] Export CSV/JSON de l'historique