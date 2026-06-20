# Three-app architecture

Each app runs on its own server with its **own credential database**. Inventory, robots, and tasks live only in **WarehouseDB**. Store and Scan read that data over **HTTP APIs** — they never open `warehouse.db` directly.

## Repository layout

```
test/
├── WarehouseDB/          # Main warehouse server (Flask, port 8000)
│   ├── Arduino/          # ESP32 robot firmware
│   ├── json/             # Sample product import data
│   ├── tests/            # WarehouseDB smoke tests
│   ├── scripts/          # Admin / debug tools
│   ├── deploy/           # Bare-metal install
│   ├── Dockerfile        # Shared image for all three apps
│   └── docker-compose.yml
├── Warehouse_scan/       # Floor scan PWA (UI 5002, API 5003)
└── Warehouse_store/      # Customer storefront (UI 5001, API 5004)
```

```
┌─────────────────────────────┐     X-Store-Key      ┌──────────────────────────────┐
│  Warehouse_store            │ ──────────────────► │  WarehouseDB                 │
│  instance/store.db          │     /api/store/*    │  instance/warehouse.db       │
│  customer accounts          │                       │  staff, items, robots, tasks │
└─────────────────────────────┘                       └──────────────▲───────────────┘
                                                                     │ X-Scan-Key
┌─────────────────────────────┐     /api/items, tasks…              │ X-Scan-Staff
│  Warehouse_scan             │ ──────────────────────────────────┘
│  instance/scan.db           │
│  floor staff accounts       │
└─────────────────────────────┘
```

## Databases (credentials + local data)

| App | File | Credentials | Warehouse data |
|-----|------|-------------|----------------|
| **WarehouseDB** | `WarehouseDB/instance/warehouse.db` | Staff users | Items, robots, tasks (source of truth) |
| **Warehouse Store** | `Warehouse_store/instance/store.db` | Owner login (solo) | Via `WAREHOUSE_URL` + `STORE_API_KEY` |
| **Warehouse Scan** | `Warehouse_scan/instance/scan.db` | Floor staff usernames/passwords | Via `WAREHOUSE_URL` + `SCAN_API_KEY` |

## API connections (not shared SQLite)

Set these in each app’s `.env` when apps are on different machines:

**WarehouseDB** (`WarehouseDB/.env` or `instance/warehousedb.env`):

```env
STORE_API_KEY=your-store-secret
SCAN_API_KEY=your-scan-secret
```

**Store** (`Warehouse_store/.env.local`):

```env
WAREHOUSE_URL=http://192.168.1.10:8000
STORE_API_KEY=your-store-secret   # must match warehouse
```

**Scan** (`Warehouse_scan/.env`):

```env
WAREHOUSE_URL=http://192.168.1.10:8000
SCAN_API_KEY=your-scan-secret     # must match warehouse
```

## Password recovery

| App | Script |
|-----|--------|
| Warehouse staff | `WarehouseDB/scripts/debug.py users …` |
| Store customers | `Warehouse_store/scripts/debug.py users …` |
| Scan floor staff | `Warehouse_scan/scripts/debug.py users …` |

## Example deployment

| Device | App | Port (default) |
|--------|-----|----------------|
| Raspberry Pi A | WarehouseDB | 8000 |
| Raspberry Pi B | Warehouse Scan | 5002 (UI), 5003 (API) |
| VPS / Pi C | Warehouse Store | 5001 (UI), 5004 (API) |

Copy only the folder you need to each host. Point `WAREHOUSE_URL` at the warehouse machine’s LAN or public URL.
