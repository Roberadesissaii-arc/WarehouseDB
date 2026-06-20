#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

set -a
# shellcheck disable=SC1091
source "$ROOT/instance/warehousedb.env"
set +a

exec "$ROOT/.venv/bin/waitress-serve" --host="$HOST" --port="$PORT" --threads=16 wsgi:app
