"""Robot data access. Home location is a dedicated dock bay, not a warehouse shelf."""
import secrets
from datetime import datetime, timedelta, timezone

from ..database import ROBOT_OFFLINE_SECONDS, ROBOT_REPORTABLE_STATUSES, get_db
from . import home_bay, notification, unit_image

_ROBOT_SQL = """
SELECT robots.id, robots.name, robots.status, robots.home_bay_id,
       robots.pairing_code, robots.paired_at, robots.device_id,
       robots.last_seen_at, robots.updated_at, robots.battery_pct,
       robots.unit_image, robots.firmware_version,
       home_bays.code AS home_bay_code,
       home_bays.name AS home_bay_name
FROM robots
LEFT JOIN home_bays ON robots.home_bay_id = home_bays.id
"""


def normalize_code(raw):
    return "".join(ch for ch in str(raw or "") if ch.isdigit())


def validate_code(code):
    if len(code) != 6:
        raise ValueError("Pairing code must be 6 digits (from the robot screen)")


class PairingError(ValueError):
    """Pairing blocked — robot or device already registered."""

    def __init__(self, message, code, robot=None):
        super().__init__(message)
        self.code = code
        self.robot = robot or {}


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace(" ", "T"))
    except ValueError:
        return None


def _is_connected(last_seen_at):
    seen = _parse_ts(last_seen_at)
    if not seen:
        return False
    return _utcnow() - seen < timedelta(seconds=ROBOT_OFFLINE_SECONDS)


def effective_status(row):
    """Offline until paired and polling; otherwise the robot's reported state."""
    if not row["paired_at"]:
        return "offline"
    if not _is_connected(row["last_seen_at"]):
        return "offline"
    stored = row["status"]
    if stored in ROBOT_REPORTABLE_STATUSES:
        return stored
    return "idle"


def _to_dict(row):
    assigned = row["home_bay_id"] is not None
    status = effective_status(row)
    wh = home_bay.get_home_warehouse_name()
    if assigned:
        bay = row["home_bay_name"] or row["home_bay_code"] or "Base"
        location = f"{wh} / {bay}"
    else:
        location = "Unassigned"
    return {
        "id": row["id"],
        "name": row["name"],
        "status": status,
        "reported_status": row["status"],
        "connected": status != "offline" and bool(row["paired_at"]),
        "paired": row["paired_at"] is not None,
        "pairing_code": row["pairing_code"],
        "paired_at": row["paired_at"],
        "device_id": row["device_id"],
        "last_seen_at": row["last_seen_at"],
        "updated_at": row["updated_at"],
        "battery_pct": row["battery_pct"],
        "unit_image": row["unit_image"] or 1,
        "unit_brand": unit_image.brand_for(row["unit_image"] or 1),
        "unit_code": unit_image.code_for(row["unit_image"] or 1),
        "firmware_version": row["firmware_version"],
        "home_bay_id": row["home_bay_id"],
        "home_bay_code": row["home_bay_code"],
        "home_warehouse_name": wh,
        "location": location,
    }


def fetch_robots():
    rows = get_db().execute(_ROBOT_SQL + " ORDER BY robots.name").fetchall()
    return [_to_dict(r) for r in rows]


def process_offline_alerts():
    """Create one alert per offline episode when a paired robot stops responding."""
    db = get_db()
    rows = db.execute(
        "SELECT id, name, status, paired_at, last_seen_at, offline_alerted FROM robots"
    ).fetchall()
    changed = False
    for row in rows:
        if not row["paired_at"]:
            continue
        online = effective_status(row) != "offline"
        if online:
            if row["offline_alerted"]:
                db.execute("UPDATE robots SET offline_alerted=0 WHERE id=?", (row["id"],))
                changed = True
            continue
        if row["offline_alerted"] or not row["last_seen_at"]:
            continue
        reported = row["status"]
        if reported not in ROBOT_REPORTABLE_STATUSES:
            reported = "idle"
        notification.create(
            "fleet",
            f'{row["name"]} went offline',
            f"Was {reported} — stopped responding",
            f'/robots/{row["id"]}',
        )
        db.execute("UPDATE robots SET offline_alerted=1 WHERE id=?", (row["id"],))
        changed = True
    if changed:
        db.commit()


def get_robot(robot_id):
    row = get_db().execute(_ROBOT_SQL + " WHERE robots.id=?", (robot_id,)).fetchone()
    return _to_dict(row) if row else None


