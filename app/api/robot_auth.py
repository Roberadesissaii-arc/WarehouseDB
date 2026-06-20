"""Allow robots to call selected APIs using their pairing code (no staff session)."""
from flask import request

from ..models import robot, task

ROBOT_OPEN_ROUTES = {
    ("POST", "/api/robots/claim"),
    ("GET", "/api/robots/ping"),
    ("GET", "/api/health"),
    ("POST", "/api/auth/login"),
}


def is_robot_device_route():
    """On-robot polling endpoints — always reachable on the LAN (auth via X-Robot-Code)."""
    parts = request.path.strip("/").split("/")
    if len(parts) < 4 or parts[0] != "api" or parts[1] != "robots":
        return False
    if parts[-1] not in ("heartbeat", "tasks"):
        return False
    try:
        int(parts[2])
        return True
    except ValueError:
        return False


def is_open_route():
    return (request.method, request.path) in ROBOT_OPEN_ROUTES


def pairing_code_from_request():
    """Pairing codes must be sent in X-Robot-Code header (not query strings)."""
    return request.headers.get("X-Robot-Code")


def robot_request_authorized():
    """True when a robot presents a valid code for the robot id in the URL."""
    code = pairing_code_from_request()
    if not code:
        return False
    parts = request.path.strip("/").split("/")
    if len(parts) < 3 or parts[0] != "api" or parts[1] != "robots":
        return False
    if parts[-1] == "claim":
        return False
    try:
        robot_id = int(parts[2])
    except ValueError:
        return False
    from ..security import verify_robot_code

    return verify_robot_code(robot_id, code, lambda c: robot.verify_code(robot_id, c))


def task_request_authorized():
    """True when a robot presents a valid code for the task's assigned robot."""
    code = pairing_code_from_request()
    if not code:
        return False
    parts = request.path.strip("/").split("/")
    if len(parts) < 3 or parts[0] != "api" or parts[1] != "tasks":
        return False
    try:
        task_id = int(parts[2])
    except ValueError:
        return False
    from ..security import verify_robot_code

    return verify_robot_code(f"t{task_id}", code, lambda c: task.verify_robot_code(task_id, c))


def is_store_route():
    return request.path.startswith("/api/store/")


# Operational APIs the Scan backend may call with X-Scan-Key (no staff session),
# scoped to the exact methods Scan uses so the shared key can't, for example,
# delete items or robots.
_SCAN_SERVICE_ROUTES = {
    "/api/health": {"GET"},
    "/api/bootstrap": {"GET"},
    "/api/items": {"GET"},
    "/api/tasks": {"GET", "POST"},
    "/api/robots": {"GET"},
    "/api/notifications": {"GET", "PUT", "DELETE"},
}


def is_scan_service_route():
    path = request.path
    if not path.startswith("/api/"):
        return False
    for prefix, methods in _SCAN_SERVICE_ROUTES.items():
        if path == prefix or path.startswith(prefix + "/"):
            return request.method in methods
    return False


def store_request_authorized():
    from flask import current_app

    from ..security import constant_time_equals

    if not is_store_route():
        return False
    key = request.headers.get("X-Store-Key")
    expected = current_app.config.get("STORE_API_KEY")
    return constant_time_equals(key, expected)


def scan_request_authorized():
    from flask import current_app

    from ..security import constant_time_equals

    if not is_scan_service_route():
        return False
    key = request.headers.get("X-Scan-Key")
    expected = current_app.config.get("SCAN_API_KEY")
    return constant_time_equals(key, expected)


def scan_service_staff_name():
    """Staff name sent by the Scan server when acting on behalf of a signed-in floor user."""
    if not scan_request_authorized():
        return None
    return (request.headers.get("X-Scan-Staff") or "").strip() or None


def api_authorized_without_session():
    if is_open_route():
        return True
    if store_request_authorized():
        return True
    if scan_request_authorized():
        return True
    if request.path.startswith("/api/robots/") and robot_request_authorized():
        return True
    if request.path.startswith("/api/tasks/") and task_request_authorized():
        return True
    return False
