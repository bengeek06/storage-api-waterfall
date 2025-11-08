# US-STORE-060 — Liste et délock forcé

## Description

**En tant qu'** administrateur ou manager de projet  
**Je veux** pouvoir lister tous les fichiers verrouillés et forcer le déverrouillage si nécessaire  
**Afin de** débloquer des situations où un utilisateur a quitté le projet ou a été supprimé.

## Critères d'acceptation

### 1. Endpoint de liste des locks
- [ ] Endpoint `GET /storage/locks` disponible
- [ ] Paramètres de filtrage :
  - `project_id` : locks d'un projet spécifique
  - `user_id` : locks d'un utilisateur spécifique  
  - `bucket_type` : type de bucket (projects/companies/users)
  - `expired_only` : seulement les locks expirés (optionnel)
  - `page`, `limit` : pagination

### 2. Informations des locks
```json
{
  "status": "success",
  "data": {
    "locks": [
      {
        "lock_id": "uuid",
        "file_id": "uuid", 
        "file_path": "/projects/123/docs/document.pdf",
        "locked_by": "user-uuid",
        "locked_by_name": "John Doe",
        "locked_at": "2025-01-01T10:00:00Z",
        "reason": "Editing for review",
        "duration_hours": 48,
        "forced": false,
        "project_id": "123",
        "bucket_type": "projects"
      }
    ],
    "pagination": {...}
  }
}
```

### 3. Détection des locks orphelins
- [ ] Identification des locks où l'utilisateur :
  - A été supprimé du système
  - A été retiré du projet
  - N'est plus actif depuis > X jours
- [ ] Flag `orphaned: true` dans la réponse

### 4. Endpoint de force unlock
- [ ] Endpoint `DELETE /storage/locks/{lock_id}/force` disponible
- [ ] Paramètres requis :
  - `reason` : raison du déverrouillage forcé
  - `notify_user` : booléen pour notifier l'utilisateur original

### 5. Vérification des droits pour force unlock
- [ ] Rôles autorisés :
  - Admin système
  - Manager du projet concerné
  - Propriétaire de l'entreprise (pour locks company)
- [ ] Vérification via service Project/Auth
- [ ] Retour 403 si droits insuffisants

### 6. Processus de force unlock
- [ ] Suppression de l'entrée dans la table `locks`
- [ ] Mise à jour du flag `forced: true` dans audit_logs
- [ ] Conservation de l'historique du lock original

### 7. Gestion du fichier draft
- [ ] Si un fichier draft existe pour ce lock :
  - Option de le conserver avec nouveau propriétaire
  - Option de le supprimer
  - Option de le committer automatiquement (si spécifié)

### 8. Structure de réponse force unlock
```json
{
  "status": "success", 
  "data": {
    "lock_id": "uuid",
    "file_id": "uuid",
    "previously_locked_by": "user-uuid",
    "unlocked_by": "admin-uuid",
    "unlocked_at": "2025-01-01T10:00:00Z",
    "reason": "User removed from project",
    "draft_action": "kept",
    "notification_sent": true
  }
}
```

### 9. Notifications
- [ ] Si `notify_user=true` : notification à l'utilisateur original
- [ ] Notification aux managers du projet
- [ ] Contenu : fichier déverrouillé, raison, action sur le draft

### 10. Audit trail complet
- [ ] Enregistrement dans `audit_logs` :
  - Action : "lock_force_removed"
  - Entity : file_id
  - Actor : admin/manager user_id
  - Metadata : original_lock_id, original_user, reason, draft_action

### 11. Dashboard administrateur
- [ ] Endpoint `GET /storage/admin/locks-summary`
- [ ] Statistiques :
  - Nombre total de locks actifs
  - Locks par projet/utilisateur
  - Locks orphelins détectés
  - Locks expirés (> X jours)

### 12. Auto-cleanup optionnel
- [ ] Job automatique de nettoyage des locks orphelins
- [ ] Configurable par politique d'entreprise
- [ ] Notification avant suppression automatique

## Priorité
**MEDIUM** - Gestion administrative

## Estimation
**5 points**

## Dépendances
- US-STORE-030 (système de locks)
- Service Project pour vérification des droits admin
- Service User pour vérification de l'existence des utilisateurs

## Tâches techniques
- [ ] Implémenter GET /storage/locks avec filtres
- [ ] Implémenter DELETE /storage/locks/{id}/force
- [ ] Implémenter GET /storage/admin/locks-summary
- [ ] Logique de détection des locks orphelins
- [ ] Intégration avec services Project/User pour droits
- [ ] Tests avec cas d'utilisateurs supprimés/retirés
- [ ] Job optionnel de cleanup automatique