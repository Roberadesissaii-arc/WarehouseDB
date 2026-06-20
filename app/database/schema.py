"""Database schema, status vocabulary, and sample-data seeding."""
import click

from .connection import get_db

SCHEMA = """
CREATE TABLE IF NOT EXISTS warehouses (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sections (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    name         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shelves (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    code       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    sku        TEXT,
    shelf_id   INTEGER NOT NULL REFERENCES shelves(id) ON DELETE CASCADE,
    quantity   INTEGER NOT NULL DEFAULT 1,
    notes      TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS home_bays (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS robots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'offline',
    section_id   INTEGER REFERENCES sections(id) ON DELETE SET NULL,
    home_bay_id  INTEGER REFERENCES home_bays(id) ON DELETE SET NULL,
    pairing_code TEXT UNIQUE,
    paired_at    TEXT,
    device_id    TEXT,
    last_seen_at TEXT,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    robot_id   INTEGER NOT NULL REFERENCES robots(id) ON DELETE CASCADE,
    action     TEXT NOT NULL DEFAULT 'pick',
    section_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
    item_id    INTEGER REFERENCES items(id) ON DELETE SET NULL,
    status     TEXT NOT NULL DEFAULT 'queued',
    note       TEXT,
    quantity   INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    first_name    TEXT NOT NULL DEFAULT '',
    last_name     TEXT NOT NULL DEFAULT '',
    email         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    title      TEXT NOT NULL,
    body       TEXT,
    href       TEXT,
    read_at    TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# The vocabularies the UI and API understand.
ROBOT_STATUSES = ("working", "idle", "charging", "returning", "error", "offline")
# Status values a paired robot may report (not set manually by staff).
ROBOT_REPORTABLE_STATUSES = ("working", "idle", "charging", "returning", "error")
# No heartbeat within this window → show as offline.
ROBOT_OFFLINE_SECONDS = 10
TASK_ACTIONS = ("pick", "restock", "move", "inspect", "charge")
TASK_STATUSES = ("queued", "in_progress", "done", "cancelled")


def _migrate_home_bays(db):
    exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='home_bays'"
    ).fetchone()
    if not exists:
        db.execute("""
            CREATE TABLE home_bays (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                code       TEXT NOT NULL UNIQUE,
                name       TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        for code, name, sort_order in (
            ("HB-01", "Base 01", 1),
            ("HB-02", "Base 02", 2),
            ("HB-03", "Base 03", 3),
            ("HB-04", "Base 04", 4),
        ):
            db.execute(
                "INSERT INTO home_bays(code, name, sort_order) VALUES(?,?,?)",
                (code, name, sort_order),
            )
    cols = {row[1] for row in db.execute("PRAGMA table_info(robots)").fetchall()}
    if "home_bay_id" not in cols:
        db.execute(
            "ALTER TABLE robots ADD COLUMN home_bay_id INTEGER "
            "REFERENCES home_bays(id) ON DELETE SET NULL"
        )
        bays = db.execute("SELECT id FROM home_bays ORDER BY sort_order, id").fetchall()
        if bays:
            robots = db.execute("SELECT id FROM robots ORDER BY id").fetchall()
            for i, row in enumerate(robots):
                db.execute(
                    "UPDATE robots SET home_bay_id=? WHERE id=?",
                    (bays[i % len(bays)]["id"], row["id"]),
                )
    bays = db.execute("SELECT id FROM home_bays ORDER BY sort_order, id").fetchall()
    if bays:
        unassigned = db.execute(
            "SELECT id FROM robots WHERE home_bay_id IS NULL ORDER BY id"
        ).fetchall()
        for i, row in enumerate(unassigned):
            db.execute(
                "UPDATE robots SET home_bay_id=? WHERE id=?",
                (bays[i % len(bays)]["id"], row["id"]),
            )


def _migrate_users(db):
    cols = {row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "first_name" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN first_name TEXT NOT NULL DEFAULT ''")
    if "last_name" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN last_name TEXT NOT NULL DEFAULT ''")
    if "email" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")


def _migrate_robots(db):
    cols = {row[1] for row in db.execute("PRAGMA table_info(robots)").fetchall()}
    if "last_seen_at" not in cols:
        db.execute("ALTER TABLE robots ADD COLUMN last_seen_at TEXT")
        db.execute(
            "UPDATE robots SET last_seen_at=datetime('now') "
            "WHERE status IN ('working', 'idle', 'charging')"
        )
    cols = {row[1] for row in db.execute("PRAGMA table_info(robots)").fetchall()}
    if "pairing_code" not in cols:
        db.execute("ALTER TABLE robots ADD COLUMN pairing_code TEXT")
    if "paired_at" not in cols:
        db.execute("ALTER TABLE robots ADD COLUMN paired_at TEXT")
    if "device_id" not in cols:
        db.execute("ALTER TABLE robots ADD COLUMN device_id TEXT")
    if "home_shelf_id" not in cols:
        db.execute(
            "ALTER TABLE robots ADD COLUMN home_shelf_id INTEGER "
            "REFERENCES shelves(id) ON DELETE SET NULL"
        )
        db.execute(
            "UPDATE robots SET home_shelf_id = ("
            "  SELECT id FROM shelves WHERE section_id = robots.section_id "
            "  ORDER BY code LIMIT 1"
            ") WHERE section_id IS NOT NULL"
        )
    rows = db.execute("SELECT id FROM robots WHERE pairing_code IS NULL").fetchall()
    for row in rows:
        code = f"{100000 + row['id']:06d}"
        while db.execute("SELECT 1 FROM robots WHERE pairing_code=?", (code,)).fetchone():
            code = f"{int(code) + 1:06d}"
        db.execute("UPDATE robots SET pairing_code=? WHERE id=?", (code, row["id"]))
    db.execute(
        "UPDATE robots SET paired_at=datetime('now') "
        "WHERE paired_at IS NULL AND last_seen_at IS NOT NULL"
    )
    cols = {row[1] for row in db.execute("PRAGMA table_info(robots)").fetchall()}
    if "offline_alerted" not in cols:
        db.execute(
            "ALTER TABLE robots ADD COLUMN offline_alerted INTEGER NOT NULL DEFAULT 0"
        )
    cols = {row[1] for row in db.execute("PRAGMA table_info(robots)").fetchall()}
    if "battery_pct" not in cols:
        db.execute("ALTER TABLE robots ADD COLUMN battery_pct INTEGER")
    cols = {row[1] for row in db.execute("PRAGMA table_info(robots)").fetchall()}
    if "unit_image" not in cols:
        db.execute("ALTER TABLE robots ADD COLUMN unit_image INTEGER")
        robots = db.execute("SELECT id FROM robots ORDER BY id").fetchall()
        for i, row in enumerate(robots):
            db.execute(
                "UPDATE robots SET unit_image=? WHERE id=?",
                ((i % 10) + 1, row["id"]),
            )
    else:
        db.execute(
            "UPDATE robots SET unit_image = ((unit_image - 1) % 10) + 1 "
            "WHERE unit_image IS NOT NULL AND unit_image > 10"
        )
    cols = {row[1] for row in db.execute("PRAGMA table_info(robots)").fetchall()}
    if "firmware_version" not in cols:
        db.execute("ALTER TABLE robots ADD COLUMN firmware_version TEXT")


def _migrate_tasks(db):
    cols = {row[1] for row in db.execute("PRAGMA table_info(tasks)").fetchall()}
    if "quantity" not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1")
    cols = {row[1] for row in db.execute("PRAGMA table_info(tasks)").fetchall()}
    if "staff_username" not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN staff_username TEXT")


def _migrate_items(db):
    cols = {row[1] for row in db.execute("PRAGMA table_info(items)").fetchall()}
    if "quantity" not in cols:
        db.execute("ALTER TABLE items ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1")


def _migrate_notifications(db):
    exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
    ).fetchone()
    if not exists:
        db.execute("""
            CREATE TABLE notifications (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                kind       TEXT NOT NULL,
                title      TEXT NOT NULL,
                body       TEXT,
                href       TEXT,
                read_at    TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def _migrate_store_pending(db):
    exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='store_pending_lines'"
    ).fetchone()
    if not exists:
        db.execute("""
            CREATE TABLE store_pending_lines (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id      TEXT,
                order_ref     TEXT NOT NULL,
                customer_name TEXT,
                item_id       INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                quantity      INTEGER NOT NULL DEFAULT 1,
                section_id    INTEGER NOT NULL,
                note          TEXT,
                priority      TEXT NOT NULL DEFAULT 'standard',
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def init_schema():
    db = get_db()
    db.executescript(SCHEMA)
    _migrate_home_bays(db)
    _migrate_users(db)
    _migrate_robots(db)
    _migrate_tasks(db)
    _migrate_items(db)
    _migrate_notifications(db)
    _migrate_store_pending(db)
    db.commit()


@click.command("init-db")
def init_db_command():
    """Create database tables (run with: flask init-db)."""
    init_schema()
    click.echo("Initialized the database.")
