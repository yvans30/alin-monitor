#!/usr/bin/env bash
# Chiffre .env (en clair, jamais commité) vers .env.enc (chiffré, committable).
# Prérequis : SOPS_AGE_KEY_FILE doit pointer vers ta clé privée age.
set -euo pipefail

cd "$(dirname "$0")/.."

: "${SOPS_AGE_KEY_FILE:?Définis SOPS_AGE_KEY_FILE (ex: export SOPS_AGE_KEY_FILE=~/.config/alin-monitor/age-key.txt)}"

if [ ! -f .env ]; then
  echo "Erreur : .env introuvable." >&2
  exit 1
fi

sops --input-type dotenv --output-type dotenv --output .env.enc -e .env
echo "OK : .env.enc régénéré depuis .env."