def get_by_pairing_code(code):
    code = normalize_code(code)
    row = get_db().execute(_ROBOT_SQL + " WHERE robots.pairing_code=?", (code,)).fetchone()
    return _to_dict(row) if row else None


def verify_code(robot_id, code):
    from ..security import constant_time_equals

    row = get_db().execute(
        "SELECT pairing_code FROM robots WHERE id=?", (robot_id,)
    ).fetchone()
    return bool(row and constant_time_equals(row["pairing_code"], normalize_code(code)))


def _resolve_home_bay(home_bay_id=None, home_bay_name=None, robot_id=None):
    return home_bay.resolve_home_bay_id(home_bay_id, home_bay_name, robot_id=robot_id)


def pair_robot(pairing_code, name, home_bay_id=None, home_bay_name=None, unit_image_id=None):
    """Link a warehouse record to the code shown on the robot."""
    code = normalize_code(pairing_code)
    validate_code(code)
    slot = unit_image.validate(unit_image_id)
    display_name = (name or "").strip() or unit_image.brand_for(slot)
    db = get_db()
    existing = db.execute(
        "SELECT id, name, paired_at FROM robots WHERE pairing_code=?", (code,)
    ).fetchone()
    if existing:
        if existing["paired_at"]:
            raise PairingError(
                f'This robot is already paired as "{existing["name"]}".',
                code="already_paired",
                robot={"id": existing["id"], "name": existing["name"]},
            )
        dock = _resolve_home_bay(home_bay_id, home_bay_name, robot_id=existing["id"])
        db.execute(
            "UPDATE robots SET name=?, home_bay_id=?, unit_image=?, updated_at=datetime('now') WHERE id=?",
            (display_name, dock, slot, existing["id"]),
        )
        db.commit()
        return existing["id"]
    dock = _resolve_home_bay(home_bay_id, home_bay_name)
    cur = db.execute(
        "INSERT INTO robots(name, status, home_bay_id, pairing_code, unit_image, last_seen_at) "
        "VALUES(?, 'offline', ?, ?, ?, NULL)",
        (display_name, dock, code, slot),
    )
    db.commit()
    return cur.lastrowid


def claim_robot(pairing_code, device_id=None):
    """Called by the physical robot to complete the handshake."""
    code = normalize_code(pairing_code)
    validate_code(code)
    device_id = (device_id or "").strip() or None
    db = get_db()
    row = db.execute(
        "SELECT id, name, paired_at, device_id, home_bay_id FROM robots WHERE pairing_code=?",
        (code,),
    ).fetchone()
    if not row:
        raise LookupError("Unknown pairing code — enter this code in WarehouseDB first")

    # Sub-second precision so paired_at orders correctly against a store pick's
    # created_at within the same second (drives backlog eligibility).
    now = _utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")

    if device_id:
        other = db.execute(
            "SELECT id, name, paired_at, pairing_code, home_bay_id FROM robots "
            "WHERE device_id=? AND paired_at IS NOT NULL AND id!=?",
            (device_id, row["id"]),
        ).fetchone()
        if other:
            # Same physical unit already registered — staff opened a new pending slot
            # (e.g. after firmware upload / new on-screen code). Merge into the live record.
            if not row["paired_at"]:
                pending_name = row["name"]
                pending_home = row["home_bay_id"]
                db.execute("DELETE FROM robots WHERE id=?", (row["id"],))
                dock = pending_home or other["home_bay_id"] or _resolve_home_bay(robot_id=other["id"])
                db.execute(
                    "UPDATE robots SET pairing_code=?, name=?, home_bay_id=?, "
                    "device_id=?, last_seen_at=?, updated_at=? WHERE id=?",
                    (code, pending_name, dock, device_id, now, now, other["id"]),
                )
                db.commit()
                return get_robot(other["id"])
            raise PairingError(
                f'Already paired as "{other["name"]}".',
                code="already_paired",
                robot={"id": other["id"], "name": other["name"]},
            )

    if row["paired_at"]:
        if device_id and row["device_id"] and row["device_id"] != device_id:
            raise PairingError(
                "This code is linked to another device.",
                code="code_in_use",
                robot={"id": row["id"], "name": row["name"]},
            )
        db.execute(
            "UPDATE robots SET last_seen_at=?, updated_at=? WHERE id=?",
            (now, now, row["id"]),
        )
        db.commit()
        return get_robot(row["id"])

    dock = row["home_bay_id"] or _resolve_home_bay(robot_id=row["id"])
    db.execute(
        "UPDATE robots SET paired_at=?, device_id=?, home_bay_id=?, last_seen_at=?, updated_at=? "
        "WHERE id=?",
        (now, device_id, dock, now, now, row["id"]),
    )
    db.commit()
    return get_robot(row["id"])


