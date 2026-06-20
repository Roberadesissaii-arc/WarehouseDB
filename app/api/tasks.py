"""API routes for tasks (robot work orders)."""
from flask import jsonify, request, session

from . import bp, require_fields
from .robot_auth import task_request_authorized, scan_service_staff_name
from ..database import TASK_ACTIONS, TASK_STATUSES
from ..database import ROBOT_REPORTABLE_STATUSES
from ..models import item, location, notification, robot, task, user


def _current_staff_name():
    """Resolve staff from warehouse session or Scan service header."""
    if session.get("user_id"):
        name = user.resolve_session_username(session)
        if name and name != session.get("username"):
            session["username"] = name
        return name
    return scan_service_staff_name()


def _notify_task(event, t, *, staff=None):
    if not t:
        return
    robot_name = t.get("robot") or "Robot"
    action = (t.get("action") or "task").upper()
    target = t.get("item") or t.get("section") or "warehouse"
    order_ref = t.get("store_order_ref")
    order_prefix = f"Pick request {order_ref} · " if order_ref else ""
    href = f"/tasks/{t['id']}" if t.get("id") else "/tasks"
    staff_name = (staff or "").strip() or None

    if event == "created":
        notification.create("task", f"New {action} task", f"{robot_name} → {target}", href)
    elif event == "in_progress":
        if staff_name:
            notification.create(
                "task",
                f"{staff_name} accepted pick",
                f"{order_prefix}Assigned to {robot_name} — staff took over · {target}",
                href,
            )
        else:
            notification.create("task", f"{robot_name} started {action}", target, href)
    elif event == "done":
        if staff_name:
            notification.create(
                "task",
                f"{staff_name} fulfilled pick",
                f"{order_prefix}Completed on the floor · {target}",
                href,
            )
        else:
            notification.create("task", f"{robot_name} finished {action}", target, href)


def _validate_action(action):
    if action not in TASK_ACTIONS:
        raise ValueError(f"Action must be one of: {', '.join(TASK_ACTIONS)}")
    return action


def _validate_status(status):
    if status not in TASK_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(TASK_STATUSES)}")
    return status


@bp.get("/tasks")
def list_tasks():
    robot_id = request.args.get("robot_id", type=int)
    status = request.args.get("status") or None
    return jsonify(task.list_tasks(robot_id, status))


@bp.get("/tasks/<int:task_id>")
def get_task(task_id):
    found = task.get_task(task_id)
    if not found:
        return jsonify(error="Not found"), 404
    return jsonify(_task_with_store_status(found))


def _task_with_store_status(task_row):
    from ..models import store_pending
    from ..store_orders import order_status_from_tasks

    payload = dict(task_row)
    order_ref = payload.get("store_order_ref")
    if order_ref:
        related = task.list_tasks_for_store_order(order_ref)
        pending = store_pending.pending_count_for_order(order_ref)
        payload["store_order_status"] = order_status_from_tasks(related, pending)
    return payload


@bp.post("/tasks")
def add_task():
    data = request.get_json(silent=True) or {}
    robot_id, action = require_fields(data, "robot_id", "action")
    _validate_action(action)
    found = robot.get_robot(robot_id)
    if not found:
        raise ValueError("Robot not found")
    if not found.get("paired"):
        raise ValueError("Robot is not paired yet — pair it before assigning tasks")
    section_id = data.get("section_id")
    item_id = data.get("item_id")
    if action == "pick" and item_id:
        it = item.get_item(item_id)
        if not it:
            raise ValueError("Item not found")
        section_id = it["location"]["section_id"]
    staff = (data.get("staff_username") or "").strip() or None
    new_id = task.create_task(
        robot_id, action, section_id, item_id,
        data.get("note"), data.get("quantity"), staff,
    )
    if data.get("status") and data["status"] != "queued":
        _validate_status(data["status"])
        task.update_task(
            new_id, action, data.get("section_id"), data.get("item_id"),
            data["status"], data.get("note"), data.get("quantity"),
        )
    _notify_task("created", task.get_task(new_id))
    return jsonify(task.get_task(new_id)), 201


