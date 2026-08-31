#!/usr/bin/env bash
# Idempotent setup for Cursor Cloud Agent development environments.
# Prepares a Python virtualenv, installs backend + frontend dependencies,
# builds the Mini App, and creates a dev-mode .env if one is missing.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# The default image ships python3.12 + node, but not the venv module.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  echo "[install] installing python3-venv"
  sudo apt-get update -qq
  sudo apt-get install -y python3.12-venv
fi

if [[ ! -d .venv ]]; then
  echo "[install] creating .venv"
  python3 -m venv .venv
fi

echo "[install] installing Python dependencies"
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/pip install -r requirements.txt

echo "[install] installing web dependencies"
cd web
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
echo "[install] building Mini App"
npm run build
cd "$ROOT"

# Dev-mode env: DEV_MODE=true and an empty BOT_TOKEN so bot polling stays off.
if [[ ! -f .env ]]; then
  echo "[install] creating dev .env"
  cp .env.example .env
  sed -i 's/^BOT_TOKEN=.*/BOT_TOKEN=/' .env
  sed -i 's/^DEV_MODE=.*/DEV_MODE=true/' .env
fi

echo "[install] done"