def pair_status(robot_id):
    row = get_db().execute(
        "SELECT id, pairing_code, paired_at, last_seen_at, status FROM robots WHERE id=?",
        (robot_id,),
    ).fetchone()
    if not row:
        return None
    return _pair_status_row(row)


def pair_status_by_code(pairing_code):
    """Poll pairing progress by the code on the robot screen (survives device merge)."""
    code = normalize_code(pairing_code)
    if len(code) != 6:
        return None
    row = get_db().execute(
        "SELECT id, pairing_code, paired_at, last_seen_at, status FROM robots WHERE pairing_code=?",
        (code,),
    ).fetchone()
    if not row:
        return {
            "robot_id": None,
            "pairing_code": code,
            "paired": False,
            "connected": False,
            "waiting": True,
        }
    return _pair_status_row(row)


def _pair_status_row(row):
    paired = row["paired_at"] is not None
    connected = paired and _is_connected(row["last_seen_at"])
    return {
        "robot_id": row["id"],
        "pairing_code": row["pairing_code"],
        "paired": paired,
        "connected": connected,
        "waiting": not paired,
    }


def cancel_pending_pairing(robot_id):
    """Remove an unpaired slot when staff cancels or pairing times out."""
    db = get_db()
    cur = db.execute(
        "DELETE FROM robots WHERE id=? AND paired_at IS NULL",
        (robot_id,),
    )
    db.commit()
    return cur.rowcount > 0


def update_robot(robot_id, name, home_bay_id=None, home_bay_name=None):
    db = get_db()
    if home_bay_name:
        dock = _resolve_home_bay(home_bay_name=home_bay_name, robot_id=robot_id)
    elif home_bay_id is not None:
        dock = _resolve_home_bay(home_bay_id=home_bay_id or None, robot_id=robot_id)
    else:
        row = db.execute("SELECT home_bay_id FROM robots WHERE id=?", (robot_id,)).fetchone()
        dock = row["home_bay_id"] if row else None
    db.execute(
        "UPDATE robots SET name=?, home_bay_id=?, updated_at=datetime('now') WHERE id=?",
        (name, dock, robot_id),
    )
    db.commit()
    row = get_db().execute(_ROBOT_SQL + " WHERE robots.id=?", (robot_id,)).fetchone()
    return _to_dict(row) if row else None


def report_status(robot_id, status, battery_pct=None, firmware_version=None):
    if status not in ROBOT_REPORTABLE_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(ROBOT_REPORTABLE_STATUSES)}")
    db = get_db()
    now = _utcnow().strftime("%Y-%m-%d %H:%M:%S")
    fw = (firmware_version or "").strip() or None
    if battery_pct is not None:
        pct = max(0, min(100, int(battery_pct)))
        if fw:
            db.execute(
                "UPDATE robots SET status=?, battery_pct=?, firmware_version=?, "
                "last_seen_at=?, updated_at=? WHERE id=? AND paired_at IS NOT NULL",
                (status, pct, fw, now, now, robot_id),
            )
        else:
            db.execute(
                "UPDATE robots SET status=?, battery_pct=?, last_seen_at=?, updated_at=? "
                "WHERE id=? AND paired_at IS NOT NULL",
                (status, pct, now, now, robot_id),
            )
    elif fw:
        db.execute(
            "UPDATE robots SET status=?, firmware_version=?, last_seen_at=?, updated_at=? "
            "WHERE id=? AND paired_at IS NOT NULL",
            (status, fw, now, now, robot_id),
        )
    else:
        db.execute(
            "UPDATE robots SET status=?, last_seen_at=?, updated_at=? WHERE id=? AND paired_at IS NOT NULL",
            (status, now, now, robot_id),
        )
    db.commit()
    if db.total_changes == 0:
        raise LookupError("Not found or not paired")
    return get_robot(robot_id)


def touch_robot(robot_id):
    """Record a poll from the robot without changing its reported status."""
    db = get_db()
    now = _utcnow().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE robots SET last_seen_at=?, updated_at=? WHERE id=? AND paired_at IS NOT NULL",
        (now, now, robot_id),
    )
    db.commit()
    if db.total_changes == 0:
        raise LookupError("Not found or not paired")


def seed_pairing_code(index):
    """Deterministic 6-digit code for sample robots."""
    return f"{100000 + index:06d}"
