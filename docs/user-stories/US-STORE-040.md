# US-STORE-040 — Commit et créer nouvelle version

## Description

**En tant que** utilisateur ayant édité un fichier copié  
**Je veux** pouvoir soumettre mon fichier modifié vers l'emplacement d'origine  
**Afin de** créer une nouvelle version du fichier projet avec statut pending validation et libérer le verrou.

## Critères d'acceptation

### 1. Endpoint de commit
- [ ] Endpoint `POST /storage/commit` disponible
- [ ] Paramètres requis :
  - `draft_file_id` : ID du fichier draft/copie à committer
  - `changelog` : description des modifications (optionnel)
  - `tags` : tags pour cette version (optionnel)

### 2. Vérifications préalables
- [ ] Vérification que le fichier draft existe et appartient à l'utilisateur
- [ ] Vérification que le fichier source est bien locked par cet utilisateur
- [ ] Vérification que le fichier draft a été modifié (différence de checksum/size)

### 3. Création de nouvelle version
- [ ] Copie du fichier draft vers l'emplacement original avec nouvelle clé objet
- [ ] Création d'une nouvelle entrée `file_versions` :
  - `version_id` : UUID
  - `file_id` : ID du fichier source original
  - `object_key` : nouvelle clé MinIO
  - `version_number` : incrémenté automatiquement
  - `created_by` : user_id de l'utilisateur
  - `changelog` : description fournie
  - `size`, `mime_type` : du fichier modifié

### 4. Mise à jour du statut
- [ ] Mise à jour du statut du fichier principal : → `pending_validation`
- [ ] Mise à jour de `current_version_id` vers la nouvelle version
- [ ] Mise à jour de `updated_at` et `modified_by`

### 5. Libération du verrou
- [ ] Suppression de l'entrée dans la table `locks`
- [ ] Le fichier redevient disponible pour d'autres utilisateurs

### 6. Gestion du fichier draft
- [ ] Option de conservation ou suppression du fichier draft
- [ ] Par défaut : suppression du draft après commit réussi
- [ ] Option `keep_draft=true` pour conserver une copie

### 7. Structure de réponse
```json
{
  "status": "success",
  "data": {
    "file_id": "uuid",
    "version_id": "uuid",
    "version_number": 3,
    "status": "pending_validation",
    "created_at": "2025-01-01T10:00:00Z",
    "lock_released": true,
    "draft_file_id": "uuid",
    "draft_kept": false
  }
}
```

### 8. Validation workflow trigger
- [ ] Création d'une entrée `validations` avec statut `pending` :
  - `validation_id` : UUID
  - `version_id` : référence vers la nouvelle version
  - `state` : "pending"
  - `requested_by` : user_id
  - `requested_at` : timestamp

### 9. Notifications (optionnel)
- [ ] Possibilité d'envoyer une notification aux reviewers du projet
- [ ] Event émis pour système de notifications externe

### 10. Audit trail
- [ ] Enregistrement dans `audit_logs` :
  - Action : "version_committed"
  - Entity : file_id
  - Actor : user_id
  - Metadata : version_id, version_number, changelog

### 11. Gestion d'erreurs
- [ ] Si le lock n'existe plus : erreur 409 "Lock expired or removed"
- [ ] Si le fichier source a été modifié : erreur 409 "Source file modified during edit"
- [ ] Si l'upload vers MinIO échoue : rollback complet

## Priorité
**HIGH** - Workflow core

## Estimation
**8 points** (logique complexe avec rollback)

## Dépendances
- US-STORE-030 (copie et lock)
- Tables file_versions, validations créées
- Système de versioning implémenté

## Tâches techniques
- [ ] Implémenter POST /storage/commit
- [ ] Logique de versioning automatique
- [ ] Système de rollback en cas d'erreur
- [ ] Gestion des conflits de versions concurrentes
- [ ] Tests d'intégration avec workflow complet copy→edit→commit
- [ ] Optimisation des opérations MinIO (copy vs re-upload)