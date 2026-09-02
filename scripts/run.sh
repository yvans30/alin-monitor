#!/usr/bin/env bash
# Lance alin-monitor en déchiffrant .env.enc à la volée, sans jamais écrire
# les secrets en clair sur disque. Utilise ce script au lieu de `python -m app.main`
# directement, aussi bien en local que sur le VPS.
set -euo pipefail

cd "$(dirname "$0")/.."

: "${SOPS_AGE_KEY_FILE:?Définis SOPS_AGE_KEY_FILE (ex: export SOPS_AGE_KEY_FILE=~/.config/alin-monitor/age-key.txt)}"

if [ ! -f .env.enc ]; then
  echo "Erreur : .env.enc introuvable. Lance d'abord scripts/encrypt-env.sh." >&2
  exit 1
fi

# `sops exec-env` ne détecte pas dotenv sur l'extension .enc : on décrypte
# via process substitution (jamais écrit sur disque) et on source le résultat.
set -a
# shellcheck disable=SC1091
source <(sops --input-type dotenv --output-type dotenv -d .env.enc)
set +a

exec python -m app.main
