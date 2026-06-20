#!/usr/bin/env bash
#
# WarehouseDB — Ubuntu / Debian installer
#
#   ./install.sh              # deps + venv + DB + systemd (auto-start on boot)
#   ./install.sh --no-service # install only, start manually
#   ./install.sh --docker     # Docker instead of native venv
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib.sh
source "$ROOT/deploy/lib.sh"

PYTHON="${PYTHON:-python3}"
VENV="$ROOT/.venv"
ENV_FILE="$ROOT/instance/warehousedb.env"
INSTALL_SERVICE=true
USE_DOCKER=false

usage() {
  sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --service) INSTALL_SERVICE=true ;;
    --no-service) INSTALL_SERVICE=false ;;
    --docker) USE_DOCKER=true ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

trap stop_sudo_keepalive EXIT

if [ -t 1 ]; then
  GREEN=$'\033[1;32m'; BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
else
  GREEN=''; BOLD=''; DIM=''; RESET=''
fi

printf '\n%s' "$GREEN"
cat <<'ART'
__      ___   ___ ___ _  _  ___  _   _ ___ ___   ___  ___
\ \    / /_\ | _ \ __| || |/ _ \| | | / __| __| |   \| _ )
 \ \/\/ / _ \|   / _|| __ | (_) | |_| \__ \ _|  | |) | _ \
  \_/\_/_/ \_\_|_\___|_||_|\___/ \___/|___/___| |___/|___/
ART
printf '%s\n' "$RESET"
echo "  ${DIM}Inventory & fleet control hub — your warehouse, your control.${RESET}"
echo "  ${DIM}project: $ROOT${RESET}"
echo

ensure_sudo
apt_bootstrap
install_cloudflared

DEFAULT_PORT=8000
CHOSEN_PORT="$(find_free_port "$DEFAULT_PORT")"
if [ "$CHOSEN_PORT" != "$DEFAULT_PORT" ]; then
  echo "==> Using port $CHOSEN_PORT (default $DEFAULT_PORT was busy)"
else
  echo "==> Using port $CHOSEN_PORT"
fi

if $USE_DOCKER; then
  install_docker_engine
  mkdir -p "$ROOT/instance"
  if [ ! -f "$ROOT/.env" ]; then
    cp "$ROOT/.env.example" "$ROOT/.env" 2>/dev/null || true
  fi
  set_env_kv "$ROOT/.env" PORT "$CHOSEN_PORT"
  if ! grep -q '^SECRET_KEY=' "$ROOT/.env" 2>/dev/null; then
    SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    set_env_kv "$ROOT/.env" SECRET_KEY "$SECRET"
  fi
  echo "==> Starting WarehouseDB with Docker"
  sudo docker compose up -d --build
  echo
  echo "==> Done (Docker). Staff board: http://127.0.0.1:${CHOSEN_PORT}"
  echo "    logs: docker compose logs -f warehouse"
  echo "    tunnel: see deploy/CLOUDFLARE-TUNNEL.md"
  exit 0
fi

if [ ! -d "$VENV" ]; then
  echo "==> Creating virtualenv at $VENV"
  "$PYTHON" -m venv "$VENV"
fi
echo "==> Installing Python dependencies"
"$VENV/bin/pip" install --upgrade pip >/dev/null
"$VENV/bin/pip" install -r requirements.txt

mkdir -p "$ROOT/instance"
if [ ! -f "$ENV_FILE" ]; then
  echo "==> Generating $ENV_FILE"
  SECRET="$("$VENV/bin/python" -c 'import secrets; print(secrets.token_hex(32))')"
  cat >"$ENV_FILE" <<EOF
FLASK_ENV=production
SECRET_KEY=$SECRET
HOST=0.0.0.0
PORT=$CHOSEN_PORT
STORE_API_KEY=store-dev-key
SCAN_API_KEY=scan-dev-key
SCAN_PUBLIC_URL=http://localhost:5002
SESSION_COOKIE_SECURE=false
EOF
  chmod 600 "$ENV_FILE"
else
  echo "==> Updating PORT in existing $ENV_FILE"
  set_env_kv "$ENV_FILE" PORT "$CHOSEN_PORT"
fi

echo "==> Initialising database"
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a
"$VENV/bin/flask" --app run init-db

chmod +x "$ROOT/start.sh"

if $INSTALL_SERVICE; then
  RUN_USER="${SUDO_USER:-$(whoami)}"
  install_systemd warehousedb "$ROOT/deploy/warehousedb.service" "$ROOT" "$RUN_USER"
  echo "    logs: journalctl -u warehousedb -f"
else
  echo
  echo "Start manually:"
  echo "    set -a; . instance/warehousedb.env; set +a"
  echo "    .venv/bin/waitress-serve --host \$HOST --port \$PORT wsgi:app"
fi

echo
echo "  ${GREEN}${BOLD}✓ WarehouseDB ready${RESET}"
echo
echo "    ${BOLD}Staff board${RESET}    http://<server-ip>:${CHOSEN_PORT}"
echo "    ${BOLD}Health${RESET}         http://127.0.0.1:${CHOSEN_PORT}/api/health"
echo "    ${BOLD}Service${RESET}        systemctl status warehousedb"
echo "    ${BOLD}Public domain${RESET}  deploy/CLOUDFLARE-TUNNEL.md"
echo
