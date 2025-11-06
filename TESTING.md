# Testing Strategy Documentation

## Overview

Ce projet utilise une approche hybride pour les tests, combinant tests unitaires avec mocks et tests d'intégration avec des services réels.

## Structure des Tests

### Tests Unitaires (avec Mocks)
- **Localisation**: `tests/unit/`
- **Objectif**: Tester la logique métier en isolation
- **Technologies**: pytest + unittest.mock
- **Rapidité**: Très rapides (< 1s par test)
- **Isolation**: Complète, aucune dépendance externe

#### Fichiers de Tests Unitaires:
1. **`tests/unit/test_storage_models.py`**: Tests des modèles de données
   - Validation des relations entre StorageFile et FileVersion
   - Tests de la logique de soft delete
   - Validation des contraintes métier

2. **`tests/unit/test_storage_schemas.py`**: Tests des schémas de validation
   - Validation des paramètres d'entrée
   - Tests des règles de validation (chemins, tags, etc.)
   - Tests des messages d'erreur

3. **`tests/unit/test_storage_resources.py`**: Tests des endpoints API
   - Tests des réponses HTTP
   - Validation de l'authentification mockée
   - Tests des différents scénarios (succès, erreurs)

#### Fichiers de Tests Unitaires:
1. **`tests/unit/test_storage_models.py`**: Tests des modèles de données
   - Validation des relations entre StorageFile et FileVersion
   - Tests de la logique de soft delete
   - Validation des contraintes métier

2. **`tests/unit/test_storage_schemas.py`**: Tests des schémas de validation
   - Validation des paramètres d'entrée
   - Tests des règles de validation (chemins, tags, etc.)
   - Tests des messages d'erreur

3. **`tests/unit/test_storage_resources.py`**: Tests des endpoints API
   - Tests des réponses HTTP
   - Validation de l'authentification mockée
   - Tests des différents scénarios (succès, erreurs)

4. **`tests/unit/test_storage_service.py`**: Tests du service de stockage
   - Tests des interactions avec MinIO (mockées)
   - Validation de la génération d'URLs
   - Tests de gestion d'erreurs

5. **`tests/unit/test_api.py`**: Tests des endpoints dummies existants
   - Tests des opérations CRUD sur les dummies
   - Validation des réponses et erreurs

6. **`tests/unit/test_config.py`**: Tests de configuration
   - Validation des endpoints de configuration
   - Tests des variables d'environnement

7. **`tests/unit/test_health.py`**: Tests des health checks
   - Validation du monitoring des services
   - Tests des indicateurs de santé

8. **`tests/unit/test_*.py`**: Autres tests existants
   - Tests de l'initialisation (`test_init.py`)
   - Tests des utilitaires (`test_utils.py`)
   - Tests du serveur WSGI (`test_wsgi.py`)
   - Tests de versioning (`test_version.py`)
   - Tests du point d'entrée (`test_run.py`)

9. **`tests/unit/conftest.py`**: Configuration spécifique aux tests unitaires
   - Fixtures avec SQLite en mémoire
   - Mocks pour tous les services externes
   - Helpers pour tests isolés

### Tests d'Intégration (avec Docker)
- **Localisation**: `tests/integration/`
- **Objectif**: Tester l'interaction avec les services réels
- **Technologies**: pytest + docker-compose + MinIO réel
- **Configuration**: `docker-compose.test.yml`

#### Fichiers de Tests d'Intégration:
1. **`tests/integration/test_integration_storage.py`**: Tests avec MinIO réel
   - Tests de bout en bout avec upload/download réels
   - Validation des opérations sur fichiers
   - Tests de performance

2. **`tests/integration/conftest.py`**: Configuration spécifique aux tests d'intégration
   - Fixtures avec services Docker réels
   - Gestion de l'attente des services
   - Helpers pour nettoyage automatique

## Configuration des Tests

### Environment de Test
```bash
# Variables d'environnement pour les tests
FLASK_ENV=testing
DATABASE_URL=sqlite:///:memory:  # Tests unitaires
DATABASE_URL=postgresql://...    # Tests d'intégration
MINIO_SERVICE_URL=http://localhost:9000
```

### Fixtures Principales (conftest.py)
- **app**: Application Flask configurée pour les tests
- **client**: Client de test HTTP
- **mock_storage_service**: Service de stockage mocké
- **mock_jwt_auth**: Authentification mockée
- **auth_headers**: Headers d'authentification

## Exécution des Tests

