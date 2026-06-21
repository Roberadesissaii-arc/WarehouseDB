#!/usr/bin/env bash
#
# WarehouseDB — clean teardown
#
#   ./uninstall.sh           # stop + remove the service, kill background processes
#   ./uninstall.sh --purge   # also delete the virtualenv and the database (instance/)
#
# After this you can re-run ./install.sh, or delete the whole folder:  rm -rf <this dir>
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PURGE=false
[ "${1:-}" = "--purge" ] && PURGE=true

echo "==> Stopping and removing the warehousedb service"
sudo systemctl stop warehousedb 2>/dev/null || true
sudo systemctl disable warehousedb 2>/dev/null || true
sudo rm -f /etc/systemd/system/warehousedb.service
sudo systemctl daemon-reload 2>/dev/null || true

echo "==> Terminating any stray WarehouseDB processes"
sudo pkill -9 -f 'waitress-serve.*wsgi:app' 2>/dev/null || true
sudo pkill -9 -f 'flask --app run' 2>/dev/null || true
PORT="$(grep -oP '(?<=^PORT=)\d+' "$ROOT/instance/warehousedb.env" 2>/dev/null || echo 8000)"
sudo pkill -9 -f "cloudflared tunnel --url http://127.0.0.1:${PORT}" 2>/dev/null || true
if command -v fuser >/dev/null 2>&1; then
  sudo fuser -k "$ROOT/instance/warehouse.db" 2>/dev/null || true
fi
sleep 1

if $PURGE; then
  echo "==> Purging virtualenv + database"
  rm -rf "$ROOT/.venv" "$ROOT/instance"
fi

echo
echo "==> Done. WarehouseDB is stopped and the service is removed."
if $PURGE; then
  echo "    Removed .venv and instance/ (database). Re-run ./install.sh for a fresh setup."
else
  echo "    Kept .venv + instance/. Use --purge to delete them, or 'rm -rf $ROOT' to remove everything."
fi
