#!/usr/bin/env python3
"""Verify warehouse / scan / store .env files load and API keys match."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WH = Path(__file__).resolve().parents[1]
ROOT = WH.parent
SCAN = ROOT / "Warehouse_scan"
STORE = ROOT / "Warehouse_store"

SNIPPET = """
import sys
from pathlib import Path
role = sys.argv[1]
root = Path({root!r})
wh = root / "WarehouseDB"
scan = root / "Warehouse_scan"
store = root / "Warehouse_store"
if role == "warehouse":
    sys.path.insert(0, str(wh))
    import config
    c = config.get_config()()
    print(c.STORE_API_KEY)
    print(c.SCAN_API_KEY)
    print(c.SECRET_KEY)
elif role == "scan":
    sys.path.insert(0, str(scan / "backend"))
    from config import Config
    print(Config.SCAN_API_KEY)
    print(Config.SECRET_KEY)
    print(Config.WAREHOUSE_URL)
else:
    sys.path.insert(0, str(store / "backend"))
    from config import Config
    print(Config.STORE_API_KEY)
    print(Config.SECRET_KEY)
    print(Config.WAREHOUSE_URL)
""".format(root=str(ROOT))


def load(role: str) -> list[str]:
    out = subprocess.check_output(
        [sys.executable, "-c", SNIPPET, role],
        text=True,
    )
    return [line.strip() for line in out.strip().splitlines()]


def main() -> int:
    wh = load("warehouse")
    sc = load("scan")
    st = load("store")

    print("=== Keys loaded (prefix only) ===")
    print(f"Warehouse STORE_API_KEY: {wh[0][:16]}...")
    print(f"Warehouse SCAN_API_KEY:  {wh[1][:16]}...")
    print(f"Warehouse SECRET_KEY:    {wh[2][:16]}...")
    print(f"Store     STORE_API_KEY: {st[0][:16]}...")
    print(f"Store     SECRET_KEY:    {st[1][:16]}...")
    print(f"Scan      SCAN_API_KEY:  {sc[0][:16]}...")
    print(f"Scan      SECRET_KEY:    {sc[1][:16]}...")

    errors: list[str] = []
    if wh[0] != st[0]:
        errors.append("STORE_API_KEY does not match (WarehouseDB/.env vs Warehouse_store/.env.local)")
    if wh[1] != sc[0]:
        errors.append("SCAN_API_KEY does not match (WarehouseDB/.env vs Warehouse_scan/.env)")
    if wh[2] in (sc[1], st[1]):
        errors.append("Warehouse SECRET_KEY must stay separate from store/scan session secrets")
    if sc[1] == st[1]:
        errors.append("Scan and store session secrets must be different")
    for label, val in [("warehouse", wh[2]), ("scan", sc[1]), ("store", st[1])]:
        if len(val) < 32:
            errors.append(f"{label} secret is too short")

    if errors:
        print("\nFAIL")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\nOK — all three apps load env files; shared API keys match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
