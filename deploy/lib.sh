#!/usr/bin/env bash
# Shared helpers for Ubuntu/Debian installers (sourced, not executed).
set -euo pipefail

# ── Presentation ──────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  GREEN=$'\033[1;32m'; CYAN=$'\033[1;36m'; YELLOW=$'\033[33m'; RED=$'\033[31m'
  WHITE=$'\033[97m'; BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
else
  GREEN=''; CYAN=''; YELLOW=''; RED=''; WHITE=''; BOLD=''; DIM=''; RESET=''
fi

__STEP=0
TOTAL_STEPS="${TOTAL_STEPS:-0}"
__RULE='━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
step() {
  __STEP=$((__STEP + 1))
  local n="Step ${__STEP}"
  if [ "${TOTAL_STEPS:-0}" -gt 0 ]; then n="Step ${__STEP}/${TOTAL_STEPS}"; fi
  printf '\n  %s%s%s\n' "$CYAN" "$__RULE" "$RESET"
  printf '  %s%s%s  %s%s%s\n' "$BOLD" "$WHITE" "$n" "$RESET$BOLD" "$1" "$RESET"
  printf '  %s%s%s\n' "$CYAN" "$__RULE" "$RESET"
}
ok()   { printf '    %s✔%s  %s\n' "$GREEN" "$RESET" "$1"; }
warn() { printf '    %s⚠%s  %s\n' "$YELLOW" "$RESET" "$1"; }
note() { printf '    %s%s%s\n' "$DIM" "$1" "$RESET"; }
fail() { printf '    %s✖%s  %s\n' "$RED" "$RESET" "$1" >&2; exit 1; }

# spin "Message" cmd args…  — runs the command in the background while showing an
# animated loader + elapsed time. Output is captured; shown only on failure.
# Sudo must be pre-authenticated (ensure_sudo) before any spinner that uses sudo.
__SPIN_LOG=""
spin() {
  local msg="$1"; shift
  local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
  local i=0 c start elapsed mins secs code log pid
  log="$(mktemp)"; __SPIN_LOG="$log"
  "$@" >"$log" 2>&1 &
  pid=$!
  start=$(date +%s)
  if [ -t 1 ]; then
    while kill -0 "$pid" 2>/dev/null; do
      elapsed=$(( $(date +%s) - start ))
      c="${frames[$(( i % ${#frames[@]} ))]}"
      if [ "$elapsed" -ge 2 ]; then
        mins=$(( elapsed / 60 )); secs=$(( elapsed % 60 ))
        printf '\r    %s%s%s  %s%s%s  %s%d:%02d%s   ' "$CYAN" "$c" "$RESET" "$DIM" "$msg" "$RESET" "$DIM" "$mins" "$secs" "$RESET"
      else
        printf '\r    %s%s%s  %s%s%s   ' "$CYAN" "$c" "$RESET" "$DIM" "$msg" "$RESET"
      fi
      i=$(( i + 1 ))
      sleep 0.12
    done
    printf '\r\033[2K'
  fi
  wait "$pid" && code=0 || code=$?
  if [ "$code" -eq 0 ]; then rm -f "$log"; __SPIN_LOG=""; fi
  return "$code"
}

# spin_ok "Loading…" "Done." cmd args…  — spin, then print ✔ done (or show the
# captured output and abort on failure).
spin_ok() {
  local label="$1" done_msg="$2"; shift 2
  if spin "$label" "$@"; then
    ok "$done_msg"
  else
    printf '\n'
    warn "step failed: $label"
    if [ -n "${__SPIN_LOG:-}" ] && [ -f "${__SPIN_LOG:-}" ]; then
      printf '    %slast output:%s\n' "$YELLOW" "$RESET"
      sed 's/^/      /' "$__SPIN_LOG"
      rm -f "$__SPIN_LOG"; __SPIN_LOG=""
    fi
    fail "$label failed"
  fi
}

SUDO_KEEPALIVE_PID=""

ensure_sudo() {
  if [ "$(id -u)" -eq 0 ]; then
    return
  fi
  note "Installer needs sudo (system packages + auto-start on boot)."
  sudo -v
  while true; do
    sudo -n true
    sleep 60
    kill -0 "$$" || exit
  done 2>/dev/null &
  SUDO_KEEPALIVE_PID=$!
}

stop_sudo_keepalive() {
  if [ -n "$SUDO_KEEPALIVE_PID" ]; then
    kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
  fi
}

