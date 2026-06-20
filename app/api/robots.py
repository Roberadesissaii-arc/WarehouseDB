"""API routes for robots."""
from flask import jsonify, request

from . import bp, require_fields
from ..database import ROBOT_REPORTABLE_STATUSES
from ..models import location, notification, robot, store_pending, task, unit_image


def _dispatch_store_queue():
    store_pending.dispatch_all(robot.fetch_robots(), task.list_tasks())


@bp.get("/robots")
def list_robots():
    robot.process_offline_alerts()
    return jsonify(robot.fetch_robots())


@bp.get("/robots/<int:robot_id>")
def get_robot(robot_id):
    robot.process_offline_alerts()
    found = robot.get_robot(robot_id)
    if not found:
        return jsonify(error="Not found"), 404
    from ..firmware_catalog import robot_firmware_status

    found["firmware"] = robot_firmware_status(found.get("firmware_version"), found.get("unit_code"))
    return jsonify(found)


@bp.get("/robots/pair-status")
def robot_pair_status_query():
    code = request.args.get("code")
    if code:
        found = robot.pair_status_by_code(code)
        return jsonify(found) if found else (jsonify(error="Invalid pairing code"), 400)
    return jsonify(error="code query parameter required"), 400


@bp.get("/robots/<int:robot_id>/pair-status")
def robot_pair_status(robot_id):
    found = robot.pair_status(robot_id)
    return jsonify(found) if found else (jsonify(error="Not found"), 404)


@bp.post("/robots/<int:robot_id>/cancel-pairing")
def cancel_robot_pairing(robot_id):
    """Drop a pending robot slot when pairing is cancelled or times out."""
    if robot.cancel_pending_pairing(robot_id):
        return jsonify(ok=True)
    return jsonify(error="Not found or already paired"), 404


@bp.get("/robots/unit-catalog")
def robot_unit_catalog():
    return jsonify(unit_image.catalog())


@bp.post("/robots/pair")
def pair_robot():
    """Link the 6-digit code from the robot screen to a fleet record."""
    data = request.get_json(silent=True) or {}
    pairing_code = data.get("pairing_code")
    if not pairing_code:
        return jsonify(error="pairing_code is required"), 400
    if data.get("unit_image") is None:
        return jsonify(error="Select a chassis model for this robot"), 400
    name = (data.get("name") or "").strip()
    try:
        new_id = robot.pair_robot(
            pairing_code,
            name,
            data.get("home_bay_id"),
            data.get("home_bay_name"),
            data.get("unit_image"),
        )
    except robot.PairingError as exc:
        return jsonify(error=str(exc), code=exc.code, robot=exc.robot), 409
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    display_name = name or unit_image.brand_for(data.get("unit_image"))
    notification.create(
        "fleet",
        f"Pairing {display_name}",
        "Waiting for the robot to confirm on its screen",
        f"/robots/{new_id}",
    )
    return jsonify(
        id=new_id,
        robot_id=new_id,
        pairing_code=robot.normalize_code(pairing_code),
        waiting=True,
    ), 201


@bp.get("/robots/ping")
def robot_ping():
    """Health check for ESP32 — no login required."""
    return jsonify(ok=True, service="warehousedb")


@bp.post("/robots/claim")
def claim_robot():
    """Physical robot confirms pairing with the code shown on its display."""
    data = request.get_json(silent=True) or {}
    (pairing_code,) = require_fields(data, "pairing_code")
    try:
        found = robot.claim_robot(pairing_code, data.get("device_id"))
    except robot.PairingError as exc:
        return jsonify(error=str(exc), code=exc.code, robot=exc.robot), 409
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except LookupError as exc:
        return jsonify(error=str(exc)), 404
    notification.create(
        "fleet",
        f"{found['name']} connected",
        "Robot completed pairing and is online",
        f"/robots/{found['id']}",
    )
    _dispatch_store_queue()
    return jsonify(found)


@bp.post("/robots")
def add_robot():
    return jsonify(
        error="Use POST /api/robots/pair with the 6-digit code from the robot screen"
    ), 400


@bp.put("/robots/<int:robot_id>")
def edit_robot(robot_id):
    """Staff may edit name and home bay only — not live status."""
    data = request.get_json(silent=True) or {}
    (name,) = require_fields(data, "name")
    if "status" in data:
        return jsonify(error="Robot status is reported automatically; it cannot be set here"), 400
    updated = robot.update_robot(
        robot_id, name, data.get("home_bay_id"), data.get("home_bay_name"),
    )
    return jsonify(updated) if updated else (jsonify(error="Not found"), 404)


@bp.post("/robots/<int:robot_id>/charge")
def send_robot_to_charge(robot_id):
    """Send a paired robot back to its home bay to charge."""
    found = robot.get_robot(robot_id)
    if not found:
        return jsonify(error="Not found"), 404
    if not found.get("paired"):
        return jsonify(error="Robot is not paired yet"), 400
    new_id = task.create_charge_task(robot_id)
    notification.create(
        "fleet",
        f"{found['name']} sent to charge",
        f"Returning to {found.get('location') or 'home bay'}",
        f"/robots/{robot_id}",
    )
    return jsonify(task.get_task(new_id)), 201


@bp.post("/robots/<int:robot_id>/heartbeat")
def robot_heartbeat(robot_id):
    """A paired robot reports its live status (working / idle / charging)."""
    data = request.get_json(silent=True) or {}
    (status,) = require_fields(data, "status")
    try:
        battery = data.get("battery_pct")
        if battery is not None and battery != "":
            battery = int(battery)
        else:
            battery = None
        fw = (data.get("firmware_version") or "").strip() or None
        updated = robot.report_status(robot_id, status, battery, fw)
        task.emit_status_notifications(task.sync_robot_tasks(robot_id, status))
        _dispatch_store_queue()
        return jsonify(updated)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except LookupError:
        return jsonify(error="Not found"), 404


@bp.delete("/robots/<int:robot_id>")
def del_robot(robot_id):
    location.delete_entity("robots", robot_id)
    return jsonify(ok=True)
