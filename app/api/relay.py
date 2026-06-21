"""Warehouse Relay status — live tunnel URL while WarehouseDB is running."""
from flask import current_app, jsonify

from ..warehouse_relay import get_status
from . import bp


@bp.get("/relay")
def relay_status():
    # The status panel must never break: if anything goes wrong gathering relay
    # state, return a valid (disabled) payload + log the real error.
    try:
        return jsonify(get_status())
    except Exception:  # noqa: BLE001
        current_app.logger.exception("relay status failed")
        return jsonify({
            "enabled": False, "installed": False, "version": None,
            "running": False, "url": None, "mode": None, "tunnel_name": None,
            "url_locked": False, "named_tunnel_ready": False,
            "local_target": None, "expected_hostname": None, "started_at": None,
            "error": "Relay status is temporarily unavailable — check server logs (journalctl -u warehousedb).",
        })
