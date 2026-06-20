"""Production WSGI entry point.

Serve with a WSGI server, e.g.:
    waitress-serve --port=8000 --threads=16 wsgi:app   (Windows-friendly)
    gunicorn --bind 0.0.0.0:8000 wsgi:app        (Linux/macOS)
"""
import os

os.environ.setdefault("FLASK_ENV", "production")

from app import create_app  # noqa: E402

app = create_app()
