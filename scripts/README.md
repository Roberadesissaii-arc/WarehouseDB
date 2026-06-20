# WarehouseDB — scripts

Operator tools for the warehouse server.

**Full guide:** [DOCUMENTATION.md](DOCUMENTATION.md) — how to list users, verify passwords, reset logins, check the database, and run deploy scripts.

**First sign-in:** no default login. Create the one account on the web login page when the database is empty.

## Quick start

```powershell
cd WarehouseDB
python scripts/debug.py status
python scripts/debug.py users list
python scripts/debug.py users reset admin -p "NewPass123"
```

## Files

| File | Purpose |
|------|---------|
| `debug.py` | Main debug CLI (status, env, db, users, counts) |
| `DOCUMENTATION.md` | **How-to documentation** |
| `reset_staff_password.py` | Password reset shortcut |
| `verify.py` | Pre-deploy monorepo checks |
| `verify_env_keys.py` | API key consistency across apps |
| `generate_icons.py` | PWA icon generator |
| `open-firewall.ps1` | Windows firewall (port 8000) |

Also see: `Warehouse_scan/scripts/`, `Warehouse_store/scripts/`.
