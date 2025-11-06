# Scripts de test pour CI/CD

## Tests Unitaires
```bash
# Script pour CI - Tests unitaires uniquement
#!/bin/bash
set -e

echo "🧪 Running unit tests in CI..."
pytest tests/unit/ \
    --verbose \
    --tb=short \
    --junit-xml=reports/unit-tests.xml \
    --cov=app \
    --cov-report=xml:reports/coverage.xml \
    --cov-report=html:reports/htmlcov \
    --cov-fail-under=80

echo "✅ Unit tests completed successfully"
```

## Tests d'Intégration
```bash
# Script pour CI - Tests d'intégration avec Docker
#!/bin/bash
set -e

echo "🐳 Setting up integration test environment..."
docker-compose -f docker-compose.test.yml up -d --build

echo "⏳ Waiting for services..."
sleep 60

echo "🔗 Running integration tests..."
pytest tests/integration/ \
    --verbose \
    --tb=long \
    --junit-xml=reports/integration-tests.xml

echo "🧹 Cleaning up..."
docker-compose -f docker-compose.test.yml down -v

echo "✅ Integration tests completed successfully"
```

## Configuration GitHub Actions
```yaml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        pip install -r requirements-dev.txt
    - name: Run unit tests
      run: make test-unit-coverage
    - name: Upload coverage
      uses: codecov/codecov-action@v3
  
  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
    - uses: actions/checkout@v3
    - name: Run integration tests
      run: make test-integration-full
```