"""Import warehouse data from a JSON backup (export format)."""
import json
import secrets

from ..database import ROBOT_STATUSES, get_db
from . import robot, setting

MAX_WAREHOUSES = 64
MAX_SECTIONS = 512
MAX_SHELVES = 5000
MAX_ITEMS = 20000
MAX_ROBOTS = 500
MAX_NAME_LEN = 120
MAX_CODE_LEN = 32
MAX_SKU_LEN = 64


def _clip(text, limit):
    return (text or "").strip()[:limit]


def _parse_robot_home_bay(robot_row, bay_map):
    if robot_row.get("home_bay_id"):
        bid = int(robot_row["home_bay_id"])
        if bid in bay_map:
            return bid
    loc = (robot_row.get("location") or "").strip()
    if not loc or loc.lower() == "unassigned":
        return None
    for bay_id, bay in bay_map.items():
        if bay["name"].lower() == loc.lower() or bay["code"].lower() == loc.lower():
            return bay_id
    return None


def _unique_pairing_code(db, preferred=None):
    code = robot.normalize_code(preferred) if preferred else ""
    if len(code) == 6:
        taken = db.execute("SELECT 1 FROM robots WHERE pairing_code=?", (code,)).fetchone()
        if not taken:
            return code
    for _ in range(200):
        code = f"{secrets.randbelow(900000) + 100000:06d}"
        if not db.execute("SELECT 1 FROM robots WHERE pairing_code=?", (code,)).fetchone():
            return code
    raise ValueError("Could not allocate a unique pairing code")


def import_snapshot(raw):
    """Replace inventory + fleet from an export file. Keeps users and login."""
    if isinstance(raw, (bytes, str)):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON backup file") from exc
    elif isinstance(raw, dict):
        data = raw
    else:
        raise ValueError("Invalid backup format")

    if isinstance(data.get("products"), list) and "warehouses" not in data:
        raise ValueError(
            "This looks like a product catalog file (products only). "
            "Use Settings → Data → Import JSON to add items."
        )

    warehouses = data.get("warehouses")
    items = data.get("items")
    robots_list = data.get("robots") or []
    settings_data = data.get("settings") or {}

    if not isinstance(warehouses, list) or not isinstance(items, list):
        raise ValueError("Backup must include warehouses and items arrays")

    if len(warehouses) == 0:
        raise ValueError("Backup has no warehouses — refusing to wipe your database")

    if len(warehouses) > MAX_WAREHOUSES:
        raise ValueError(f"Too many warehouses (max {MAX_WAREHOUSES})")
    if len(items) > MAX_ITEMS:
        raise ValueError(f"Too many items (max {MAX_ITEMS})")
    if len(robots_list) > MAX_ROBOTS:
        raise ValueError(f"Too many robots (max {MAX_ROBOTS})")

    db = get_db()
    from . import home_bay, unit_image
    home_bay.ensure_defaults(db)
    bay_map = {r["id"]: dict(r) for r in db.execute("SELECT id, code, name FROM home_bays").fetchall()}
    shelf_map = {}
    section_map = {}
    sec_total = 0
    shelf_total = 0
    imported_items = 0
    imported_robots = 0

    from ..database.seed import _wipe_warehouse_graph

    try:
        _wipe_warehouse_graph(db)

        for wh in warehouses:
            wh_name = _clip(wh.get("name"), MAX_NAME_LEN)
            if not wh_name:
                raise ValueError("Warehouse name is required")
            cur = db.execute("INSERT INTO warehouses(name) VALUES(?)", (wh_name,))
            wh_id = cur.lastrowid
            for sec in wh.get("sections") or []:
                sec_total += 1
                if sec_total > MAX_SECTIONS:
                    raise ValueError(f"Too many sections (max {MAX_SECTIONS})")
                sec_name = _clip(sec.get("name"), MAX_NAME_LEN)
                if not sec_name:
                    continue
                cur = db.execute(
                    "INSERT INTO sections(warehouse_id, name) VALUES(?,?)",
                    (wh_id, sec_name),
                )
                sec_id = cur.lastrowid
                section_map[(wh_name, sec_name)] = sec_id
                for sh in sec.get("shelves") or []:
                    shelf_total += 1
                    if shelf_total > MAX_SHELVES:
                        raise ValueError(f"Too many bays (max {MAX_SHELVES})")
                    code = _clip(sh.get("code"), MAX_CODE_LEN)
                    if not code:
                        continue
                    cur = db.execute(
                        "INSERT INTO shelves(section_id, code) VALUES(?,?)",
                        (sec_id, code),
                    )
                    shelf_map[(wh_name, sec_name, code)] = cur.lastrowid

        for it in items:
            name = _clip(it.get("name"), MAX_NAME_LEN)
            if not name:
                continue
            loc = it.get("location") or {}
            key = (
                _clip(loc.get("warehouse"), MAX_NAME_LEN),
                _clip(loc.get("section"), MAX_NAME_LEN),
                _clip(loc.get("shelf"), MAX_CODE_LEN),
            )
            shelf_id = shelf_map.get(key)
            if not shelf_id:
                raise ValueError(f"Item '{name}' references unknown location")
            sku = _clip(it.get("sku"), MAX_SKU_LEN) or None
            notes = _clip(it.get("notes"), 500) or None
            qty = int(it.get("quantity") or 1)
            if qty < 1:
                qty = 1
            db.execute(
                "INSERT INTO items(name, sku, shelf_id, quantity, notes) VALUES(?,?,?,?,?)",
                (name, sku, shelf_id, qty, notes),
            )
            imported_items += 1

        for rb in robots_list:
            name = _clip(rb.get("name"), MAX_NAME_LEN)
            if not name:
                continue
            status = rb.get("reported_status") or rb.get("status") or "offline"
            if status not in ROBOT_STATUSES:
                status = "offline"
            home_bay_id = _parse_robot_home_bay(rb, bay_map) or home_bay.pick_default_home_bay()
            code = _unique_pairing_code(db, rb.get("pairing_code"))
            paired_at = rb.get("paired_at") if rb.get("paired") or rb.get("paired_at") else None
            slot = unit_image.validate(rb.get("unit_image")) if rb.get("unit_image") is not None else 1
            db.execute(
                "INSERT INTO robots(name, status, home_bay_id, pairing_code, paired_at, unit_image) "
                "VALUES(?,?,?,?,?,?)",
                (name, status, home_bay_id, code, paired_at, slot),
            )
            imported_robots += 1

        if isinstance(settings_data, dict):
            if "org_name" in settings_data:
                db.execute(
                    "INSERT INTO settings(key, value) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ("org_name", _clip(settings_data.get("org_name"), MAX_NAME_LEN)),
                )
            if "home_warehouse_name" in settings_data:
                db.execute(
                    "INSERT INTO settings(key, value) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ("home_warehouse_name", _clip(settings_data.get("home_warehouse_name"), MAX_NAME_LEN)),
                )
            if isinstance(settings_data.get("status_labels"), dict):
                db.execute(
                    "INSERT INTO settings(key, value) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ("status_labels", json.dumps(settings_data["status_labels"])),
                )
            if isinstance(settings_data.get("status_colors"), dict):
                db.execute(
                    "INSERT INTO settings(key, value) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ("status_colors", json.dumps(settings_data["status_colors"])),
                )
            sec = settings_data.get("security")
            if isinstance(sec, dict):
                setting.set_security(sec)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "warehouses": len(warehouses),
        "sections": sec_total,
        "bays": shelf_total,
        "items": imported_items,
        "robots": imported_robots,
    }
