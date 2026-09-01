#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "[render-build] cwd=$ROOT"
if [[ "${SKIP_PIP:-0}" != "1" ]]; then
  pip install -r requirements.txt
fi
cd web
# Force devDependencies (typescript, vite, @types/react, ...). Render sets
# NODE_ENV=production, under which a plain `npm install` omits devDependencies,
# so `tsc`/`vite` are missing and `npm run build` fails with TS7016/TS7026.
echo "[render-build] installing web deps (incl. dev)"
npm ci --include=dev --no-audit --no-fund || npm install --include=dev --no-audit --no-fund
echo "[render-build] npm run build"
npm run build
test -f dist/index.html
echo "[render-build] done"
