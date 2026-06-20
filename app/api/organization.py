"""Organization name — workspace branding shown in headers and exports."""
from flask import jsonify, request

from . import bp
from ..models import setting


@bp.get("/organization")
def get_organization():
    return jsonify(setting.get_organization())


@bp.put("/organization")
def update_organization():
    data = request.get_json(silent=True) or {}
    if "org_name" not in data:
        raise ValueError("org_name is required")
    setting.set_organization(data["org_name"])
    return jsonify(setting.get_organization())
