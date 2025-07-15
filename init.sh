#!/bin/bash
echo "📦 Build et lancement de l'application mail"

# Vérifie que .env existe
if [ ! -f .env ]; then
  echo "❌ Fichier .env introuvable !"
  exit 1
fi

# Build + up
docker compose up --build
