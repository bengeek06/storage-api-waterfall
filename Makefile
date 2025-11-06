# Makefile pour faciliter l'exécution des tests

# Variables
PYTEST = pytest
DOCKER_COMPOSE = docker-compose -f docker-compose.test.yml

# Tests unitaires (rapides, avec mocks)
.PHONY: test-unit
test-unit:
	@echo "🧪 Running unit tests..."
	$(PYTEST) tests/unit/ -v

.PHONY: test-unit-fast
test-unit-fast:
	@echo "⚡ Running unit tests (fast mode)..."
	$(PYTEST) tests/unit/ -v -x --tb=line

.PHONY: test-unit-coverage
test-unit-coverage:
	@echo "📊 Running unit tests with coverage..."
	$(PYTEST) tests/unit/ --cov=app --cov-report=html --cov-report=term-missing

# Tests d'intégration (avec services Docker)
.PHONY: test-integration-setup
test-integration-setup:
	@echo "🐳 Starting Docker services for integration tests..."
	$(DOCKER_COMPOSE) up -d --build
	@echo "⏳ Waiting for services to be ready..."
	sleep 30

.PHONY: test-integration
test-integration: test-integration-setup
	@echo "🔗 Running integration tests..."
	$(PYTEST) tests/integration/ -v

.PHONY: test-integration-teardown
test-integration-teardown:
	@echo "🧹 Cleaning up Docker services..."
	$(DOCKER_COMPOSE) down -v

.PHONY: test-integration-full
test-integration-full: test-integration-setup test-integration test-integration-teardown

# Tests de performance
.PHONY: test-performance
test-performance: test-integration-setup
	@echo "⚡ Running performance tests..."
	$(PYTEST) tests/integration/ -m "performance or slow" -v

# Tests complets
.PHONY: test-all
test-all: test-unit test-integration-full

.PHONY: test
test: test-unit

# Développement
.PHONY: test-watch
test-watch:
	@echo "👀 Watching for changes and running unit tests..."
	$(PYTEST) tests/unit/ --looponfail

# Tests spécifiques par composant
.PHONY: test-models
test-models:
	@echo "📋 Testing models only..."
	$(PYTEST) tests/unit/test_storage_models.py -v

.PHONY: test-schemas
test-schemas:
	@echo "🔍 Testing schemas only..."
	$(PYTEST) tests/unit/test_storage_schemas.py -v

.PHONY: test-resources
test-resources:
	@echo "🛠️  Testing resources only..."
	$(PYTEST) tests/unit/test_storage_resources.py -v

.PHONY: test-services
test-services:
	@echo "⚙️  Testing services only..."
	$(PYTEST) tests/unit/test_storage_service.py -v

.PHONY: test-api
test-api:
	@echo "🌐 Testing API endpoints..."
	$(PYTEST) tests/unit/test_api.py -v

.PHONY: test-health
test-health:
	@echo "💓 Testing health checks..."
	$(PYTEST) tests/unit/test_health.py -v

.PHONY: test-config
test-config:
	@echo "⚙️  Testing configuration..."
	$(PYTEST) tests/unit/test_config.py -v

.PHONY: test-storage
test-storage:
	@echo "💾 Testing storage components only..."
	$(PYTEST) tests/unit/test_storage_*.py -v

.PHONY: test-existing
test-existing:
	@echo "📦 Testing existing components..."
	$(PYTEST) tests/unit/test_api.py tests/unit/test_config.py tests/unit/test_health.py tests/unit/test_init.py tests/unit/test_run.py tests/unit/test_utils.py tests/unit/test_version.py tests/unit/test_wsgi.py -v

# Utilitaires
.PHONY: clean-test
clean-test:
	@echo "🧹 Cleaning test artifacts..."
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

.PHONY: lint-tests
lint-tests:
	@echo "🔍 Linting test files..."
	flake8 tests/

.PHONY: help
help:
	@echo "📚 Available test commands:"
	@echo ""
	@echo "Unit Tests (Fast, Mocked):"
	@echo "  make test-unit          - Run all unit tests"
	@echo "  make test-unit-fast     - Run unit tests (fail fast)"
	@echo "  make test-unit-coverage - Run unit tests with coverage"
	@echo "  make test-models        - Test models only"
	@echo "  make test-schemas       - Test schemas only"
	@echo "  make test-resources     - Test resources only"
	@echo "  make test-storage       - Test storage components only"
	@echo "  make test-api           - Test API endpoints"
	@echo "  make test-health        - Test health checks"
	@echo "  make test-config        - Test configuration"
	@echo "  make test-existing      - Test existing components"
	@echo ""
	@echo "Integration Tests (Real Services):"
	@echo "  make test-integration-setup     - Start Docker services"
	@echo "  make test-integration           - Run integration tests"
	@echo "  make test-integration-teardown  - Stop Docker services"
	@echo "  make test-integration-full      - Full integration test cycle"
	@echo "  make test-performance           - Run performance tests"
	@echo ""
	@echo "Combined:"
	@echo "  make test               - Run unit tests (default)"
	@echo "  make test-all           - Run all tests"
	@echo ""
	@echo "Development:"
	@echo "  make test-watch         - Watch and run unit tests"
	@echo "  make clean-test         - Clean test artifacts"
	@echo "  make lint-tests         - Lint test files"