### Tests Unitaires (Recommandé pour développement)
```bash
# Tous les tests unitaires
pytest tests/unit/ -v

# Test spécifique
pytest tests/unit/test_storage_models.py::TestStorageFile::test_create_file -v

# Avec couverture
pytest --cov=app tests/unit/ --cov-report=html

# Tests rapides pendant le développement
pytest tests/unit/test_storage_models.py tests/unit/test_storage_schemas.py -v
```

### Tests d'Intégration (Pour validation complète)
```bash
# Démarrer l'environnement de test
docker-compose -f docker-compose.test.yml up --build -d

# Attendre que les services soient prêts
sleep 30

# Exécuter les tests d'intégration
pytest tests/integration/ -v

# Tests de performance (marqués comme slow)
pytest tests/integration/ -m "slow" -v

# Nettoyer
docker-compose -f docker-compose.test.yml down -v
```

### Tous les Tests
```bash
# Suite complète (unitaires puis intégration)
pytest tests/unit/ -v && pytest tests/integration/ -v

# Parallélisation des tests unitaires
pytest tests/unit/ -n auto -v
```

## Avantages de cette Approche

### Tests Unitaires (Mocks)
✅ **Rapidité**: Exécution en quelques secondes  
✅ **Isolation**: Aucune dépendance externe  
✅ **Fiabilité**: Pas d'effets de bord  
✅ **Parallélisation**: Peut s'exécuter en parallèle  
✅ **CI/CD**: Idéal pour l'intégration continue  

### Tests d'Intégration (Docker)
✅ **Réalisme**: Tests avec services réels  
✅ **Validation complète**: Tests de bout en bout  
✅ **Détection de problèmes**: Issues de configuration/réseau  
✅ **Performance**: Tests de charge et performance  

## Stratégie de Testing par Phase

### Phase de Développement
1. **TDD avec mocks**: Écrire tests unitaires d'abord
2. **Développement rapide**: Cycle court test/code/refactor
3. **Validation locale**: Tests unitaires en continu

### Phase de Validation
1. **Tests d'intégration**: Validation avec services réels
2. **Tests de performance**: Charge et latence
3. **Tests de régression**: Suite complète

### Phase de Production
1. **CI Pipeline**: Tests unitaires à chaque commit
2. **Tests d'intégration**: Sur les branches principales
3. **Tests de smoke**: Validation en production

## Mocking Strategy

### Ce qu'on mocke:
- **Base de données**: SQLAlchemy sessions
- **MinIO client**: Toutes les opérations S3
- **Authentification**: JWT et vérifications d'accès
- **Appels réseau**: Requêtes externes

### Ce qu'on ne mocke PAS dans les tests d'intégration:
- **MinIO réel**: Container Docker avec vraies opérations
- **Base de données**: PostgreSQL réel pour tests d'intégration
- **Réseau**: Vraies requêtes HTTP entre services

## Exemple d'Utilisation

### Test Unitaire Typique
```python
@patch('app.resources.storage.StorageFile.get_by_path')
@patch('app.resources.storage.storage_backend.generate_download_url')
def test_download_url_success(mock_generate, mock_get, client):
    # Setup mocks
    mock_file = MagicMock()
    mock_file.storage_key = "test_key"
    mock_get.return_value = mock_file
    mock_generate.return_value = ("https://url", 3600)
    
    # Test
    response = client.get('/storage/download-url?project_id=1&path=/test.txt')
    
    # Assertions
    assert response.status_code == 200
    data = response.get_json()
    assert data['url'] == "https://url"
```

### Test d'Intégration Typique
```python
def test_real_upload_download_flow(storage_api_base_url, auth_headers):
    # Get real upload URL
    response = requests.post(f"{storage_api_base_url}/storage/upload-url", ...)
    upload_url = response.json()['url']
    
    # Upload to real MinIO
    requests.put(upload_url, data="test content")
    
    # Get real download URL and verify
    response = requests.get(f"{storage_api_base_url}/storage/download-url", ...)
    download_url = response.json()['url']
    
    content = requests.get(download_url).text
    assert content == "test content"
```

## Maintenance

### Mise à jour des Mocks
- Vérifier que les mocks correspondent aux vraies interfaces
- Mettre à jour lors des changements d'API MinIO
- Valider avec les tests d'intégration

### Performance des Tests
- **Tests unitaires**: < 1s par test
- **Suite complète unitaire**: < 30s
- **Tests d'intégration**: < 5min
- **Optimisation**: Parallélisation et fixtures réutilisables

Cette approche garantit un développement rapide avec des tests unitaires fiables, tout en maintenant la confiance avec des tests d'intégration réalistes.