def _apply_sync_notifications(changed):
    task.emit_status_notifications(changed)


@bp.put("/tasks/<int:task_id>")
def edit_task(task_id):
    data = request.get_json(silent=True) or {}
    (action,) = require_fields(data, "action")
    _validate_action(action)
    before = task.get_task(task_id)
    if not before:
        return jsonify(error="Not found"), 404
    if task_request_authorized() or session.get("username"):
        status = _validate_status(data.get("status") or before["status"])
    else:
        status = before["status"]
    updated = task.update_task(
        task_id, action, data.get("section_id"), data.get("item_id"),
        status, data.get("note"), data.get("quantity"),
    )
    staff = _current_staff_name() if session.get("user_id") else None
    if before["status"] != status:
        if staff and status in ("in_progress", "done"):
            task.set_staff_username(task_id, staff)
        if status == "in_progress":
            _notify_task("in_progress", updated, staff=staff)
        elif status == "done":
            _notify_task("done", updated, staff=staff)
    return jsonify(updated)


@bp.post("/tasks/<int:task_id>/fulfill")
def fulfill_task(task_id):
    """Staff manually marks a task complete (e.g. picked by hand when robot is stuck)."""
    staff = _current_staff_name()
    if not staff:
        return jsonify(error="Unauthorized"), 401
    before = task.get_task(task_id)
    if not before:
        return jsonify(error="Not found"), 404
    if before["status"] == "cancelled":
        return jsonify(error="Task is cancelled"), 400
    task.set_staff_username(task_id, staff)
    if before["status"] != "done":
        _, updated = task.set_task_status(task_id, "done")
        _notify_task("done", updated, staff=staff)
    else:
        updated = task.get_task(task_id)
    return jsonify(_task_with_store_status(updated))


@bp.post("/tasks/<int:task_id>/accept")
def accept_task(task_id):
    """Staff accepts a queued task and marks it in progress."""
    staff = _current_staff_name()
    if not staff:
        return jsonify(error="Unauthorized"), 401
    before = task.get_task(task_id)
    if not before:
        return jsonify(error="Not found"), 404
    if before["status"] not in ("queued", "in_progress"):
        return jsonify(error="Only open tasks can be accepted"), 400
    task.set_staff_username(task_id, staff)
    if before["status"] != "in_progress":
        _, updated = task.set_task_status(task_id, "in_progress")
        _notify_task("in_progress", updated, staff=staff)
    else:
        updated = task.get_task(task_id)
    return jsonify(_task_with_store_status(updated))


@bp.post("/tasks/<int:task_id>/cancel")
def cancel_task(task_id):
    try:
        updated = task.cancel_task(task_id)
    except LookupError:
        return jsonify(error="Not found"), 404
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(updated)


@bp.delete("/tasks/<int:task_id>")
def del_task(task_id):
    location.delete_entity("tasks", task_id)
    return jsonify(ok=True)


@bp.get("/robots/<int:robot_id>/tasks")
def robot_tasks(robot_id):
    """A paired robot polls this to read its assigned work and stay online."""
    status = request.args.get("status")
    found = robot.get_robot(robot_id)
    if not found:
        return jsonify(error="Not found"), 404
    try:
        if status:
            if status not in ROBOT_REPORTABLE_STATUSES:
                return jsonify(
                    error=f"status must be one of: {', '.join(ROBOT_REPORTABLE_STATUSES)}"
                ), 400
            robot.report_status(robot_id, status)
            _apply_sync_notifications(task.sync_robot_tasks(robot_id, status))
        else:
            robot.touch_robot(robot_id)
            live = found.get("status")
            if live in ROBOT_REPORTABLE_STATUSES:
                _apply_sync_notifications(task.sync_robot_tasks(robot_id, live))
    except LookupError:
        return jsonify(error="Not found"), 404
    return jsonify(task.list_tasks(robot_id=robot_id))
