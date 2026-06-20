"""Firmware catalog — latest robot release shipped with WarehouseDB."""
from flask import jsonify

from ..firmware_catalog import latest_release, robot_firmware_status
from . import bp


@bp.get("/firmware")
def firmware_catalog():
    latest = latest_release()
    return jsonify(
        latest=latest["version"],
        released_at=latest.get("released_at"),
        notes=latest.get("notes") or "",
        sketch_root=latest.get("sketch_root") or "Arduino",
    )


@bp.get("/firmware/robots/<int:robot_id>")
def robot_firmware(robot_id):
    from ..models import robot as robot_model

    found = robot_model.get_robot(robot_id)
    if not found:
        return jsonify(error="Not found"), 404
    return jsonify(robot_firmware_status(found.get("firmware_version"), found.get("unit_code")))
