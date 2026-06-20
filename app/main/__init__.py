"""Main blueprint: server-rendered pages."""
from flask import Blueprint

bp = Blueprint("main", __name__)

from . import routes  # noqa: E402,F401  registers routes on bp
