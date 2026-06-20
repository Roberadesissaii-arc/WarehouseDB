"""Development entry point.

    python run.py

Then open http://localhost:8000
For production, serve `wsgi:app` with a WSGI server (gunicorn / waitress).
"""
import os
import socket

from app import create_app
from config import get_config

app = create_app()


def _lan_ip():
    """Best-effort local IPv4 for robot firmware (WAREHOUSE_HOST in config.h)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


if __name__ == "__main__":
    cfg = get_config()
    lan = _lan_ip()
    host = cfg.HOST
    if host in ("127.0.0.1", "localhost", "::1"):
        print("NOTE: HOST was localhost - switching to 0.0.0.0 so ESP32 robots on Wi-Fi can connect.")
        host = "0.0.0.0"
    print(f"WarehouseDB running at http://localhost:{cfg.PORT}  (Ctrl+C to stop)")
    print(f"Listening on {host}:{cfg.PORT} - robots on your Wi-Fi must reach this PC.")
    if lan:
        print(f"ESP32 config.h ->  #define WAREHOUSE_HOST \"{lan}\"")
    else:
        print("Could not detect LAN IP — run ipconfig and set WAREHOUSE_HOST in Arduino/config.h")
    print("If robots still show NO SERVER, allow port 8000 in Windows Firewall (see scripts/open-firewall.ps1)")
    # The interactive debugger is remote code execution if exposed, and this dev
    # server binds 0.0.0.0 for robots. Require an explicit opt-in to enable it.
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes", "on")
    if debug:
        print("WARNING: debug mode ON (FLASK_DEBUG) — never use this on a shared network.")
    app.run(host=host, port=cfg.PORT, debug=debug, threaded=True)