# Installs the base toolchain every app needs: Python 3 + venv + pip and friends.
apt_bootstrap() {
  spin_ok "Updating + upgrading system packages…" "System packages up to date" \
    bash -c 'sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq'
  spin_ok "Installing Python, pip, venv, curl, gnupg…" "Base toolchain installed" \
    bash -c 'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-venv python3-pip curl ca-certificates gnupg lsb-release psmisc'
  ok "Python $(python3 -V 2>&1 | awk '{print $2}') ready"
}

# Free a SQLite db file held by a stray/orphaned process (e.g. a previous install
# that was Ctrl+C'd), so init-db can't deadlock waiting for the lock. psmisc
# (installed above) provides fuser; without it this is a safe no-op.
free_database() {
  local dbfile=$1
  [ -e "$dbfile" ] || return 0
  command -v fuser >/dev/null 2>&1 || return 0
  if sudo fuser -s "$dbfile" 2>/dev/null; then
    warn "another process still holds the database — terminating it"
    sudo fuser -k "$dbfile" 2>/dev/null || true
    sleep 1
  fi
}

port_is_used() {
  local port=$1
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | grep -qE ":${port}[[:space:]]"
    return $?
  fi
  python3 - "$port" <<'PY'
import socket, sys
p = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.25)
try:
    raise SystemExit(0 if s.connect_ex(("127.0.0.1", p)) == 0 else 1)
finally:
    s.close()
PY
}

find_free_port() {
  local port=$1
  local limit=$((port + 50))
  while [ "$port" -lt "$limit" ]; do
    if ! port_is_used "$port"; then
      echo "$port"
      return
    fi
    echo "    Port $port is in use — trying $((port + 1))..." >&2
    port=$((port + 1))
  done
  echo "!! No free port between $1 and $limit" >&2
  exit 1
}

set_env_kv() {
  local file=$1 key=$2 val=$3
  touch "$file"
  if grep -q "^${key}=" "$file" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$file"
  else
    echo "${key}=${val}" >>"$file"
  fi
}

install_cloudflared() {
  if command -v cloudflared >/dev/null 2>&1; then
    ok "cloudflared already installed ($(cloudflared --version 2>/dev/null | head -1))"
    # systemd services run with a minimal PATH (no ~/.local/bin). Make sure the
    # binary is reachable from /usr/local/bin so the relay can find it.
    local cf; cf="$(command -v cloudflared)"
    if [ "$cf" != "/usr/local/bin/cloudflared" ] && [ ! -x /usr/bin/cloudflared ]; then
      sudo ln -sf "$cf" /usr/local/bin/cloudflared 2>/dev/null \
        && note "linked cloudflared into /usr/local/bin (for the service)" || true
    fi
    return
  fi
  # Try the official apt repo first (clean auto-updates). It doesn't cover every
  # Ubuntu/Debian codename, so fall back to the static binary from GitHub.
  if spin "Installing cloudflared (apt)…" bash -c '
      set -e
      curl -fsSL https://pkg.cloudflare.com/cloudflare-public-v2.gpg | sudo tee /usr/share/keyrings/cloudflare-public-v2.gpg >/dev/null
      echo "deb [signed-by=/usr/share/keyrings/cloudflare-public-v2.gpg] https://pkg.cloudflare.com/cloudflared $(. /etc/os-release && echo "${VERSION_CODENAME:-$UBUNTU_CODENAME}") main" | sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null
      sudo apt-get update -qq
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cloudflared
    ' && command -v cloudflared >/dev/null 2>&1; then
    ok "cloudflared installed ($(cloudflared --version 2>/dev/null | head -1))"
    return
  fi
  rm -f "${__SPIN_LOG:-}" 2>/dev/null || true; __SPIN_LOG=""
  # apt repo has no package for this distro/codename — install the static binary.
  sudo rm -f /etc/apt/sources.list.d/cloudflared.list 2>/dev/null || true
  local cf_arch
  case "$(uname -m)" in
    x86_64|amd64) cf_arch=amd64 ;;
    aarch64|arm64) cf_arch=arm64 ;;
    armv7l|armhf) cf_arch=arm ;;
    *) cf_arch=amd64 ;;
  esac
  if spin "Installing cloudflared (direct ${cf_arch} binary)…" bash -c "
      set -e
      sudo curl -fsSL 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${cf_arch}' -o /usr/local/bin/cloudflared
      sudo chmod +x /usr/local/bin/cloudflared
    " && command -v cloudflared >/dev/null 2>&1; then
    ok "cloudflared installed ($(cloudflared --version 2>/dev/null | head -1))"
  else
    rm -f "${__SPIN_LOG:-}" 2>/dev/null || true; __SPIN_LOG=""
    warn "cloudflared install failed — relay/tunnel will stay off (see deploy/CLOUDFLARE-TUNNEL.md)"
  fi
}

