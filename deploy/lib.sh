#!/usr/bin/env bash
# Shared helpers for Ubuntu/Debian installers (sourced, not executed).
set -euo pipefail

SUDO_KEEPALIVE_PID=""

ensure_sudo() {
  if [ "$(id -u)" -eq 0 ]; then
    return
  fi
  echo "==> Installer needs sudo (system packages + auto-start on boot)."
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

apt_bootstrap() {
  echo "==> apt update / upgrade"
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3 python3-venv python3-pip curl ca-certificates gnupg lsb-release
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
  echo "==> Installing cloudflared (optional tunnel for a public domain later)"
  if command -v cloudflared >/dev/null 2>&1; then
    echo "    already installed: $(cloudflared --version 2>/dev/null | head -1)"
    return
  fi
  curl -fsSL https://pkg.cloudflare.com/cloudflare-public-v2.gpg | sudo tee /usr/share/keyrings/cloudflare-public-v2.gpg >/dev/null
  echo "deb [signed-by=/usr/share/keyrings/cloudflare-public-v2.gpg] https://pkg.cloudflare.com/cloudflared $(. /etc/os-release && echo "${VERSION_CODENAME:-$UBUNTU_CODENAME}") main" \
    | sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null
  sudo apt-get update -qq
  if sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cloudflared; then
    echo "    cloudflared installed"
  else
    echo "    !! cloudflared apt install failed — see deploy/CLOUDFLARE-TUNNEL.md"
  fi
}

install_docker_engine() {
  echo "==> Installing Docker"
  if command -v docker >/dev/null 2>&1; then
    echo "    already installed"
    return
  fi
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io
  if command -v docker >/dev/null 2>&1; then
    sudo usermod -aG docker "${SUDO_USER:-$USER}" 2>/dev/null || true
    echo "    Docker installed (log out/in if 'docker' permission denied)"
  fi
}

ensure_node() {
  if command -v node >/dev/null 2>&1; then
    local major
    major="$(node -p 'process.versions.node.split(".")[0]')"
    if [ "$major" -ge 18 ]; then
      return
    fi
  fi
  echo "==> Installing Node.js 22"
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs
  if command -v corepack >/dev/null 2>&1; then
    sudo corepack enable
  fi
}

ensure_pnpm() {
  if command -v pnpm >/dev/null 2>&1; then
    return
  fi
  ensure_node
  corepack enable
  corepack prepare pnpm@9 --activate
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
  echo "==> Service $name enabled — starts automatically on boot"
  echo "    status: systemctl status $name"
}
