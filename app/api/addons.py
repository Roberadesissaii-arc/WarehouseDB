"""Install sibling apps (Store / Scan) from the Integration page.

Gated by the same logged-in session as the rest of the API. The actual work runs
with no root (see app/addons.py).
"""
from flask import jsonify

from .. import addons
from . import bp


@bp.post("/addons/<addon_id>/install")
def addon_install(addon_id):
    try:
        st = addons.start_install(addon_id)
    except ValueError:
        return jsonify(error="Unknown app"), 404
    return jsonify(ok=True, **st)


@bp.get("/addons/<addon_id>/status")
def addon_status(addon_id):
    return jsonify(addons.get_status(addon_id))
