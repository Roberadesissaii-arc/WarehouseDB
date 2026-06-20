"""JSON login for the scan app and other API clients."""
from flask import jsonify, request, session

from . import bp
from ..models import user
from ..security import clear_login_attempts, login_allowed, record_failed_login, session_lifetime


@bp.post("/auth/login")
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify(error="Username and password are required"), 400

    try:
        login_allowed(username)
    except ValueError as exc:
        return jsonify(error=str(exc)), 429

    row = user.verify(username, password)
    if not row:
        record_failed_login(username)
        return jsonify(error="Invalid username or password. Check both fields and try again."), 401

    clear_login_attempts(username)
    session.clear()
    session.permanent = True
    from flask import current_app

    current_app.permanent_session_lifetime = session_lifetime()
    session["user_id"] = row["id"]
    session["username"] = row["username"]
    return jsonify(signed_in=True, username=row["username"])


@bp.post("/auth/logout")
def api_logout():
    session.clear()
    return jsonify(ok=True)
