# GitHub Actions Workflows

Ce projet utilise trois workflows GitHub Actions pour CI/CD :

## 1. `python-app.yml` - Tests Unitaires et Lint

**Déclenchement :**
- Push sur branches `main` ou `guardian_staging`
- Pull requests vers `main`

**Actions :**
1. ✅ Lint avec Pylint (score requis: 10.00/10)
2. ✅ Tests unitaires (`tests/unit/`) - 111 tests
3. ✅ Matrice Python : 3.10, 3.11, 3.12, 3.13

**Durée estimée :** ~2-3 minutes par version Python

**Variables d'environnement :**
- `DATABASE_URL`: SQLite en mémoire
- `MINIO_SERVICE_URL`: http://localhost:9000
- `PROJECT_SERVICE_URL`: http://localhost:5001
- Toutes les variables nécessaires sont créées automatiquement

**Note :** Les tests unitaires ne nécessitent pas de services externes (MinIO, PostgreSQL).

---

## 2. `integration-tests.yml` - Tests d'Intégration (Optionnel)

**Déclenchement :**
- Push sur `main`
- Pull requests vers `main`
- Manuellement via "Actions" > "Integration Tests" > "Run workflow"

**Actions :**
1. 🐳 Démarre MinIO dans un conteneur Docker
2. ✅ Tests d'intégration (`tests/integration/`) - 21 tests + 1 skip
3. 🧹 Nettoyage automatique des conteneurs

**Durée estimée :** ~1-2 minutes

**Note :** Ce workflow est **optionnel** et peut être désactivé si non nécessaire.

---

## 3. `docker-image.yml` - Build et Publication Docker

**Déclenchement :**
- Push sur `main` ou `fix_issues` avec modifications de Dockerfile ou fichiers Python
- Pull requests vers `main`

**Actions :**
1. 🧪 **Test Job** : Build image de test + exécution tests unitaires dans conteneur
2. 🏗️ **Build Job (PR)** : Build image production sans push (validation)
3. 🚀 **Build-and-Push Job (Push)** : Build + publication vers `ghcr.io`

**Tags créés (push sur main) :**
- `ghcr.io/org/repo:latest`
- `ghcr.io/org/repo:sha-<short_sha>`
- `ghcr.io/org/repo:<version>` (si fichier VERSION existe)

**Durée estimée :** ~5-10 minutes

**Images cibles :**
- `test` : Exécute uniquement les tests unitaires (`pytest tests/unit/`)
- `production` : Image minimale pour déploiement (gunicorn + appuser non-root)

**Note :** Les tests dans Docker n'ont **pas besoin de services externes** car seuls les tests unitaires sont exécutés.

---

## Exécution Locale

### Tests unitaires uniquement (rapide)
```bash
pytest tests/unit/ -v
```

### Tests d'intégration (nécessite MinIO)
```bash
# Démarrer MinIO
docker-compose up -d minio

# Lancer les tests
pytest tests/integration/ -v

# Arrêter MinIO
docker-compose down
```

### Tous les tests
```bash
./scripts/run_integration_tests.sh
```

---

## Badges de Status

Ajoutez ces badges dans votre README principal :

```markdown
![CI - Unit Tests](https://github.com/bengeek06/storage-api-waterfall/actions/workflows/python-app.yml/badge.svg)
![CI - Integration Tests](https://github.com/bengeek06/storage-api-waterfall/actions/workflows/integration-tests.yml/badge.svg)
![Docker Build](https://github.com/bengeek06/storage-api-waterfall/actions/workflows/docker-image.yml/badge.svg)
![Pylint Score](https://img.shields.io/badge/pylint-10.00%2F10-brightgreen)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
```

---

## Troubleshooting

### Les tests unitaires échouent en CI
- Vérifier que toutes les dépendances sont dans `requirements-dev.txt`
- Vérifier que le score Pylint est 10.00/10
- Vérifier que `.env.testing` contient toutes les variables

### Les tests d'intégration échouent
- Vérifier que MinIO démarre correctement (check health endpoint)
- Augmenter le timeout si nécessaire (ligne `timeout 30`)
- Vérifier les logs du conteneur MinIO

### Désactiver temporairement les tests d'intégration
Commentez les lignes dans `integration-tests.yml` :
```yaml
on:
  # push:
  #   branches: [ main ]
  # pull_request:
  #   branches: [ main ]
  workflow_dispatch:  # Garder uniquement le déclenchement manuel
```
