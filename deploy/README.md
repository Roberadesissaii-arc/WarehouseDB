# Deploying WarehouseDB

Run on Ubuntu / Debian with one command, or use **Docker**.

## Quick install (Ubuntu server)

```bash
cd WarehouseDB
./install.sh
```

This will:

1. Ask for your **sudo password** (apt update/upgrade, system packages)
2. Pick the first free port starting at **8000** (8001, 8002, … if busy)
3. Create venv, database, and **systemd service** (starts now + on every reboot)
4. Install **cloudflared** for an optional public domain later — see `deploy/CLOUDFLARE-TUNNEL.md`

```bash
./install.sh --no-service   # install only, no systemd
./install.sh --docker       # Docker instead of native venv
```

Staff board: `http://<server-ip>:<PORT>` (PORT is in `instance/warehousedb.env`).

```bash
systemctl status warehousedb
journalctl -u warehousedb -f
```

## Docker — warehouse only

```bash
cd WarehouseDB
cp .env.example .env
./install.sh --docker
# or: docker compose up --build -d
```

Data persists in volume `warehousedb_data`.

## Docker — full platform (warehouse + store + scan)

From `WarehouseDB/` when you have the full monorepo:

```bash
cp .env.example .env
docker compose -f docker-compose.all.yml up --build -d
```

| Service | URL |
|---------|-----|
| Warehouse (staff) | http://localhost:8000 |
| Customer store | http://localhost:5001 |
| Floor scan PWA | http://localhost:5002 |

## Split servers

Copy each app folder to its own Ubuntu host and run `./install.sh` in that folder. Each installer picks free ports independently.

| App | Default ports | Env file |
|-----|---------------|----------|
| WarehouseDB | 8000+ | `instance/warehousedb.env` |
| Scan | PWA 5002+, API 5003+ | `.env` |
| Store | UI 5001+, API 5004+ | `.env.local` |

Match `STORE_API_KEY` / `SCAN_API_KEY` on WarehouseDB with the same keys in store/scan env files. Set `WAREHOUSE_URL` on store/scan to the warehouse host (or Cloudflare tunnel URL).

See **[Warehouse_store/README.md](../../Warehouse_store/README.md)** and **[Warehouse_scan/README.md](../../Warehouse_scan/README.md)**.

Default login: **none** — first visit creates the one warehouse account on the login page. Change credentials under **Settings → Account**.

## Notes

- **Backup:** `instance/warehouse.db` or Settings → Export (JSON).
- **cloudflared:** binary installed during `./install.sh`; tunnel login/create is manual — `deploy/CLOUDFLARE-TUNNEL.md`.
- **Robots:** flash firmware from `Arduino/` — see `Arduino/README.md`.

## Verify before handoff

```bash
python scripts/verify.py
```
