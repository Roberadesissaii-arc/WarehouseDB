"""Warehouse Relay status — live tunnel URL while WarehouseDB is running."""
from flask import jsonify

from ..warehouse_relay import get_status
from . import bp


@bp.get("/relay")
def relay_status():
    return jsonify(get_status())
