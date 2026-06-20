"""Task (work-order) data access. A task tells a robot what to do and where."""
from ..database import get_db

# Resolve a task to readable robot / section / item names.
_TASK_SQL = """
SELECT tasks.id, tasks.action, tasks.status, tasks.note, tasks.quantity,
       tasks.staff_username, tasks.created_at, tasks.updated_at,
       tasks.robot_id, robots.name AS robot_name,
       tasks.section_id, sections.name AS section_name,
       tasks.item_id, items.name AS item_name, items.sku AS item_sku
FROM tasks
JOIN robots        ON tasks.robot_id   = robots.id
LEFT JOIN sections ON tasks.section_id = sections.id
LEFT JOIN items    ON tasks.item_id    = items.id
"""


def _parse_quantity(raw):
    if raw is None or raw == "":
        return 1
    qty = int(raw)
    if qty < 1:
        raise ValueError("Quantity must be at least 1")
    return qty


def _to_dict(row):
    from ..store_orders import parse_store_order_ref

    note = row["note"]
    return {
        "id": row["id"],
        "action": row["action"],
        "status": row["status"],
        "note": note,
        "quantity": row["quantity"] if row["quantity"] is not None else 1,
        "staff_username": row["staff_username"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "robot_id": row["robot_id"],
        "robot": row["robot_name"],
        "section_id": row["section_id"],
        "section": row["section_name"] or "—",
        "item_id": row["item_id"],
        "item": row["item_name"],
        "item_sku": row["item_sku"],
        "store_order_ref": parse_store_order_ref(note),
    }


def list_tasks_for_store_order(order_ref):
    if not order_ref:
        return []
    pattern = f"%Store:{order_ref}%"
    sql = _TASK_SQL + " WHERE tasks.note LIKE ? ORDER BY tasks.created_at ASC, tasks.id ASC"
    return [_to_dict(r) for r in get_db().execute(sql, (pattern,)).fetchall()]


def list_tasks(robot_id=None, status=None):
    sql, params, clauses = _TASK_SQL, [], []
    if robot_id:
        clauses.append("tasks.robot_id = ?")
        params.append(robot_id)
    if status:
        clauses.append("tasks.status = ?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY tasks.created_at DESC, tasks.id DESC"
    return [_to_dict(r) for r in get_db().execute(sql, params)]


def get_task(task_id):
    row = get_db().execute(_TASK_SQL + " WHERE tasks.id = ?", (task_id,)).fetchone()
    return _to_dict(row) if row else None


def set_task_status(task_id, status):
    """Update only the status column. Returns (before, after) or (None, None)."""
    if status not in ("queued", "in_progress", "done", "cancelled"):
        raise ValueError(f"Invalid status: {status}")
    before = get_task(task_id)
    if not before or before["status"] == status:
        return before, before
    db = get_db()
    db.execute(
        "UPDATE tasks SET status=?, updated_at=datetime('now') WHERE id=?",
        (status, task_id),
    )
    db.commit()
    return before, get_task(task_id)


def set_staff_username(task_id, staff_username):
    """Record which staff member accepted or completed a task on the floor."""
    name = (staff_username or "").strip() or None
    if not name:
        return get_task(task_id)
    db = get_db()
    db.execute(
        "UPDATE tasks SET staff_username=?, updated_at=datetime('now') WHERE id=?",
        (name, task_id),
    )
    db.commit()
    return get_task(task_id)


def sync_robot_tasks(robot_id, robot_status):
    """Keep open tasks aligned with live robot status (working → in progress, idle → done)."""
    db = get_db()
    queued = db.execute(
        "SELECT id FROM tasks WHERE robot_id=? AND status='queued' "
        "ORDER BY created_at ASC, id ASC",
        (robot_id,),
    ).fetchall()
    in_prog = db.execute(
        "SELECT id FROM tasks WHERE robot_id=? AND status='in_progress' "
        "ORDER BY created_at ASC, id ASC",
        (robot_id,),
    ).fetchall()

    changed = []
    if robot_status in ("working", "returning"):
        if not in_prog and queued:
            before, after = set_task_status(queued[0]["id"], "in_progress")
            if before and after and before["status"] != after["status"]:
                changed.append((before, after))
    elif robot_status in ("idle", "charging"):
        if not queued and in_prog:
            for row in in_prog:
                before, after = set_task_status(row["id"], "done")
                if before and after and before["status"] != after["status"]:
                    changed.append((before, after))
    return changed


def emit_status_notifications(changed):
    """Fire alert feed entries for automatic status transitions."""
    from . import notification

    for before, after in changed or []:
        if not before or not after or before["status"] == after["status"]:
            continue
        robot_name = after.get("robot") or "Robot"
        action = (after.get("action") or "task").upper()
        target = after.get("item") or after.get("section") or "warehouse"
        href = f"/tasks/{after['id']}"
        if after["status"] == "in_progress":
            notification.create("task", f"{robot_name} started {action}", target, href)
        elif after["status"] == "done":
            notification.create("task", f"{robot_name} finished {action}", target, href)


def cancel_task(task_id):
    found = get_task(task_id)
    if not found:
        raise LookupError("Not found")
    if found["status"] not in ("queued", "in_progress"):
        raise ValueError("Only queued or in-progress tasks can be cancelled")
    _, updated = set_task_status(task_id, "cancelled")
    return updated


def verify_robot_code(task_id, code):
    from .robot import normalize_code
    from ..security import constant_time_equals
    row = get_db().execute(
        "SELECT robots.pairing_code FROM tasks "
        "JOIN robots ON tasks.robot_id = robots.id WHERE tasks.id=?",
        (task_id,),
    ).fetchone()
    return bool(row and constant_time_equals(row["pairing_code"], normalize_code(code)))


def create_task(robot_id, action, section_id, item_id, note, quantity=1, staff_username=None):
    db = get_db()
    qty = _parse_quantity(quantity)
    _validate_task(action, section_id, item_id, qty)
    cur = db.execute(
        "INSERT INTO tasks(robot_id, action, section_id, item_id, note, quantity, staff_username) "
        "VALUES(?,?,?,?,?,?,?)",
        (robot_id, action, section_id or None, item_id or None, note or None, qty, staff_username or None),
    )
    db.commit()
    return cur.lastrowid


def create_charge_task(robot_id):
    """Send robot home to charge — not created through the normal task form."""
    return create_task(robot_id, "charge", None, None, "Return to home bay to charge", 1)


def _section_count():
    row = get_db().execute("SELECT COUNT(*) AS n FROM sections").fetchone()
    return row["n"] if row else 0


def _validate_task(action, section_id, item_id, quantity):
    from . import item as item_model

    if action == "charge":
        return
    if action not in ("pick", "restock", "move", "inspect"):
        raise ValueError(f"Unknown action: {action}")

    it = item_model.get_item(item_id) if item_id else None

    if action == "pick":
        if not item_id or not it:
            raise ValueError("Pick requires an item")
        if quantity > (it.get("quantity") or 1):
            raise ValueError(f"Only {it.get('quantity', 1)} in stock")
        return

    if action == "move":
        if _section_count() < 2:
            raise ValueError("Move requires at least two sections in the warehouse")
        if not item_id or not it:
            raise ValueError("Move requires an item")
        if not section_id:
            raise ValueError("Move requires a destination section")
        if int(section_id) == int(it["location"]["section_id"]):
            raise ValueError("Destination must differ from the item's current section")
        if quantity > (it.get("quantity") or 1):
            raise ValueError(f"Only {it.get('quantity', 1)} in stock")
        return

    if action == "restock":
        if not item_id or not it:
            raise ValueError("Restock requires an item")
        if not section_id:
            raise ValueError("Restock requires a destination section")
        if quantity > (it.get("quantity") or 1):
            raise ValueError(f"Only {it.get('quantity', 1)} available")
        return

    if action == "inspect":
        if not section_id:
            raise ValueError("Inspect requires a section")
        return


def update_task(task_id, action, section_id, item_id, status, note, quantity=None):
    db = get_db()
    existing = get_task(task_id)
    qty = _parse_quantity(quantity if quantity is not None else (existing or {}).get("quantity", 1))
    _validate_task(action, section_id, item_id, qty)
    db.execute(
        "UPDATE tasks SET action=?, section_id=?, item_id=?, status=?, note=?, quantity=?, "
        "updated_at=datetime('now') WHERE id=?",
        (action, section_id or None, item_id or None, status, note or None, qty, task_id),
    )
    db.commit()
    return get_task(task_id)
