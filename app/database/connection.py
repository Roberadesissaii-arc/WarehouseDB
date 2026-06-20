"""Request-scoped SQLite connection lifecycle."""
import sqlite3

from flask import current_app, g


def get_db():
    """Return a SQLite connection bound to the current request/app context."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
        # Wait (instead of erroring) when another thread holds the write lock —
        # important under multi-threaded waitress with robots/store/scan writing.
        g.db.execute("PRAGMA busy_timeout = 5000")
    return g.db


def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    """Wire connection teardown and the `flask init-db` CLI command."""
    app.teardown_appcontext(close_db)

    from .schema import init_db_command  # local import avoids a circular import
    from ..models.user import reset_staff_password_command

    app.cli.add_command(init_db_command)
    app.cli.add_command(reset_staff_password_command)
