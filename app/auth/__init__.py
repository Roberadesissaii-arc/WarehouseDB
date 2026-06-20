"""Auth blueprint: login / logout."""
from flask import Blueprint

bp = Blueprint("auth", __name__)

from . import routes  # noqa: E402,F401  registers routes on bp
