#!/usr/bin/env python3
"""Pre-flight checks before production deploy or customer handoff."""
from __future__ import annotations

import compileall
import os
import subprocess
import sys
from pathlib import Path

WH = Path(__file__).resolve().parents[1]
ROOT = WH.parent
STORE = ROOT / "Warehouse_store"
SCAN = ROOT / "Warehouse_scan"


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def fail(msg: str) -> None:
    print(f"FAIL  {msg}", file=sys.stderr)
    sys.exit(1)


def check_python_compile() -> None:
    print("==> Python syntax (WarehouseDB)")
    if not compileall.compile_dir(str(WH / "app"), quiet=1):
        fail("Python compile errors in WarehouseDB/app/")
    for f in ("config.py", "run.py", "wsgi.py"):
        if not compileall.compile_file(str(WH / f), quiet=1):
            fail(f"Syntax error in {f}")
    ok("all WarehouseDB Python files compile")


def check_store_python() -> None:
    print("==> Python syntax (Warehouse Store)")
    if not STORE.is_dir():
        fail("Warehouse_store/ directory missing")
    if not compileall.compile_dir(str(STORE), quiet=1):
        fail("Python compile errors in store/")
    ok("all store Python files compile")


def check_scan_python() -> None:
    print("==> Python syntax (Warehouse Scan API)")
    scan_api = SCAN / "backend"
    if not scan_api.is_dir():
        fail("scan/backend/ directory missing")
    if not compileall.compile_dir(str(scan_api), quiet=1):
        fail("Python compile errors in scan/backend/")
    ok("all scan API Python files compile")


def check_imports() -> None:
    print("==> App imports")
    os.environ.setdefault("FLASK_ENV", "development")
    sys.path.insert(0, str(WH))
    from app import create_app  # noqa: F401

    ok("WarehouseDB create_app() imports")

    subprocess.run(
        [
            sys.executable,
            "-c",
            "from app import app; rules={r.rule for r in app.url_map.iter_rules()}; "
            "assert {'/', '/shop', '/cart', '/sign-in', '/search'} <= rules",
        ],
        cwd=str(STORE),
        check=True,
        capture_output=True,
        text=True,
    )
    ok("Warehouse Store app imports and core routes registered")


def check_static_assets() -> None:
    print("==> Static assets")
    icon_sets = (
        ("WarehouseDB", WH / "app" / "static" / "icons"),
        ("Scan", SCAN / "public" / "icons"),
        ("Store", STORE / "public" / "icons"),
    )
    for label, icons in icon_sets:
        for name in ("pwa-192.png", "pwa-512.png", "apple-touch-icon.png"):
            path = icons / name
            if not path.is_file() or path.stat().st_size < 100:
                fail(
                    f"Missing or empty {path.relative_to(ROOT)} — run: "
                    "cd WarehouseDB && python scripts/generate_icons.py"
                )
        ok(f"{label} PWA icons present")

    store_icons = STORE / "public" / "icons" / "ui"
    for name in ("empty-bag.svg", "shopping-bag.svg", "warehouse.svg"):
        path = store_icons / name
        if not path.is_file():
            fail(f"Missing store icon {path.relative_to(ROOT)}")
    ok("store UI icons present")


def check_arduino_config() -> None:
    print("==> Arduino config")
    robot_dirs = [
        p for p in (WH / "Arduino").iterdir()
        if p.is_dir() and p.name.startswith("WarehouseDB_") and list(p.glob("*.ino"))
    ]
    if len(robot_dirs) < 2:
        fail(f"expected at least 2 Arduino robot folders, found {len(robot_dirs)}")
    for folder in robot_dirs:
        cfg = folder / "config.h"
        if not cfg.is_file():
            fail(f"{folder.name} missing config.h")
    ok("two robot folders, each with config.h")


def check_js_syntax() -> None:
    print("==> JavaScript syntax")
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  skip  node not installed")
        return

    js_files = list((WH / "app" / "static" / "js").rglob("*.js"))
    js_files += list((STORE / "static" / "js").rglob("*.js"))
    for path in js_files:
        subprocess.run(["node", "--check", str(path)], check=True, capture_output=True)
    ok(f"{len(js_files)} JS files pass syntax check")


def check_tests() -> None:
    print("==> Smoke tests")
    env = os.environ.copy()
    env.setdefault("FLASK_ENV", "development")
    subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=str(WH),
        check=True,
        env=env,
    )
    ok("WarehouseDB unittest suite passed")
    subprocess.run(
        [sys.executable, "-m", "unittest", "test_smoke", "-v"],
        cwd=str(STORE),
        check=True,
        env=env,
    )
    ok("Warehouse Store unittest suite passed")
    subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=str(SCAN / "backend"),
        check=True,
        env=env,
    )
    ok("Warehouse Scan unittest suite passed")


def check_production_hints() -> None:
    print("==> Production reminders")
    if os.environ.get("FLASK_ENV", "development").lower() != "production":
        print("  note  set FLASK_ENV=production for deploy")
    if not (WH / "LICENSE").is_file():
        fail("LICENSE missing")
    if not (WH / "docker-compose.yml").is_file():
        fail("docker-compose.yml missing")
    if not (WH / ".env.example").is_file():
        fail(".env.example missing for WarehouseDB")
    if not (STORE / ".env.example").is_file() and not (STORE / ".env.local.example").is_file():
        fail("Warehouse_store/.env.example missing")
    if not (SCAN / ".env.example").is_file():
        fail("Warehouse_scan/.env.example missing")
    if os.environ.get("SECRET_KEY") is None:
        print("  note  set SECRET_KEY in production (warehouse)")
    if os.environ.get("STORE_SECRET_KEY") is None:
        print("  note  set STORE_SECRET_KEY in production (store)")
    if os.environ.get("STORE_API_KEY") is None:
        print("  note  set STORE_API_KEY to match warehouse store key")
    if os.environ.get("SCAN_SECRET_KEY") is None:
        print("  note  set SCAN_SECRET_KEY in production (scan app)")
    ok("reviewed deploy env hints")


def main() -> None:
    print(f"WarehouseDB verify — {ROOT}\n")
    check_python_compile()
    check_store_python()
    check_scan_python()
    check_imports()
    check_static_assets()
    check_arduino_config()
    check_js_syntax()
    check_tests()
    check_production_hints()
    print("\nAll checks passed. WarehouseDB, Store, and Scan are ready for deploy.")


if __name__ == "__main__":
    main()
