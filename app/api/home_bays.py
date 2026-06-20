"""API routes for robot home warehouse and dock bases."""
from flask import jsonify, request

from . import bp, require_fields
from ..models import home_bay


@bp.get("/home-bays")
def list_home_bays():
    return jsonify(home_bay.fetch_payload())


@bp.post("/home-bays")
def create_home_bay():
    data = request.get_json(silent=True) or {}
    (name,) = require_fields(data, "name")
    try:
        return jsonify(home_bay.create_home_bay(name)), 201
    except ValueError as exc:
        return jsonify(error=str(exc)), 400


@bp.delete("/home-bays/<int:bay_id>")
def delete_home_bay(bay_id):
    try:
        home_bay.delete_home_bay(bay_id)
        return jsonify(ok=True)
    except LookupError:
        return jsonify(error="Not found"), 404
    except ValueError as exc:
        return jsonify(error=str(exc)), 400


@bp.put("/home-bays/warehouse")
def rename_home_warehouse():
    data = request.get_json(silent=True) or {}
    (name,) = require_fields(data, "name")
    wh = home_bay.set_home_warehouse_name(name)
    return jsonify(home_bay.fetch_payload() | {"warehouse_name": wh})
