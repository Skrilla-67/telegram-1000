#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "[render-build] cwd=$ROOT"
if [[ "${SKIP_PIP:-0}" != "1" ]]; then
  pip install -r requirements.txt
fi
cd web
echo "[render-build] npm install"
npm install
echo "[render-build] npm run build"
npm run build
test -f dist/index.html
echo "[render-build] done"
