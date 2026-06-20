# WarehouseDB

**Your warehouse, your control.** Self-hosted.

WarehouseDB is the hub of the warehouse system — a staff board for inventory, the robot
fleet, pick tasks, the floor map, and settings. Robots and the customer apps (Store, Scan)
all connect to it. Run it on your own machine; no cloud account required.

Server-rendered Flask + SQLite — **one process, one port (8000)**, no separate frontend to run.

| App | Folder | Port | What it is |
|-----|--------|------|------------|
| **WarehouseDB** (this repo) | `.` | 8000 | Inventory + fleet + tasks hub |
| **Store** | `../Warehouse_store` | 5001 UI · 5004 API | Customer storefront |
| **Scan** | `../Warehouse_scan` | 5002 UI · 5003 API | Staff floor PWA |

## What you get

| Area | Description |
|------|-------------|
| First-run setup | Claim the instance on first visit — create the one owner account (no public signup) |
| Inventory | Warehouses → sections → shelves → items, with SKU generation and CSV/JSON import |
| Fleet | Pair robots with a code, assign home bays, watch live status on the floor map |
| Tasks | Pick tasks queued to robots, manual fulfilment, and a store-order backlog queue |
| Map | Live floor view of bays, robots, and zones |
| Settings | Account, security, organization, notifications, data import/export |
| Warehouse Relay | Optional Cloudflare tunnel for a public URL — toggle in **Settings** |
| Notifications | In-app inbox + desktop/mobile toasts when something needs attention |
| Robots | ESP32 firmware in `Arduino/` pairs each unit to this server |

## Prerequisites

A Linux server or Raspberry Pi (Debian/Ubuntu) with `git`, `sudo`, and Python 3.10+.
The installer pulls in everything else. (Windows is supported for local development — see below.)

## Quick start

```bash
git clone https://github.com/Roberadesissaii-arc/WarehouseDB.git
cd WarehouseDB
chmod +x install.sh
./install.sh
```

`./install.sh` will, in one shot:

1. Install system deps (apt update, Python venv, `cloudflared` for tunnels)
2. Create the virtualenv and install requirements
3. Generate `instance/warehousedb.env` with a random `SECRET_KEY`
4. Initialise the SQLite database
5. Register a **systemd service** (`systemctl enable --now warehousedb`) — it **starts now
   and again on every boot**, and restarts on crash

When it finishes it prints the URL, e.g. `http://<server-ip>:8000`.

> You run `install.sh` **once**. After that WarehouseDB is always on — **you never start
> it by hand.** Re-run it anytime to update after `git pull`.

```bash
./install.sh --no-service   # install only — start by hand
./install.sh --docker       # run with Docker instead of a native venv
```

**First sign-in:** open the URL and create the one owner account on the login page
(username + password, 8+ chars with a letter and a number). Change it later under
**Settings → Account**.

## Managing the service

```bash
systemctl status warehousedb            # is it running?
sudo systemctl restart warehousedb      # restart now
sudo systemctl stop warehousedb         # stop until next boot
sudo systemctl disable warehousedb      # stop auto-starting on boot
journalctl -u warehousedb -f            # live logs

git pull && ./install.sh                # update after pulling new code
```

## Public access (Cloudflare tunnel)

Turn on **Warehouse Relay** under **Settings** to expose WarehouseDB on a public URL while
it runs. Quick tunnels get a random `*.trycloudflare.com` link that stays the same until you
restart the server; a named tunnel gives you a fixed domain. See
[deploy/CLOUDFLARE-TUNNEL.md](deploy/CLOUDFLARE-TUNNEL.md).

## Development (Windows / macOS / Linux)

Single process — no separate frontend:

```bash
cd WarehouseDB
pip install -r requirements.txt
python run.py                 # http://localhost:8000
```

Copy [.env.example](.env.example) to `.env` to override defaults (secret keys, ports, the
`store-dev-key` / `scan-dev-key` API keys shared with Store and Scan).

Handy scripts:

```bash
python scripts/debug.py status
python scripts/verify.py
python -m unittest discover -s tests   # smoke tests
```

## Environment

Generated as `instance/warehousedb.env` on install. Key values:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | *(generated)* | Flask session signing |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Bind address and port |
| `STORE_API_KEY` | `store-dev-key` | Shared key the Store app authenticates with |
| `SCAN_API_KEY` | `scan-dev-key` | Shared key the Scan app authenticates with |
| `SCAN_PUBLIC_URL` | `http://localhost:5002` | LAN URL printed in item QR codes |
| `SESSION_COOKIE_SECURE` | `false` | Set `true` behind HTTPS |

See [.env.example](.env.example) for the full list.

## Project layout

```
WarehouseDB/
├── app/                  # Flask app: routes, models, templates, static
│   ├── api/              # JSON API (robots, store, tasks, settings, relay…)
│   ├── models/           # SQLite data access (item, robot, task, store_pending…)
│   ├── warehouse_relay.py# Cloudflare tunnel control (Warehouse Relay)
│   ├── templates/        # Server-rendered pages
│   └── static/           # JS, CSS, icons, PWA manifest + service worker
├── deploy/               # install.sh, systemd unit, Cloudflare guide
├── Arduino/              # ESP32 robot firmware per unit
├── json/                 # Sample import data
├── scripts/              # debug / verify / maintenance
├── tests/                # Smoke tests
└── run.py                # Dev entrypoint
```

## Documentation

| Doc | Contents |
|-----|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design |
| [deploy/README.md](deploy/README.md) | Docker + production deploy |
| [deploy/CLOUDFLARE-TUNNEL.md](deploy/CLOUDFLARE-TUNNEL.md) | Public domain via Cloudflare |
| [scripts/DOCUMENTATION.md](scripts/DOCUMENTATION.md) | Maintenance scripts |
| [Arduino/README.md](Arduino/README.md) | Flashing robot firmware |

License: [MIT](LICENSE) · Third-party: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)

WarehouseDB — built for the warehouse you own.
