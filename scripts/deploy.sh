#!/usr/bin/env bash
# Exécuté sur le VPS via la clé SSH dédiée GitHub Actions (commande forcée,
# cf. authorized_keys). Ne rien ajouter ici qui nécessite une saisie humaine.
set -euo pipefail

cd "$(dirname "$0")/.."

git pull --ff-only origin master
export AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
docker compose up -d --build
docker image prune -f
