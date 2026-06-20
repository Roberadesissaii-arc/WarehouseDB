"""API routes for items."""
from flask import jsonify, request

from . import bp, require_fields
from ..models import item, location


@bp.get("/items")
def list_items():
    q = (request.args.get("q") or "").strip() or None
    shelf_id = request.args.get("shelf_id", type=int)
    return jsonify(item.search_items(q, shelf_id))


@bp.get("/items/<int:item_id>")
def get_item(item_id):
    found = item.get_item(item_id)
    return (jsonify(found), 200) if found else (jsonify(error="Not found"), 404)


@bp.get("/items/by-sku/<sku>")
def get_item_by_sku(sku):
    found = item.get_item_by_sku(sku)
    return (jsonify(found), 200) if found else (jsonify(error="Not found"), 404)


@bp.post("/items")
def add_item():
    data = request.get_json(silent=True) or {}
    name, shelf_id = require_fields(data, "name", "shelf_id")
    new_id = item.create_item(name, data.get("sku"), shelf_id, data.get("notes"), data.get("quantity"))
    return jsonify(id=new_id), 201


@bp.put("/items/<int:item_id>")
def edit_item(item_id):
    data = request.get_json(silent=True) or {}
    name, shelf_id = require_fields(data, "name", "shelf_id")
    return jsonify(item.update_item(
        item_id, name, data.get("sku"), shelf_id, data.get("notes"), data.get("quantity"),
    ))


@bp.delete("/items/<int:item_id>")
def del_item(item_id):
    location.delete_entity("items", item_id)
    return jsonify(ok=True)
