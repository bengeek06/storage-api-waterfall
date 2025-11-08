# US-STORE-030 — Copier fichier projet → user (déclenche lock)

## Description

**En tant que** utilisateur avec accès à un projet  
**Je veux** pouvoir copier un fichier depuis un projet vers mon espace personnel  
**Afin de** l'éditer localement sans impacter les autres utilisateurs, avec verrouillage automatique du fichier source.

## Critères d'acceptation

### 1. Endpoint de copie
- [ ] Endpoint `POST /storage/copy` disponible
- [ ] Paramètres requis :
  - `source_path` : chemin source (ex: `/projects/123/docs/document.pdf`)
  - `destination_path` : chemin destination (ex: `/users/{user_id}/drafts/project_123/document.pdf`)
  - `lock_reason` : raison du verrouillage (optionnel)

### 2. Vérification des droits
- [ ] Check membership de l'utilisateur dans le projet via service Project
- [ ] Retour 403 si l'utilisateur n'a pas accès au projet
- [ ] Retour 503 si le service Project est unreachable :
```json
{
  "status": "error", 
  "message": "project service unreachable"
}
```

### 3. Vérification de l'état du fichier
- [ ] Vérification que le fichier source n'est pas déjà locked
- [ ] Si déjà locked → retour 409 Conflict :
```json
{
  "status": "error",
  "message": "File is already locked by another user",
  "details": {
    "locked_by": "user-uuid",
    "locked_at": "2025-01-01T10:00:00Z",
    "lock_reason": "Editing for review"
  }
}
```

### 4. Copie physique
- [ ] Création d'une copie physique du fichier dans MinIO
- [ ] Génération d'une nouvelle clé objet pour la destination
- [ ] Chemin de destination automatique : `/users/{user_id}/drafts/{project_id}/...`
- [ ] Préservation des métadonnées originales (mime_type, tags, etc.)

### 5. Verrouillage du fichier source
- [ ] Création d'une entrée dans la table `locks` :
  - `file_id` : ID du fichier source
  - `locked_by` : user_id de l'utilisateur
  - `locked_at` : timestamp actuel
  - `reason` : raison fournie ou "Copied for editing"
  - `forced` : false

### 6. Métadonnées de la copie
- [ ] Création d'une nouvelle entrée `files` pour la copie
- [ ] Lien de référence vers le fichier source (`source_file_id`)
- [ ] Statut initial : "draft"
- [ ] Owner : utilisateur qui fait la copie

### 7. Structure de réponse
```json
{
  "status": "success",
  "data": {
    "source_file_id": "uuid",
    "copy_file_id": "uuid",
    "copy_path": "/users/user-uuid/drafts/project_123/document.pdf",
    "lock_id": "uuid",
    "locked_at": "2025-01-01T10:00:00Z"
  }
}
```

### 8. Audit trail
- [ ] Enregistrement de l'action dans `audit_logs` :
  - Action : "file_copied_and_locked"
  - Entity : file source
  - Actor : user_id
  - Metadata : destination_path, lock_id

### 9. Gestion des chemins
- [ ] Création automatique de l'arborescence de destination si nécessaire
- [ ] Évitement des conflits de noms (suffixe numérique si nécessaire)
- [ ] Validation que la destination est bien dans l'espace user

## Priorité
**HIGH** - Workflow core

## Estimation
**8 points** (complexe avec vérifications multiples)

## Dépendances
- US-STORE-001 (structure de base)
- US-STORE-010 (listing pour vérifications)
- Service Project opérationnel
- Tables locks et audit_logs créées

## Tâches techniques
- [ ] Implémenter POST /storage/copy
- [ ] Intégration avec service Project pour check membership
- [ ] Logique de copie MinIO (copy_object)
- [ ] Système de verrouillage en base
- [ ] Tests avec cas d'erreur (déjà locked, pas d'accès, etc.)
- [ ] Gestion des timeouts service Project