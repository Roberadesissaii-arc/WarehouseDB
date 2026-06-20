# WarehouseDB scripts — documentation

Operator and debug tools for the **warehouse server** (`WarehouseDB/`). Use these when you need to check the database, list staff, test a password, or reset login credentials.

---

## Before you start

1. Open a terminal.
2. Go to the warehouse app folder (not the repo root):

```powershell
cd path\to\test\WarehouseDB
```

3. Use **Python 3.10+** (same as the Flask app).
4. Install app dependencies if you have not already:

```powershell
pip install -r requirements.txt
```

5. Built-in help on any command:

```powershell
python scripts/debug.py --help
python scripts/debug.py users --help
python scripts/debug.py users reset --help
```

---

## Database this folder touches

| File | Contents |
|------|----------|
| `instance/warehouse.db` | Staff logins, items, robots, tasks, settings |

These scripts **do not** change Store or Scan databases. Those apps have their own `scripts/` folders.

---

## Main tool: `debug.py`

Run everything as:

```powershell
python scripts/debug.py <command> [options]
```

### `status` — quick health check

Shows app root, database path, file size, whether first-time setup is still needed, and how many staff accounts exist.

```powershell
python scripts/debug.py status
```

**Use when:** you want to confirm which `warehouse.db` file is in use.

---

### `env` — loaded configuration (secrets masked)

Prints `SECRET_KEY`, `STORE_API_KEY`, `SCAN_API_KEY`, `SCAN_PUBLIC_URL`, and `DATABASE`. Secrets show only a short prefix.

```powershell
python scripts/debug.py env
```

**Use when:** debugging deploy env files (`.env` or `instance/warehousedb.env`).

---

### `db` — table row counts

Lists SQLite tables and how many rows each has (`users`, `items`, `robots`, `tasks`, etc.).

```powershell
python scripts/debug.py db
```

---

### `counts` — floor snapshot

Summary of inventory and work on the floor: item count, robot count, tasks by status.

```powershell
python scripts/debug.py counts
```

---

### `users` — staff account tools

Examples below use `admin` as a sample username. After first sign-in, run `users list` and substitute your real username.

#### List all staff usernames

```powershell
python scripts/debug.py users list
```

#### Show one account (no password shown)

```powershell
python scripts/debug.py users show admin
```

#### Test username + password (does not change anything)

```powershell
python scripts/debug.py users verify admin -p "your-password"
```

If you omit `-p`, the terminal will prompt you (password is hidden).

```powershell
python scripts/debug.py users verify admin
```

#### Reset password

```powershell
python scripts/debug.py users reset admin -p "NewPass123"
```

Prompted (no password on command line):

```powershell
python scripts/debug.py users reset admin
```

Create the first account on an empty database:

```powershell
python scripts/debug.py users reset admin -p "NewPass123" --create-if-missing
```

**Password rules:** at least 8 characters, at least one letter and one number.

**First sign-in:** there is no preset username or password. The web login page creates the one warehouse account when the database is empty. Use `users list` to see which username exists after setup.

---

## Other scripts

### `reset_staff_password.py`

Shortcut for password reset (same as `debug.py users reset`).

```powershell
python scripts/reset_staff_password.py --list
python scripts/reset_staff_password.py --username admin --password "NewPass123"
```

### `verify.py`

Full pre-deploy check for the whole monorepo (Python syntax, tests, icons, Arduino folders). Run from `WarehouseDB/`:

```powershell
python scripts/verify.py
```

### `verify_env_keys.py`

Checks that WarehouseDB, Store, and Scan `.env` files load and that shared API keys match. Run from repo root or `WarehouseDB/`:

```powershell
python scripts/verify_env_keys.py
```

### `generate_icons.py`

Regenerates PWA icons for warehouse, scan, and store apps.

```powershell
pip install Pillow
python scripts/generate_icons.py
```

### `open-firewall.ps1`

Windows only — allows inbound TCP port **8000** for robots on your LAN. Run **PowerShell as Administrator**:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\open-firewall.ps1
```

---

## Common tasks

| I want to… | Command |
|------------|---------|
| See if warehouse DB exists | `python scripts/debug.py status` |
| List staff usernames | `python scripts/debug.py users list` |
| Check if a password works | `python scripts/debug.py users verify admin -p "…"` |
| Reset staff password | `python scripts/debug.py users reset <username> -p "…"` |
| See how many tasks are queued | `python scripts/debug.py counts` |
| Check API keys before deploy | `python scripts/verify_env_keys.py` |
| Full release checklist | `python scripts/verify.py` |

---

## Flask CLI alternative

From `WarehouseDB/` with Flask app context:

```powershell
flask reset-staff-password --username admin
```

---

## Related documentation

- Scan floor staff (separate database): `Warehouse_scan/scripts/DOCUMENTATION.md`
- Store customers (separate database): `Warehouse_store/scripts/DOCUMENTATION.md`
- Three-app layout: `ARCHITECTURE.md` in `WarehouseDB/`
