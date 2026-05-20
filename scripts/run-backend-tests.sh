#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

if [ ! -x ".venv/bin/python" ]; then
  echo "Missing backend virtualenv. Run scripts/setup-dev.sh first." >&2
  exit 1
fi

.venv/bin/python manage.py test
