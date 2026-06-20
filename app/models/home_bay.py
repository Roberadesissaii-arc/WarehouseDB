"""Dedicated robot dock bays inside the home warehouse (not inventory shelves)."""
from ..database import get_db
from . import setting

MAX_NAME_LEN = 120
MAX_BAYS = 32

DEFAULT_BAYS = (
    ("HB-01", "Base 01", 1),
    ("HB-02", "Base 02", 2),
    ("HB-03", "Base 03", 3),
    ("HB-04", "Base 04", 4),
)


def get_home_warehouse_name():
    setting.ensure_defaults()
    name = (setting.get("home_warehouse_name") or "").strip()
    return name or "Robot Home"


def set_home_warehouse_name(name):
    name = (name or "").strip()[:MAX_NAME_LEN] or "Robot Home"
    setting.set("home_warehouse_name", name)
    return name


def _bay_label(warehouse_name, bay_name):
    return f"{warehouse_name} / {bay_name}"


def _decorate(row, warehouse_name=None):
    wh = warehouse_name or get_home_warehouse_name()
    bay = dict(row)
    bay["warehouse_name"] = wh
    bay["label"] = _bay_label(wh, bay["name"])
    return bay


def ensure_defaults(db=None):
    """Create the four standard dock bays if the table is empty."""
    db = db or get_db()
    setting.ensure_defaults()
    count = db.execute("SELECT COUNT(*) AS n FROM home_bays").fetchone()["n"]
    if count:
        return
    for code, name, sort_order in DEFAULT_BAYS:
        db.execute(
            "INSERT INTO home_bays(code, name, sort_order) VALUES(?,?,?)",
            (code, name, sort_order),
        )
    db.commit()


def fetch_home_bays():
    ensure_defaults()
    wh = get_home_warehouse_name()
    rows = get_db().execute(
        "SELECT id, code, name, sort_order FROM home_bays ORDER BY sort_order, id"
    ).fetchall()
    return [_decorate(r, wh) for r in rows]


def fetch_payload():
    ensure_defaults()
    wh = get_home_warehouse_name()
    bays = fetch_home_bays()
    return {"warehouse_name": wh, "bays": bays}


def get_home_bay(bay_id):
    row = get_db().execute(
        "SELECT id, code, name, sort_order FROM home_bays WHERE id=?", (bay_id,)
    ).fetchone()
    return _decorate(row) if row else None


def _next_code(db):
    rows = db.execute("SELECT code FROM home_bays").fetchall()
    max_n = 0
    for row in rows:
        code = row["code"] or ""
        if code.startswith("HB-"):
            try:
                max_n = max(max_n, int(code[3:]))
            except ValueError:
                pass
    return f"HB-{max_n + 1:02d}"


def create_home_bay(name):
    name = (name or "").strip()[:MAX_NAME_LEN]
    if not name:
        raise ValueError("Base name is required")
    db = get_db()
    ensure_defaults(db)
    count = db.execute("SELECT COUNT(*) AS n FROM home_bays").fetchone()["n"]
    if count >= MAX_BAYS:
        raise ValueError(f"Maximum of {MAX_BAYS} home bases allowed")
    dup = db.execute("SELECT 1 FROM home_bays WHERE lower(name)=lower(?)", (name,)).fetchone()
    if dup:
        raise ValueError("A base with that name already exists")
    code = _next_code(db)
    sort_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM home_bays"
    ).fetchone()["n"]
    cur = db.execute(
        "INSERT INTO home_bays(code, name, sort_order) VALUES(?,?,?)",
        (code, name, sort_order),
    )
    db.commit()
    return get_home_bay(cur.lastrowid)


def delete_home_bay(bay_id):
    db = get_db()
    row = db.execute("SELECT id FROM home_bays WHERE id=?", (bay_id,)).fetchone()
    if not row:
        raise LookupError("Home base not found")
    count = db.execute("SELECT COUNT(*) AS n FROM home_bays").fetchone()["n"]
    if count <= 1:
        raise ValueError("At least one home base must remain")
    in_use = db.execute(
        "SELECT 1 FROM robots WHERE home_bay_id=? LIMIT 1", (bay_id,)
    ).fetchone()
    if in_use:
        raise ValueError("Cannot delete — a robot is assigned to this base")
    db.execute("DELETE FROM home_bays WHERE id=?", (bay_id,))
    db.commit()
    return True


def pick_default_home_bay(exclude_robot_id=None):
    """First open dock, or the least-used if all are taken."""
    db = get_db()
    ensure_defaults(db)
    bays = fetch_home_bays()
    if not bays:
        return None
    rid = exclude_robot_id or -1
    for bay in bays:
        taken = db.execute(
            "SELECT 1 FROM robots WHERE home_bay_id=? AND id!=?", (bay["id"], rid)
        ).fetchone()
        if not taken:
            return bay["id"]
    counts = []
    for bay in bays:
        n = db.execute(
            "SELECT COUNT(*) AS n FROM robots WHERE home_bay_id=? AND id!=?",
            (bay["id"], rid),
        ).fetchone()["n"]
        counts.append((n, bay["id"]))
    counts.sort()
    return counts[0][1]


def resolve_home_bay_id(home_bay_id=None, home_bay_name=None, robot_id=None):
    """Pick an existing bay, create a custom one, or auto-assign."""
    if home_bay_name:
        name = (home_bay_name or "").strip()
        if name:
            db = get_db()
            ensure_defaults(db)
            row = db.execute(
                "SELECT id FROM home_bays WHERE lower(name)=lower(?)", (name,)
            ).fetchone()
            if row:
                return row["id"]
            return create_home_bay(name)["id"]
    if home_bay_id:
        if not get_home_bay(home_bay_id):
            raise ValueError("Unknown home base")
        return home_bay_id
    return pick_default_home_bay(exclude_robot_id=robot_id)
