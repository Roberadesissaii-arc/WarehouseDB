"""Application factory."""
import os

from flask import Flask, jsonify, redirect, request, session, url_for

from config import get_config
from . import database


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or get_config())

    # Keep the database in the instance folder (outside the source tree).
    os.makedirs(app.instance_path, exist_ok=True)
    if not app.config.get("DATABASE"):
        app.config["DATABASE"] = os.path.join(app.instance_path, "warehouse.db")
    app.config["STARTED_AT"] = __import__("time").time()

    # Honor X-Forwarded-For only when explicitly told how many proxies sit in
    # front of us. With 0 hops (the default) the header is ignored, so client
    # IPs used for throttling and the allowlist can't be spoofed.
    hops = app.config.get("TRUST_PROXY_HOPS", 0)
    if hops > 0:
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)

    # Database lifecycle + schema + first-run seed/defaults.
    database.init_app(app)
    with app.app_context():
        database.init_schema()
        from .models import setting, user
        user.ensure_default_admin()
        setting.ensure_defaults()
        database.seed_if_empty()
        # Schema-only CLI commands (flask init-db) must run fast and exit cleanly,
        # so they must NOT launch the cloudflared tunnel (a long-lived subprocess
        # that would keep the short-lived process from exiting). The actual server
        # starts the relay normally.
        if os.environ.get("WAREHOUSE_SKIP_RELAY") != "1":
            from . import warehouse_relay
            warehouse_relay.sync_with_settings()

    _register_security(app)

    # Blueprints.
    from .main import bp as main_bp
    from .api import bp as api_bp
    from .auth import bp as auth_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)

    return app


def _register_security(app):
    """Require a logged-in session for everything except login and static files."""
    import os
    from config import DEFAULT_SCAN_API_KEY, DEFAULT_SECRET_KEY, DEFAULT_STORE_API_KEY

    if os.environ.get("FLASK_ENV", "").lower() == "production":
        insecure = []
        if app.config.get("SECRET_KEY") == DEFAULT_SECRET_KEY:
            insecure.append("SECRET_KEY")
        if app.config.get("STORE_API_KEY") == DEFAULT_STORE_API_KEY:
            insecure.append("STORE_API_KEY")
        if app.config.get("SCAN_API_KEY") == DEFAULT_SCAN_API_KEY:
            insecure.append("SCAN_API_KEY")
        if insecure:
            raise RuntimeError(
                "Refusing to start in production with default "
                + ", ".join(insecure)
                + ". Set strong values in instance/warehousedb.env."
            )

    @app.after_request
    def add_security_headers(response):
        from .security import apply_security_headers
        return apply_security_headers(response)

    @app.before_request
    def apply_session_policy():
        app.permanent_session_lifetime = __import__(
            "app.security", fromlist=["session_lifetime"]
        ).session_lifetime()

    @app.before_request
    def check_ip_allowlist():
        if request.endpoint in ("auth.login", "static", "main.service_worker") or request.endpoint is None:
            return
        from .api.robot_auth import api_authorized_without_session, is_open_route, is_robot_device_route
        if is_open_route() or is_robot_device_route():
            return
        if api_authorized_without_session():
            return
        from .security import ip_is_allowed
        if ip_is_allowed():
            return
        if request.path.startswith("/api/"):
            return jsonify(error="Access denied from this network"), 403
        return (
            "<h1>403 — network not allowed</h1>"
            "<p>Your IP is not on the warehouse allowlist. Contact an administrator.</p>",
            403,
        )

    @app.before_request
    def require_login():
        if request.endpoint in ("auth.login", "static", "main.service_worker") or request.endpoint is None:
            return
        if "user_id" not in session:
            from .api.robot_auth import api_authorized_without_session
            if request.path.startswith("/api/") and api_authorized_without_session():
                return
            if request.path.startswith("/api/"):
                return jsonify(error="Authentication required"), 401
            return redirect(url_for("auth.login"))

    @app.context_processor
    def inject_globals():
        org_name = ""
        first_name = last_name = email = ""
        if "user_id" in session:
            from .models import setting, user
            org_name = setting.get("org_name") or ""
            row = user.get_by_id(session["user_id"])
            if row:
                keys = row.keys()
                first_name = (row["first_name"] if "first_name" in keys else "") or ""
                last_name = (row["last_name"] if "last_name" in keys else "") or ""
                email = (row["email"] if "email" in keys else "") or ""
        return {
            "org_name": org_name,
            "current_user": session.get("username"),
            "current_first_name": first_name,
            "current_last_name": last_name,
            "current_email": email,
        }
