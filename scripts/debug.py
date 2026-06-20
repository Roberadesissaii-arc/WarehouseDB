#!/usr/bin/env python3
"""WarehouseDB operator/debug CLI — users, database, env, inventory counts."""
from __future__ import annotations

import argparse
import getpass
import os
import sqlite3
import sys
from pathlib import Path

WH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WH))

from app import create_app  # noqa: E402
from app.models import user  # noqa: E402


def _mask(value: str | None, show: int = 12) -> str:
    if not value:
        return "(not set)"
    if len(value) <= show:
        return value
    return f"{value[:show]}… ({len(value)} chars)"


def _db_path(app) -> Path:
    return Path(app.config["DATABASE"])


def _db_size(path: Path) -> str:
    if not path.is_file():
        return "missing"
    kb = path.stat().st_size / 1024
    return f"{kb:.1f} KB"


def _table_counts(db_path: Path, tables: list[str]) -> list[tuple[str, int | str]]:
    if not db_path.is_file():
        return [(t, "—") for t in tables]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    out: list[tuple[str, int | str]] = []
    for name in tables:
        try:
            n = conn.execute(f"SELECT COUNT(*) c FROM {name}").fetchone()["c"]
            out.append((name, int(n)))
        except sqlite3.Error:
            out.append((name, "missing"))
    conn.close()
    return out


def cmd_status(app) -> int:
    cfg = app.config
    db = _db_path(app)
    print("=== WarehouseDB status ===")
    print(f"App root:     {WH}")
    print(f"FLASK_ENV:    {os.environ.get('FLASK_ENV', 'development')}")
    print(f"Host:port:    {cfg.get('HOST')}:{cfg.get('PORT')}")
    print(f"Database:     {db}")
    print(f"DB size:      {_db_size(db)}")
    print(f"Setup needed: {user.needs_setup()}")
    print(f"Staff count:  {len(user.list_usernames())}")
    return 0


def cmd_env(app) -> int:
    cfg = app.config
    print("=== WarehouseDB environment ===")
    print(f"SECRET_KEY:      {_mask(cfg.get('SECRET_KEY'))}")
    print(f"STORE_API_KEY:   {_mask(cfg.get('STORE_API_KEY'))}")
    print(f"SCAN_API_KEY:    {_mask(cfg.get('SCAN_API_KEY'))}")
    print(f"SCAN_PUBLIC_URL: {cfg.get('SCAN_PUBLIC_URL')}")
    print(f"DATABASE:        {cfg.get('DATABASE')}")
    return 0


def cmd_db(app) -> int:
    db = _db_path(app)
    tables = [
        "users",
        "warehouses",
        "sections",
        "shelves",
        "items",
        "robots",
        "tasks",
        "notifications",
        "settings",
    ]
    print(f"=== Database: {db} ===")
    print(f"Size: {_db_size(db)}")
    print("Table rows:")
    for name, count in _table_counts(db, tables):
        print(f"  {name:16} {count}")
    return 0


def cmd_counts(app) -> int:
    db = _db_path(app)
    if not db.is_file():
        print(f"Database not found: {db}", file=sys.stderr)
        return 1
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    print("=== Floor snapshot ===")
    for label, sql in (
        ("Items", "SELECT COUNT(*) c FROM items"),
        ("Robots", "SELECT COUNT(*) c FROM robots"),
        ("Tasks (all)", "SELECT COUNT(*) c FROM tasks"),
        ("Tasks queued", "SELECT COUNT(*) c FROM tasks WHERE status='queued'"),
        ("Tasks in progress", "SELECT COUNT(*) c FROM tasks WHERE status='in_progress'"),
        ("Tasks done", "SELECT COUNT(*) c FROM tasks WHERE status='done'"),
        ("Robots online", "SELECT COUNT(*) c FROM robots WHERE status<>'offline'"),
    ):
        try:
            n = conn.execute(sql).fetchone()["c"]
            print(f"  {label:20} {n}")
        except sqlite3.Error as exc:
            print(f"  {label:20} error ({exc})")
    conn.close()
    return 0


def cmd_users_list(_app) -> int:
    names = user.list_usernames()
    if not names:
        print("No staff accounts.")
        return 0
    print("Staff accounts:")
    for name in names:
        print(f"  - {name}")
    return 0


def cmd_users_show(_app, username: str) -> int:
    row = user.get_by_username(username)
    if not row:
        print(f"No user named {username!r}", file=sys.stderr)
        return 1
    print(f"id:       {row['id']}")
    print(f"username: {row['username']}")
    print(f"hash:     {_mask(row['password_hash'], 16)}")
    return 0


def cmd_users_verify(_app, username: str, password: str | None) -> int:
    if not password:
        password = getpass.getpass("Password to test: ")
    ok = user.verify(username, password)
    if ok:
        print(f"OK — password matches {username!r} (id={ok['id']})")
        return 0
    print(f"FAIL — password does not match {username!r}", file=sys.stderr)
    return 1


def cmd_users_reset(_app, username: str, password: str | None, create_if_missing: bool) -> int:
    if not password:
        password = getpass.getpass("New password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            return 1
    try:
        action = user.reset_staff_password(username, password, create_if_missing=create_if_missing)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Staff account {action}: {username}")
    print(f"Sign in at http://127.0.0.1:8000/login with username {username!r}")
    print(f"Verify: python scripts/debug.py users verify {username} -p \"<password>\"")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="WarehouseDB debug / operator tools")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="App and database summary")
    sub.add_parser("env", help="Loaded config (secrets masked)")
    sub.add_parser("db", help="SQLite file and table row counts")
    sub.add_parser("counts", help="Items, robots, tasks snapshot")

    users = sub.add_parser("users", help="Staff account tools")
    users_sub = users.add_subparsers(dest="users_cmd", required=True)

    users_sub.add_parser("list", help="List staff usernames")

    show_p = users_sub.add_parser("show", help="Show one staff account")
    show_p.add_argument("username")

    verify_p = users_sub.add_parser("verify", help="Test username/password")
    verify_p.add_argument("username")
    verify_p.add_argument("-p", "--password", help="Password (prompted if omitted)")

    reset_p = users_sub.add_parser("reset", help="Reset staff password")
    reset_p.add_argument("username")
    reset_p.add_argument("-p", "--password", help="New password (prompted if omitted)")
    reset_p.add_argument("--create-if-missing", action="store_true")

    args = parser.parse_args()
    app = create_app()

    with app.app_context():
        if args.command == "status":
            return cmd_status(app)
        if args.command == "env":
            return cmd_env(app)
        if args.command == "db":
            return cmd_db(app)
        if args.command == "counts":
            return cmd_counts(app)
        if args.command == "users":
            if args.users_cmd == "list":
                return cmd_users_list(app)
            if args.users_cmd == "show":
                return cmd_users_show(app, args.username)
            if args.users_cmd == "verify":
                return cmd_users_verify(app, args.username, args.password)
            if args.users_cmd == "reset":
                return cmd_users_reset(app, args.username, args.password, args.create_if_missing)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
