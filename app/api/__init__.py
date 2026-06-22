"""JSON API blueprint. Shared helpers + error handlers live here;
route handlers are split into per-domain modules imported at the bottom."""
import sqlite3

from flask import Blueprint, jsonify

bp = Blueprint("api", __name__, url_prefix="/api")


def require_fields(data, *fields):
    """Pull required fields from a JSON body or raise a clean 400."""
    missing = [f for f in fields if not data.get(f) and data.get(f) != 0]
    if missing:
        raise ValueError(f"Missing field(s): {', '.join(missing)}")
    return [data[f] for f in fields]


@bp.errorhandler(ValueError)
def _bad_request(err):
    return jsonify(error=str(err)), 400


@bp.errorhandler(sqlite3.IntegrityError)
def _integrity(err):
    return jsonify(error=f"Invalid reference: {err}"), 400


# Import route modules to register them on `bp` (kept last to avoid circular imports).
from . import addons, home_bays, auth, bootstrap, firmware, health, items, locations, notifications, organization, relay, robots, settings, store, system, tasks  # noqa: E402,F401
