"""In-app alerts for task and fleet activity."""
from ..database import get_db


def _row_to_dict(row):
    return {
        "id": row["id"],
        "kind": row["kind"],
        "title": row["title"],
        "body": row["body"],
        "href": row["href"],
        "read": row["read_at"] is not None,
        "read_at": row["read_at"],
        "created_at": row["created_at"],
    }


def create(kind, title, body=None, href=None):
    db = get_db()
    cur = db.execute(
        "INSERT INTO notifications(kind, title, body, href) VALUES(?,?,?,?)",
        (kind, title, body or None, href or None),
    )
    db.commit()
    return cur.lastrowid


def list_recent(limit=40):
    rows = get_db().execute(
        "SELECT * FROM notifications ORDER BY read_at IS NOT NULL, created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def unread_count():
    row = get_db().execute(
        "SELECT COUNT(*) c FROM notifications WHERE read_at IS NULL"
    ).fetchone()
    return row["c"] if row else 0


def mark_read(notification_id):
    db = get_db()
    db.execute(
        "UPDATE notifications SET read_at=datetime('now') WHERE id=? AND read_at IS NULL",
        (notification_id,),
    )
    db.commit()
    return db.total_changes > 0


def mark_all_read():
    db = get_db()
    db.execute("UPDATE notifications SET read_at=datetime('now') WHERE read_at IS NULL")
    db.commit()
    return db.total_changes


def clear_all():
    db = get_db()
    db.execute("DELETE FROM notifications")
    db.commit()
    return db.total_changes


def snapshot():
    """Lightweight state for live push / polling."""
    db = get_db()
    latest = db.execute("SELECT MAX(id) AS id FROM notifications").fetchone()
    unread = db.execute(
        "SELECT COUNT(*) AS c FROM notifications WHERE read_at IS NULL"
    ).fetchone()
    return {
        "latest_id": latest["id"] or 0,
        "unread": unread["c"] if unread else 0,
    }


def list_since(since_id=0, limit=20):
    rows = get_db().execute(
        "SELECT * FROM notifications WHERE id > ? ORDER BY id DESC LIMIT ?",
        (since_id, limit),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]
