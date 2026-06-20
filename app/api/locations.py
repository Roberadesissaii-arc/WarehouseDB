"""API routes for the location hierarchy: tree, warehouses, sections, shelves."""
from flask import jsonify, request

from . import bp, require_fields
from ..models import location


@bp.get("/tree")
def tree():
    return jsonify(location.fetch_tree())


@bp.post("/warehouses")
def add_warehouse():
    (name,) = require_fields(request.get_json(silent=True) or {}, "name")
    return jsonify(id=location.create_warehouse(name)), 201


@bp.post("/sections")
def add_section():
    data = request.get_json(silent=True) or {}
    warehouse_id, name = require_fields(data, "warehouse_id", "name")
    return jsonify(id=location.create_section(warehouse_id, name)), 201


@bp.post("/shelves")
def add_shelf():
    data = request.get_json(silent=True) or {}
    section_id, code = require_fields(data, "section_id", "code")
    return jsonify(id=location.create_shelf(section_id, code)), 201


@bp.delete("/warehouses/<int:wid>")
def del_warehouse(wid):
    location.delete_entity("warehouses", wid)
    return jsonify(ok=True)


@bp.delete("/sections/<int:sid>")
def del_section(sid):
    location.delete_entity("sections", sid)
    return jsonify(ok=True)


@bp.delete("/shelves/<int:shid>")
def del_shelf(shid):
    location.delete_entity("shelves", shid)
    return jsonify(ok=True)
