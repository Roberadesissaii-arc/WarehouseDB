#!/usr/bin/env bash
#
# WarehouseDB — Ubuntu / Debian installer
#
#   ./install.sh              # deps + venv + DB + systemd (auto-start on boot)
#   ./install.sh --no-service # install only, start manually
#   ./install.sh --docker     # Docker instead of native venv
#   ./install.sh --reset      # wipe the database, then reinstall fresh
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
RESET_DB=false

usage() {
  sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --service) INSTALL_SERVICE=true ;;
    --no-service) INSTALL_SERVICE=false ;;
    --docker) USE_DOCKER=true ;;
    --reset) RESET_DB=true ;;
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

TOTAL_STEPS=7
if [ -t 1 ]; then clear 2>/dev/null || true; fi
printf '\n  %sW A R E H O U S E%s\n%s' "$DIM" "$RESET" "$GREEN"
cat <<'ART'
  ██████╗  █████╗ ████████╗ █████╗ ██████╗  █████╗ ███████╗███████╗
  ██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔════╝
  ██║  ██║███████║   ██║   ███████║██████╔╝███████║███████╗█████╗
  ██║  ██║██╔══██║   ██║   ██╔══██║██╔══██╗██╔══██║╚════██║██╔══╝
  ██████╔╝██║  ██║   ██║   ██║  ██║██████╔╝██║  ██║███████║███████╗
  ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝
ART
printf '%s\n' "$RESET"
echo "  ${BOLD}WarehouseDB${RESET}  ${DIM}— inventory & fleet control hub${RESET}                ${DIM}self-hosted${RESET}"
echo "  ${DIM}──────────────────────────────────────────────────────────${RESET}"
echo

step "System packages & toolchain"
ensure_sudo
stop_service_if_running warehousedb
apt_bootstrap
install_cloudflared

step "Network port"
DEFAULT_PORT=8000
CHOSEN_PORT="$(find_free_port "$DEFAULT_PORT")"
if [ "$CHOSEN_PORT" != "$DEFAULT_PORT" ]; then
  ok "Using port $CHOSEN_PORT (default $DEFAULT_PORT was busy)"
else
  ok "Using port $CHOSEN_PORT"
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
  step "Docker"
  note "starting WarehouseDB with Docker…"
  sudo docker compose up -d --build
  echo
  ok "WarehouseDB running (Docker) — http://127.0.0.1:${CHOSEN_PORT}"
  open_firewall_port "$CHOSEN_PORT" "WarehouseDB"
  note "logs: docker compose logs -f warehouse"
  note "tunnel: see deploy/CLOUDFLARE-TUNNEL.md"
  exit 0
fi

step "Python environment"
if [ ! -d "$VENV" ]; then
  note "creating virtualenv at $VENV"
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/pip" install --upgrade pip >/dev/null 2>&1 || true
spin_ok "Installing Python dependencies…" "Python dependencies installed" \
  "$VENV/bin/pip" install -r requirements.txt

step "Configuration"
mkdir -p "$ROOT/instance"
gen_key() { "$VENV/bin/python" -c 'import secrets; print(secrets.token_hex(24))'; }
if [ ! -f "$ENV_FILE" ]; then
  note "generating $ENV_FILE with a random secret + API keys"
  SECRET="$("$VENV/bin/python" -c 'import secrets; print(secrets.token_hex(32))')"
  STORE_KEY="$(gen_key)"
  SCAN_KEY="$(gen_key)"
  cat >"$ENV_FILE" <<EOF
FLASK_ENV=production
SECRET_KEY=$SECRET
HOST=0.0.0.0
PORT=$CHOSEN_PORT
STORE_API_KEY=$STORE_KEY
SCAN_API_KEY=$SCAN_KEY
SCAN_PUBLIC_URL=http://localhost:5002
SESSION_COOKIE_SECURE=false
EOF
  chmod 600 "$ENV_FILE"
  ok "Created $ENV_FILE (strong SECRET_KEY + API keys)"
