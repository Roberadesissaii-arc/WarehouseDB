"""System diagnostics — host device and database snapshot."""
from flask import jsonify

from ..system_info import collect
from . import bp


@bp.get("/system")
def system_overview():
    return jsonify(collect())
