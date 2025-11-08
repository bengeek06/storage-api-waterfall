#!/bin/bash

# Script pour démarrer rapidement l'environnement de développement
# Utile pour les développeurs qui veulent juste tester l'API

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}🚀 Démarrage de l'environnement de développement${NC}"

cd "$PROJECT_DIR"

# Démarrer docker-compose en arrière-plan
echo -e "${BLUE}🐳 Démarrage des services Docker...${NC}"
docker-compose up -d

# Démarrer le service storage
echo -e "${BLUE}🚀 Démarrage du service storage...${NC}"
echo "Service disponible sur: http://localhost:5000"
echo "Documentation API: http://localhost:5000/docs (si configuré)"
echo ""
echo "Utilisez Ctrl+C pour arrêter le service"

FLASK_ENV=development python run.py