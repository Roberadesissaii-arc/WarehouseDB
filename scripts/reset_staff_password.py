#!/usr/bin/env python3
"""Reset WarehouseDB staff login (instance/warehouse.db). Store and Scan are not affected."""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

WH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WH))

from app import create_app
from app.models import user


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset WarehouseDB staff password")
    parser.add_argument("--username", default=user.DEFAULT_USERNAME, help="Staff username")
    parser.add_argument("--password", help="New password (prompted if omitted)")
    parser.add_argument(
        "--create-if-missing",
        action="store_true",
        help="Create or rename the sole account when the username is missing",
    )
    parser.add_argument("--list", action="store_true", help="List staff usernames and exit")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.list:
            names = user.list_usernames()
            if not names:
                print("No staff accounts in the database.")
            else:
                print("Staff accounts:")
                for name in names:
                    print(f"  - {name}")
            print(f"Database: {app.config['DATABASE']}")
            return 0

        password = args.password
        if not password:
            password = getpass.getpass("New password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Passwords do not match.", file=sys.stderr)
                return 1

        try:
            action = user.reset_staff_password(
                args.username,
                password,
                create_if_missing=args.create_if_missing,
            )
        except ValueError as exc:
            print(exc, file=sys.stderr)
            print("Tip: run with --list to see usernames in this database.", file=sys.stderr)
            return 1

        print(f"Staff account {action}: {args.username}")
        print(f"Database: {app.config['DATABASE']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
