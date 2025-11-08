# US-STORE-050 — Workflow de validation

## Description

**En tant que** validateur/reviewer d'un projet  
**Je veux** pouvoir approuver ou rejeter les nouvelles versions de fichiers soumises  
**Afin de** contrôler la qualité et valider les modifications avant qu'elles deviennent officielles.

## Critères d'acceptation

### 1. Endpoint d'approbation
- [ ] Endpoint `POST /storage/approve` disponible
- [ ] Paramètres requis :
  - `version_id` : ID de la version à approuver
  - `comment` : commentaire de validation (optionnel)

### 2. Endpoint de rejet
- [ ] Endpoint `POST /storage/reject` disponible  
- [ ] Paramètres requis :
  - `version_id` : ID de la version à rejeter
  - `comment` : raison du rejet (requis)
  - `require_new_version` : booléen, si une nouvelle soumission est requise

### 3. Vérification des droits
- [ ] Vérification que l'utilisateur a le droit de valider dans ce projet
- [ ] Vérification que l'utilisateur n'est pas celui qui a soumis la version
- [ ] Retour 403 si droits insuffisants

### 4. Vérification de l'état
- [ ] Vérification que la version est en statut `pending_validation`
- [ ] Retour 409 si déjà validée/rejetée

### 5. Processus d'approbation
- [ ] Mise à jour de l'entrée `validations` :
  - `state` : "pending" → "approved"
  - `reviewed_by` : user_id du reviewer
  - `reviewed_at` : timestamp
  - `comment` : commentaire fourni
- [ ] Mise à jour du statut du fichier : → `approved`
- [ ] Marquer cette version comme "validated" et active

### 6. Processus de rejet
- [ ] Mise à jour de l'entrée `validations` :
  - `state` : "pending" → "rejected"  
  - `reviewed_by` : user_id du reviewer
  - `reviewed_at` : timestamp
  - `comment` : raison du rejet
- [ ] Mise à jour du statut du fichier selon le cas :
  - Si `require_new_version=true` : → `requires_revision`
  - Sinon : → `approved` (version précédente reste active)

### 7. Gestion des versions actives
- [ ] Après approbation : cette version devient la "current_version"
- [ ] Après rejet : 
  - Si require_new_version=false : version précédente reste current
  - Si require_new_version=true : statut "requires_revision"

### 8. Structure de réponse
```json
{
  "status": "success",
  "data": {
    "version_id": "uuid",
    "validation_id": "uuid", 
    "state": "approved",
    "reviewed_by": "reviewer-uuid",
    "reviewed_at": "2025-01-01T10:00:00Z",
    "comment": "Changes look good, approved",
    "file_status": "approved",
    "is_current_version": true
  }
}
```

### 9. Notifications
- [ ] Notification automatique au créateur de la version
- [ ] Contenu : statut (approved/rejected), commentaire, reviewer
- [ ] Event émis pour système de notifications externe

### 10. Audit trail
- [ ] Enregistrement dans `audit_logs` pour chaque action :
  - Action : "version_approved" ou "version_rejected"
  - Entity : version_id
  - Actor : reviewer user_id
  - Metadata : comment, previous_state

### 11. Endpoint de liste des validations en attente
- [ ] Endpoint `GET /storage/pending-validations` 
- [ ] Filtres par projet, reviewer assigné, date
- [ ] Pagination et tri par date de soumission

### 12. Historique des validations
- [ ] Endpoint `GET /storage/validation-history?file_id=...`
- [ ] Liste toutes les validations passées pour un fichier
- [ ] Inclut commentaires, reviewers, dates

## Priorité
**HIGH** - Workflow critique

## Estimation  
**5 points**

## Dépendances
- US-STORE-040 (commit et versions)
- Service Project pour vérification des droits de reviewer
- Table validations implémentée
- Système de notifications (optionnel)

## Tâches techniques
- [ ] Implémenter POST /storage/approve
- [ ] Implémenter POST /storage/reject  
- [ ] Implémenter GET /storage/pending-validations
- [ ] Implémenter GET /storage/validation-history
- [ ] Intégration avec service Project pour droits reviewer
- [ ] Tests du workflow complet commit→approve/reject
- [ ] Système de notifications des décisions