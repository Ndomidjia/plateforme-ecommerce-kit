#!/usr/bin/env bash
# Script de déploiement, exécuté sur le serveur (SSH) par mon pipeline CD
# (.github/workflows/cd.yml) après chaque push réussi sur main -- voir
# docs/deploiement.md. Peut aussi être lancé à la main pendant la mise en
# place initiale du serveur.
set -euo pipefail

APP_DIR="$HOME/plateforme-ecommerce-kit"
cd "$APP_DIR"

echo "--- git pull ---"
git pull --ff-only origin main

echo "--- build + redémarrage des conteneurs ---"
docker compose -f docker-compose.prod.yml up -d --build

echo "--- nettoyage des anciennes images (libère de l'espace disque) ---"
docker image prune -f

echo "--- état des conteneurs ---"
docker compose -f docker-compose.prod.yml ps

echo "Déploiement terminé."
