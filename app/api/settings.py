"""API routes for settings, account, and data export/reset/import."""
import json
from datetime import datetime, timezone

from flask import Response, jsonify, request, session

from . import bp, require_fields
from .. import database
from ..models import data_import, item, location, product_import, robot, setting, user
from ..security import verify_current_password


@bp.get("/security")
def get_security():
    from ..security import client_ip, ip_allowlist_enabled, parse_allowlist

    cfg = setting.get_security()
    return jsonify(
        **cfg,
        client_ip=client_ip(),
        allowlist_entries=parse_allowlist(cfg["ip_allowlist"]),
        password_min_length=8,
        headers_enabled=True,
    )


@bp.put("/security")
def update_security():
    data = request.get_json(silent=True) or {}
    (password,) = require_fields(data, "current_password")
    verify_current_password(user, session["user_id"], password)
    setting.set_security(data)
    from flask import current_app
    from ..security import session_lifetime

    current_app.permanent_session_lifetime = session_lifetime()
    return jsonify(setting.get_security())


def _export_payload():
    robots_out = []
    for r in robot.fetch_robots():
        row = dict(r)
        row.pop("pairing_code", None)
        robots_out.append(row)
    return {
        "export_version": 1,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "warehouses": location.fetch_tree(),
        "items": item.search_items(),
        "robots": robots_out,
        "settings": {**setting.get_public(), "security": setting.get_security()},
    }


@bp.get("/settings")
def get_settings():
    return jsonify(setting.get_public())


@bp.get("/me")
def me():
    if not session.get("user_id"):
        return jsonify(signed_in=False, username=None)
    name = user.resolve_session_username(session)
    if name and name != session.get("username"):
        session["username"] = name
    return jsonify(signed_in=True, username=name, user_id=session["user_id"])


@bp.put("/settings")
def update_settings():
    data = request.get_json(silent=True) or {}
    if "org_name" in data:
        setting.set_organization(data["org_name"])
    if "status_labels" in data:
        if not isinstance(data["status_labels"], dict):
            raise ValueError("status_labels must be an object")
        setting.set("status_labels", json.dumps(data["status_labels"]))
    if "home_warehouse_name" in data:
        setting.set("home_warehouse_name", (data["home_warehouse_name"] or "").strip()[:120] or "Robot Home")
    if "status_colors" in data:
        if not isinstance(data["status_colors"], dict):
            raise ValueError("status_colors must be an object")
        setting.set("status_colors", json.dumps(data["status_colors"]))
    if "notifications" in data:
        setting.set_notifications(data["notifications"])
    if "fleet" in data:
        setting.set_fleet(data["fleet"])
    if "relay" in data:
        setting.set_relay(data["relay"])
    return jsonify(setting.get_public())


@bp.put("/account")
def update_account():
    data = request.get_json(silent=True) or {}
    username, current = require_fields(data, "username", "current_password")
    verify_current_password(user, session["user_id"], current)
    new_password = data.get("new_password")
    if isinstance(new_password, str):
        new_password = new_password.strip() or None
    else:
        new_password = None
    if new_password:
        confirm = data.get("confirm_password")
        if isinstance(confirm, str):
            confirm = confirm.strip()
        else:
            confirm = ""
        if not confirm:
            raise ValueError("Confirm your new password.")
        if new_password != confirm:
            raise ValueError("New password and confirmation do not match.")
    username = username.strip()
    user.update_credentials(session["user_id"], username, new_password)
    session["username"] = username
    return jsonify(ok=True, username=username, password_changed=bool(new_password))


@bp.post("/export")
def export_data():
    """Download a JSON backup. Requires current password."""
    data = request.get_json(silent=True) or {}
    (password,) = require_fields(data, "current_password")
    verify_current_password(user, session["user_id"], password)
    payload = _export_payload()
    body = json.dumps(payload, indent=2)
    return Response(
        body,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=warehousedb-export.json"},
    )


@bp.get("/export")
def export_data_get():
    """Legacy GET — disabled; use POST with password."""
    return jsonify(error="Use POST /api/export with your current password"), 405


@bp.post("/import")
def import_data():
    """Restore warehouse data from a JSON backup. Requires current password."""
    password = request.form.get("current_password")
    raw = None

    upload = request.files.get("file")
    if upload:
        if not password:
            password = request.form.get("current_password")
        raw = upload.read()
    elif request.is_json:
        body = request.get_json(silent=True) or {}
        password = password or body.get("current_password")
        raw = {k: v for k, v in body.items() if k != "current_password"}

    if not password:
        raise ValueError("current_password is required")
    verify_current_password(user, session["user_id"], password)
    if raw is None:
        raise ValueError("Upload a JSON backup file")

    summary = data_import.import_snapshot(raw)
    return jsonify(ok=True, summary=summary)


@bp.post("/import/products")
def import_products():
    """Add items from a product catalog JSON file. Requires current password."""
    password = request.form.get("current_password")
    raw = None

    upload = request.files.get("file")
    if upload:
        raw = upload.read()
    elif request.is_json:
        body = request.get_json(silent=True) or {}
        password = password or body.get("current_password")
        raw = {k: v for k, v in body.items() if k != "current_password"}

    if not password:
        raise ValueError("current_password is required")
    verify_current_password(user, session["user_id"], password)
    if raw is None:
        raise ValueError("Upload a JSON product catalog file")

    summary = product_import.import_products(raw)
    return jsonify(ok=True, summary=summary)


@bp.post("/reset")
def reset_data():
    """Wipe all warehouse data (inventory, robots, tasks, alerts). Requires current password."""
    data = request.get_json(silent=True) or {}
    (password,) = require_fields(data, "current_password")
    verify_current_password(user, session["user_id"], password)
    database.reset_sample_data()
    return jsonify(ok=True)


@bp.post("/seed-demo")
def seed_demo():
    """Load demo warehouses and items when the database is empty. Requires current password."""
    data = request.get_json(silent=True) or {}
    (password,) = require_fields(data, "current_password")
    verify_current_password(user, session["user_id"], password)
    summary = database.load_demo_data()
    return jsonify(ok=True, summary=summary)
