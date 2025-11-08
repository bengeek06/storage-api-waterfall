# US-STORE-001 — Gestion documentaire collaborative (v1)

## Description

**En tant que** utilisateur du frontend de l'application de gestion de projets  
**Je veux** pouvoir parcourir, copier, éditer (via copie locale), versionner, verrouiller/déverrouiller, soumettre et valider des fichiers liés aux projets, entreprises et utilisateurs  
**Afin de** collaborer sur des fichiers projet sans conflit et garder un historique complet des versions avec un circuit de validation.

## Critères d'acceptation

### 1. API endpoints complets
- [ ] L'API expose tous les endpoints décrits dans l'OpenAPI :
  - Upload presigned/proxy
  - Download presigned/proxy  
  - List, metadata
  - Lock/unlock, list locks
  - Copy, commit version, list versions
  - Approve/reject, delete, move

### 2. Authentification et autorisation
- [ ] Toutes les requêtes sont authentifiées via JWT envoyé en cookie httpOnly
- [ ] Les endpoints sont protégés par le décorateur RBAC (vérifie permission sur endpoint/role)

### 3. Stockage MinIO structuré
- [ ] Les fichiers sont stockés dans MinIO avec buckets logiques : users, companies, projects
- [ ] Les chemins sont type `/users/{user_id}/...`, `/projects/{project_id}/...`, `/companies/{company_id}/...` (arborescence libre)

### 4. Validation de taille
- [ ] Taille max de fichier : 100 MiB (validation côté API)
- [ ] Refus explicite avec message d'erreur si dépassement

### 5. Mécanisme de verrouillage
- [ ] Copier un fichier depuis `projects/<project_id>/...` vers `users/<user_id>/...` :
  - Crée une copie physique
  - Crée une entrée DB locks qui marque le fichier source comme locked par user_id
- [ ] Tant que le fichier est locked, aucun autre utilisateur ne peut initier la même opération de copy (renvoi 409 Conflict)

### 6. Workflow de soumission
- [ ] Lorsque l'utilisateur soumet la nouvelle version via commit, le service :
  - Crée une nouvelle version (référence objet MinIO)
  - L'état du fichier passe `pending_validation`
  - Le lock est levé sur la ressource projet
  - La précédente version reste disponible en historique

### 7. Workflow de validation
- [ ] Le workflow de validation (approve/reject) est géré dans la DB de storage
- [ ] États : `pending_validation` → `approved` (validée) / `rejected`

### 8. Gestion des locks
- [ ] L'API fournit un endpoint pour lister les fichiers lockés
- [ ] Un endpoint admin pour forcer l'unlock (cas utilisateur supprimé ou sorti du projet)

### 9. Métadonnées complètes
- [ ] Les métadonnées sont stockées en Postgres et reliées aux objets MinIO :
  - owner, created_at, updated_at, modified_by
  - tags, mime_type, size, status

### 10. Audit trail
- [ ] Chaque action critique est tracée (audit log) :
  - Actions : lock, unlock, commit version, approve, reject, delete
  - Données : qui, quand, action, version_id (persistée en DB)

### 11. Gestion d'erreurs de service
- [ ] Si le service Project est unreachable lors d'une vérification d'accès :
  - L'API renvoie `{ "status":"error", "message": "project service unreachable" }` (HTTP 503)

### 12. Format de réponse standardisé
- [ ] Les endpoints renvoient la réponse standard :
  - Succès : `{ "status": "success", "data": ... }`
  - Erreur : `{ "status":"error","message":... }`

## Priorité
**HIGH** - User story principale

## Estimation
**13 points** (complexe)

## Dépendances
- Service Project pour vérification des droits d'accès
- MinIO opérationnel
- Base de données Postgres
- Système d'authentification JWT

## Notes techniques
- Implémentation progressive via les sous-stories US-STORE-010 à US-STORE-070
- Nécessite migration de la base pour les nouvelles tables (voir modèle de données)
- Tests d'intégration complets requis pour valider le workflow complet