else
  note "updating existing $ENV_FILE"
  set_env_kv "$ENV_FILE" PORT "$CHOSEN_PORT"
  # The production guard refuses to start with the old dev defaults — replace them.
  if grep -q '^STORE_API_KEY=store-dev-key$' "$ENV_FILE"; then
    set_env_kv "$ENV_FILE" STORE_API_KEY "$(gen_key)"
    warn "Replaced insecure default STORE_API_KEY with a strong value"
  fi
  if grep -q '^SCAN_API_KEY=scan-dev-key$' "$ENV_FILE"; then
    set_env_kv "$ENV_FILE" SCAN_API_KEY "$(gen_key)"
    warn "Replaced insecure default SCAN_API_KEY with a strong value"
  fi
fi

step "Database"
DB_FILE="$ROOT/instance/warehouse.db"
if $RESET_DB; then
  warn "--reset: wiping the existing database for a clean start"
  rm -f "$ROOT"/instance/warehouse.db* 2>/dev/null || true
fi
free_database "$DB_FILE"
# Time-bound so a lock can never hang the installer; the schema also initialises
# on service start, so this is a fast pre-check rather than a hard dependency.
if spin "Initialising SQLite database…" \
     timeout --kill-after=5 60 bash -c 'cd "$3"; set -a; . "$1"; set +a; WAREHOUSE_SKIP_RELAY=1 "$2"/bin/flask --app run init-db' _ "$ENV_FILE" "$VENV" "$ROOT"; then
  ok "Database ready"
else
  rm -f "${__SPIN_LOG:-}" 2>/dev/null || true; __SPIN_LOG=""
  warn "Database init didn't finish — something is still holding ${DB_FILE}."
  warn "Fix: sudo fuser -k '${DB_FILE}'  (or reboot), then re-run ./install.sh"
  fail "Could not initialise the database"
fi

chmod +x "$ROOT/start.sh"

step "Service (auto-start on boot)"
if $INSTALL_SERVICE; then
  RUN_USER="${SUDO_USER:-$(whoami)}"
  install_systemd warehousedb "$ROOT/deploy/warehousedb.service" "$ROOT" "$RUN_USER"
  note "logs: journalctl -u warehousedb -f"
  # Let per-user services survive reboots — used by Store/Scan when installed from
  # the Integration page's INSTALL button (which runs without root).
  sudo loginctl enable-linger "$RUN_USER" >/dev/null 2>&1 && note "user-service lingering enabled for $RUN_USER" || true
else
  note "Start manually:"
  note "  set -a; . instance/warehousedb.env; set +a"
  note "  .venv/bin/waitress-serve --host \$HOST --port \$PORT wsgi:app"
fi

step "Firewall"
open_firewall_port "$CHOSEN_PORT" "WarehouseDB"

STORE_API_KEY_VAL="$(grep '^STORE_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
SCAN_API_KEY_VAL="$(grep '^SCAN_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"

echo
echo "  ${GREEN}${BOLD}✓ WarehouseDB ready${RESET}"
echo
echo "    ${BOLD}Staff board${RESET}    http://<server-ip>:${CHOSEN_PORT}"
echo "    ${BOLD}Health${RESET}         http://127.0.0.1:${CHOSEN_PORT}/api/health"
echo "    ${BOLD}Service${RESET}        systemctl status warehousedb"
echo "    ${BOLD}Public domain${RESET}  deploy/CLOUDFLARE-TUNNEL.md"
echo
echo "  ${DIM}Store & Scan must use these same API keys to connect. If they run on${RESET}"
echo "  ${DIM}another machine, set them there; on this machine their installer copies${RESET}"
echo "  ${DIM}them automatically.${RESET}"
echo "    ${BOLD}STORE_API_KEY${RESET}  ${STORE_API_KEY_VAL}"
echo "    ${BOLD}SCAN_API_KEY${RESET}   ${SCAN_API_KEY_VAL}"
echo