install_docker_engine() {
  if command -v docker >/dev/null 2>&1; then
    ok "Docker already installed"
    return
  fi
  note "installing Docker engine…"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io
  if command -v docker >/dev/null 2>&1; then
    sudo usermod -aG docker "${SUDO_USER:-$USER}" 2>/dev/null || true
    ok "Docker installed (log out/in if 'docker' permission denied)"
  fi
}

ensure_node() {
  if command -v node >/dev/null 2>&1; then
    local major
    major="$(node -p 'process.versions.node.split(".")[0]')"
    if [ "$major" -ge 18 ]; then
      ok "Node.js $(node -v) already installed"
      return
    fi
  fi
  spin_ok "Installing Node.js 22 from NodeSource…" "Node.js installed" bash -c '
      curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs
    '
  if command -v corepack >/dev/null 2>&1; then
    sudo corepack enable
  fi
  ok "Node.js $(node -v) ready"
}

ensure_pnpm() {
  if command -v pnpm >/dev/null 2>&1; then
    ok "pnpm $(pnpm --version) already installed"
    return
  fi
  ensure_node
  corepack enable
  spin_ok "Activating pnpm…" "pnpm ready" corepack prepare pnpm@9 --activate
  ok "pnpm $(pnpm --version 2>/dev/null || echo 9) ready"
}

# Stop a running instance of this service before reinstalling, so it doesn't
# keep holding its port or an open lock on the SQLite database (which makes
# `init-db` hang). Safe when the service isn't installed or isn't running.
stop_service_if_running() {
  local name=$1
  command -v systemctl >/dev/null 2>&1 || return 0
  if systemctl is-active --quiet "$name" 2>/dev/null; then
    note "stopping running ${name} (frees its port + unlocks the database)…"
    sudo systemctl stop "$name" 2>/dev/null || true
    sleep 1
  fi
}

# Run an app as a per-user systemd service — NO root. Used by the web-triggered
# "Install" button in WarehouseDB. Needs lingering (enabled by WarehouseDB's
# terminal install) to survive reboots; falls back to a detached process if the
# user systemd bus isn't reachable, so the app at least runs immediately.
install_user_service() {
  local name=$1 root=$2 venv=$3
  local udir="$HOME/.config/systemd/user"
  mkdir -p "$udir"
  cat >"$udir/${name}.service" <<EOF
[Unit]
Description=${name} (Warehouse add-on)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${root}
EnvironmentFile=-${root}/.env.local
EnvironmentFile=-${root}/.env
EnvironmentFile=-${root}/instance/install.env
Environment=PATH=${venv}/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=${root}/start.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  if systemctl --user daemon-reload 2>/dev/null && systemctl --user enable --now "$name" 2>/dev/null; then
    echo "    user service ${name} started (auto-starts on boot)"
    return 0
  fi
  echo "    user systemd not available — starting ${name} in the background"
  ( cd "$root" && setsid nohup ./start.sh >"$root/instance/run.log" 2>&1 & ) || true
}

install_systemd() {
  local name=$1 template=$2 root=$3 user=$4
  shift 4
  local tmp unit="/etc/systemd/system/${name}.service"
  tmp="$(mktemp)"
  sed -e "s|@ROOT@|$root|g" -e "s|@USER@|$user|g" "$@" "$template" >"$tmp"
  sudo cp "$tmp" "$unit"
  rm -f "$tmp"
  sudo systemctl daemon-reload
  sudo systemctl enable --now "$name"
  ok "Service $name enabled — starts now and on every boot"
}

# Open a TCP port in ufw — but only if ufw is installed AND active, so we never
# turn on a firewall the user isn't using or touch a different firewall setup.
open_firewall_port() {
  local port=$1 label="${2:-app}"
  if ! command -v ufw >/dev/null 2>&1; then
    note "ufw not installed — skipping firewall (open port ${port}/tcp on your firewall if needed)"
    return 0
  fi
  if ! sudo ufw status 2>/dev/null | grep -q '^Status: active'; then
    note "ufw is inactive — nothing blocking port ${port}; not enabling the firewall"
    return 0
  fi
  if sudo ufw status 2>/dev/null | grep -qE "^${port}/tcp[[:space:]]"; then
    ok "Firewall already allows ${port}/tcp"
    return 0
  fi
  if sudo ufw allow "${port}/tcp" comment "$label" >/dev/null 2>&1; then
    ok "Opened firewall port ${port}/tcp ($label)"
  else
    warn "Could not open ${port}/tcp in ufw — run: sudo ufw allow ${port}/tcp"
  fi
}
