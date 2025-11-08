#!/bin/bash

# Script pour lancer les tests d'intégration
# Orchestre Docker Compose, le service storage et les tests

set -e  # Arrêter le script en cas d'erreur

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Répertoire du script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}🚀 Lancement des tests d'intégration${NC}"
echo "Répertoire du projet: $PROJECT_DIR"

# Fonction pour nettoyer à la sortie
cleanup() {
    echo -e "\n${YELLOW}🧹 Nettoyage...${NC}"
    
    # Arrêter les services Docker
    echo "Arrêt des services Docker de test..."
    cd "$PROJECT_DIR"
    docker compose -f docker-compose.test.yml down -v 2>/dev/null || true
    
    echo -e "${GREEN}✅ Nettoyage terminé${NC}"
}

# Configurer le nettoyage automatique
trap cleanup EXIT INT TERM

cd "$PROJECT_DIR"

# 1. Vérifier que docker compose est disponible
echo -e "${BLUE}🐳 Vérification de Docker Compose...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker n'est pas installé${NC}"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose n'est pas disponible${NC}"
    exit 1
fi

# 2. Démarrer les services Docker d'intégration
echo -e "${BLUE}🐳 Démarrage des services Docker d'intégration...${NC}"
cd "$PROJECT_DIR"
docker compose -f docker-compose.test.yml up -d --build

# Attendre que les services soient prêts
echo -e "${YELLOW}⏳ Attente que les services soient prêts...${NC}"
timeout=120
counter=0

# Attendre que le service storage soit prêt
while ! curl -s http://localhost:5000/health > /dev/null 2>&1; do
    if [ $counter -ge $timeout ]; then
        echo -e "${RED}❌ Le service storage n'est pas prêt après ${timeout}s${NC}"
        echo "Logs du service storage:"
        docker compose -f docker-compose.test.yml logs storage-service
        exit 1
    fi
    sleep 3
    counter=$((counter + 3))
    echo -n "."
done
echo -e "\n${GREEN}✅ Service storage prêt sur http://localhost:5000${NC}"

# 3. Configurer l'environnement Python (si nécessaire)
echo -e "${BLUE}🐍 Configuration de l'environnement Python...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
fi
if [ -f "requirements-dev.txt" ]; then
    pip install -q -r requirements-dev.txt
fi

# 4. Lancer les tests d'intégration
echo -e "${BLUE}🧪 Lancement des tests d'intégration...${NC}"
export FLASK_ENV=testing
pytest tests/integration/ -v --tb=short --color=yes

# 5. Afficher le résumé
echo -e "\n${GREEN}🎉 Tests d'intégration terminés !${NC}"
echo -e "${BLUE}📊 Services utilisés:${NC}"
echo "  - MinIO: http://localhost:9000"
echo "  - PostgreSQL: localhost:5432"
echo "  - Storage API: http://localhost:5000"
echo "  - Redis: localhost:6379"