"""Store order lines waiting for a robot to become available."""
from datetime import datetime, timezone

from ..database import get_db
from ..models import item, setting, task
from ..store_notifications import notify_robot_assigned
from ..store_orders import build_store_note, pick_robot_for_store, robot_eligible_for_backlog


def enqueue(order_id, order_ref, customer_name, item_row, quantity, section_id, note, priority="standard"):
    db = get_db()
    cur = db.execute(
        "INSERT INTO store_pending_lines"
        "(order_id, order_ref, customer_name, item_id, quantity, section_id, note, priority, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (
            order_id,
            order_ref,
            customer_name,
            item_row["id"],
            quantity,
            section_id,
            note,
            priority,
            # Microsecond precision so created_at orders correctly against a
            # robot's paired_at within the same second (backlog eligibility).
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"),
        ),
    )
    db.commit()
    return cur.lastrowid


def pending_count():
    row = get_db().execute("SELECT COUNT(*) AS n FROM store_pending_lines").fetchone()
    return row["n"] if row else 0


def pending_count_for_order(order_ref):
    row = get_db().execute(
        "SELECT COUNT(*) AS n FROM store_pending_lines WHERE order_ref=?",
        (order_ref,),
    ).fetchone()
    return row["n"] if row else 0


def dispatch_all(robots, tasks, *, assign_backlog_on_pair=None):
    """Assign queued store lines to robots when a paired unit is available."""
    if assign_backlog_on_pair is None:
        assign_backlog_on_pair = setting.assign_backlog_on_pair()
    db = get_db()
    rows = db.execute(
        "SELECT * FROM store_pending_lines ORDER BY created_at ASC, id ASC"
    ).fetchall()
    if not rows:
        return []

    created = []
    reserved = []
    work_tasks = list(tasks)
    removed = []

    for row in rows:
        it = item.get_item(row["item_id"])
        if not it:
            db.execute("DELETE FROM store_pending_lines WHERE id=?", (row["id"],))
            removed.append(row["id"])
            continue
        qty = min(int(row["quantity"]), int(it.get("quantity") or 0))
        if qty < 1:
            db.execute("DELETE FROM store_pending_lines WHERE id=?", (row["id"],))
            removed.append(row["id"])
            continue

        rush = (row["priority"] or "standard") == "rush"

        def eligible(r):
            return robot_eligible_for_backlog(r, row["created_at"], assign_backlog_on_pair)

        robot_id = pick_robot_for_store(
            row["section_id"], robots, work_tasks, reserved, rush=rush, robot_filter=eligible,
        )
        if not robot_id:
            continue

        reserved.append(robot_id)
        task_id = task.create_task(
            robot_id,
            "pick",
            row["section_id"],
            row["item_id"],
            row["note"],
            qty,
        )
        task_row = task.get_task(task_id)
        if task_row:
            work_tasks.append(task_row)
            created.append(task_row)
            notify_robot_assigned(task_row)
        db.execute("DELETE FROM store_pending_lines WHERE id=?", (row["id"],))
        removed.append(row["id"])

    if removed:
        db.commit()
    return created
