# WarehouseDB

Staff warehouse board — inventory, fleet, tasks, map, and settings. Port **8000**.

Also ships robot firmware (`Arduino/`), Docker deploy, sample import data (`json/`), and ecosystem install scripts.

| Related app | Folder | Port |
|-------------|--------|------|
| **Store** | `../Warehouse_store` | 5001 (UI), 5004 (API) |
| **Scan** | `../Warehouse_scan` | 5002 (UI), 5003 (API) |

License: [MIT](LICENSE) · Third-party: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) · Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

## Quick start

```powershell
cd WarehouseDB
pip install -r requirements.txt
python run.py
```

Open http://localhost:8000 — on **first visit**, create the one warehouse account on the login page (username and password of your choice; 8+ characters with a letter and a number). Change credentials later under **Settings → Account**.

Install all three apps:

```bash
./install.sh
```

## Docker

```bash
cd WarehouseDB
cp .env.example .env
docker compose up --build -d
```

See [deploy/README.md](deploy/README.md).

## Configuration

Copy [.env.example](.env.example) to `.env`. Store and Scan have their own env files in sibling folders.

## Scripts

```powershell
python scripts/debug.py status
python scripts/verify.py
```

Full guide: [scripts/DOCUMENTATION.md](scripts/DOCUMENTATION.md)

## Robots

Flash firmware from `Arduino/WarehouseDB_<unitId>/` — see [Arduino/README.md](Arduino/README.md).
