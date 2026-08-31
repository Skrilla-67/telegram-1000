#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
pip install -r requirements.txt
cd web
npm install
npm run build
test -f dist/index.html