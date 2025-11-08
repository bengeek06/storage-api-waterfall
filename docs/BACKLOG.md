# Backlog des User Stories - Service Storage

## User Story principale (Epic)

- **[US-STORE-001](./user-stories/US-STORE-001.md)** — Gestion documentaire collaborative (v1) `HIGH` `13 points`

## User Stories de fonctionnalités (par ordre de priorité)

### Sprint 1 - Fonctionnalités de base
- **[US-STORE-010](./user-stories/US-STORE-010.md)** — Lister et naviguer `HIGH` `3 points`
- **[US-STORE-020](./user-stories/US-STORE-020.md)** — Obtenir presigned URL pour upload `HIGH` `5 points`

### Sprint 2 - Workflow collaboratif
- **[US-STORE-030](./user-stories/US-STORE-030.md)** — Copier fichier projet → user (déclenche lock) `HIGH` `8 points`
- **[US-STORE-040](./user-stories/US-STORE-040.md)** — Commit et créer nouvelle version `HIGH` `8 points`

### Sprint 3 - Validation et administration
- **[US-STORE-050](./user-stories/US-STORE-050.md)** — Workflow de validation `HIGH` `5 points`
- **[US-STORE-060](./user-stories/US-STORE-060.md)** — Liste et délock forcé `MEDIUM` `5 points`

### Sprint 4 - Fonctionnalités avancées
- **[US-STORE-070](./user-stories/US-STORE-070.md)** — Versions et historique `MEDIUM` `5 points`

## Ressources de référence

- **[Modèle de données](./database-model.md)** — Schéma Postgres recommandé
- **[OpenAPI](../openapi.yml)** — Spécification des endpoints

## Estimation totale

- **Total points** : 52 points
- **Sprints estimés** : 4 sprints
- **Durée approximative** : 8-10 semaines (selon vélocité équipe)

## Prérequis techniques

### Infrastructure
- [ ] MinIO opérationnel avec buckets configurés
- [ ] Base de données Postgres
- [ ] Service d'authentification JWT
- [ ] Service Project pour vérification des droits

### Dépendances externes
- [ ] Service Project - vérification membership utilisateurs
- [ ] Service Auth - validation JWT et RBAC
- [ ] Service User - informations utilisateurs (noms, etc.)
- [ ] Service Notifications (optionnel)

## Notes de planification

### Sprint 1 (US-STORE-010, US-STORE-020)
- **Objectif** : Fonctionnalités de base (list, upload)
- **Livrable** : API basique fonctionnelle
- **Risques** : Configuration MinIO, structure de données

### Sprint 2 (US-STORE-030, US-STORE-040)
- **Objectif** : Workflow copy/edit/commit
- **Livrable** : Système de locks et versioning
- **Risques** : Complexité du système de locks, intégration service Project

### Sprint 3 (US-STORE-050, US-STORE-060)
- **Objectif** : Validation et administration
- **Livrable** : Workflow complet de validation
- **Risques** : Gestion des droits complexes, cas d'erreur nombreux

### Sprint 4 (US-STORE-070)
- **Objectif** : Fonctionnalités avancées
- **Livrable** : Historique et comparaison de versions
- **Risques** : Performance avec historiques volumineux

## Critères de "Done"

Pour chaque user story :
- [ ] Code développé et review
- [ ] Tests unitaires > 80% coverage
- [ ] Tests d'intégration passants
- [ ] Documentation OpenAPI mise à jour
- [ ] Tests de charge basic (si applicable)
- [ ] Déployé en environnement de staging
- [ ] Validation métier par PO