#!/usr/bin/env bash
# Shared helpers for Ubuntu/Debian installers (sourced, not executed).
set -euo pipefail

# ── Presentation ──────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  GREEN=$'\033[1;32m'; CYAN=$'\033[1;36m'; YELLOW=$'\033[33m'; RED=$'\033[31m'
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
else
  GREEN=''; CYAN=''; YELLOW=''; RED=''; BOLD=''; DIM=''; RESET=''
fi

__STEP=0
step() { __STEP=$((__STEP + 1)); printf '\n  %s━━━━ Step %d · %s%s\n' "$CYAN" "$__STEP" "$1" "$RESET"; }
ok()   { printf '    %s✔%s  %s\n' "$GREEN" "$RESET" "$1"; }
warn() { printf '    %s⚠%s  %s\n' "$YELLOW" "$RESET" "$1"; }
note() { printf '    %s%s%s\n' "$DIM" "$1" "$RESET"; }
fail() { printf '    %s✖%s  %s\n' "$RED" "$RESET" "$1" >&2; exit 1; }

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
  note "apt update + upgrade (this can take a minute)…"
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq
  note "installing python3, python3-venv, python3-pip, curl, gnupg…"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3 python3-venv python3-pip curl ca-certificates gnupg lsb-release
  ok "Python $(python3 -V 2>&1 | awk '{print $2}') + pip + venv ready"
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
    return
  fi
  note "installing cloudflared (optional tunnel for a public domain later)…"
  curl -fsSL https://pkg.cloudflare.com/cloudflare-public-v2.gpg | sudo tee /usr/share/keyrings/cloudflare-public-v2.gpg >/dev/null
  echo "deb [signed-by=/usr/share/keyrings/cloudflare-public-v2.gpg] https://pkg.cloudflare.com/cloudflared $(. /etc/os-release && echo "${VERSION_CODENAME:-$UBUNTU_CODENAME}") main" \
    | sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null
  sudo apt-get update -qq
  if sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cloudflared; then
    ok "cloudflared installed"
  else
    warn "cloudflared apt install failed — see deploy/CLOUDFLARE-TUNNEL.md"
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
  note "installing Node.js 22 from NodeSource…"
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs
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
  corepack prepare pnpm@9 --activate
  ok "pnpm $(pnpm --version 2>/dev/null || echo 9) ready"
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
