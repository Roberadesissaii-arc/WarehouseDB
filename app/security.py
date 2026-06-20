"""Security helpers: headers, password policy, login throttling, IP allowlist."""
import hmac
import ipaddress
import re
import time
from collections import defaultdict

from flask import request

_FAILED = defaultdict(lambda: {"count": 0, "locked_until": 0.0})
ATTEMPT_WINDOW = 900
# Cap the throttle map so a flood of distinct keys can't exhaust memory.
_MAX_TRACKED_KEYS = 4096

# Robot pairing codes double as device API credentials, so brute force is
# throttled per (ip, robot) just like staff logins.
_ROBOT_FAILED = defaultdict(lambda: {"count": 0, "locked_until": 0.0})
ROBOT_MAX_ATTEMPTS = 10
ROBOT_LOCKOUT_SECONDS = 900


def constant_time_equals(a, b):
    """Timing-safe comparison for secrets (API keys, pairing codes)."""
    if not a or not b:
        return False
    return hmac.compare_digest(str(a), str(b))


def _prune(store, now):
    """Drop entries whose lock has expired and window has elapsed."""
    if len(store) <= _MAX_TRACKED_KEYS:
        return
    stale = [
        key
        for key, rec in store.items()
        if rec["locked_until"] <= now and now - rec["locked_until"] > ATTEMPT_WINDOW
    ]
    for key in stale:
        store.pop(key, None)

PASSWORD_MIN_LEN = 8
_PASSWORD_HAS_LETTER = re.compile(r"[A-Za-z]")
_PASSWORD_HAS_DIGIT = re.compile(r"\d")

_LOCAL_IPS = frozenset({"127.0.0.1", "::1"})


def _policy():
    from .models import setting

    try:
        max_attempts = int(setting.get("security_max_login_attempts") or 8)
    except (TypeError, ValueError):
        max_attempts = 8
    try:
        lockout_minutes = int(setting.get("security_lockout_minutes") or 5)
    except (TypeError, ValueError):
        lockout_minutes = 5
    try:
        session_hours = int(setting.get("security_session_hours") or 12)
    except (TypeError, ValueError):
        session_hours = 12

    return {
        "max_attempts": max(3, min(20, max_attempts)),
        "lockout_seconds": max(60, min(3600, lockout_minutes * 60)),
        "session_hours": max(1, min(72, session_hours)),
    }


def validate_password(password):
    """Enforce a minimal password policy for warehouse staff accounts."""
    if not password or len(password) < PASSWORD_MIN_LEN:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LEN} characters")
    if not _PASSWORD_HAS_LETTER.search(password) or not _PASSWORD_HAS_DIGIT.search(password):
        raise ValueError("Password must include at least one letter and one number")


def client_ip():
    # remote_addr is the real peer. When TRUST_PROXY is configured, ProxyFix has
    # already resolved it from X-Forwarded-For, so we never trust that header here.
    return request.remote_addr or "unknown"


def parse_allowlist(raw):
    entries = []
    for line in (raw or "").replace(",", "\n").split("\n"):
        line = line.strip()
        if line:
            entries.append(line)
    return entries


def _ip_matches(ip, entry):
    if ip == entry:
        return True
    if entry.endswith(".") and ip.startswith(entry):
        return True
    if "/" in entry:
        try:
            return ipaddress.ip_address(ip) in ipaddress.ip_network(entry, strict=False)
        except ValueError:
            return False
    return False


def ip_allowlist_enabled():
    from .models import setting

    return (setting.get("security_ip_allowlist_enabled") or "0") == "1"


def ip_is_allowed():
    """True when the client IP may access staff routes."""
    if not ip_allowlist_enabled():
        return True
    ip = client_ip()
    if ip in _LOCAL_IPS:
        return True
    for entry in parse_allowlist(_allowlist_raw()):
        if _ip_matches(ip, entry):
            return True
    return False


def _allowlist_raw():
    from .models import setting

    return setting.get("security_ip_allowlist") or ""


def _attempt_key(username=None):
    ip = client_ip()
    user = (username or "").strip().lower()
    if user:
        return f"{ip}:{user}"
    return ip


def login_allowed(username=None):
    policy = _policy()
    rec = _FAILED[_attempt_key(username)]
    now = time.time()
    if rec["locked_until"] > now:
        remaining = int(rec["locked_until"] - now)
        raise ValueError(f"Too many failed logins. Try again in {remaining // 60 + 1} min.")
    if rec["locked_until"] and rec["locked_until"] <= now:
        rec["count"] = 0
        rec["locked_until"] = 0.0


def record_failed_login(username=None):
    policy = _policy()
    now = time.time()
    _prune(_FAILED, now)
    rec = _FAILED[_attempt_key(username)]
    if rec["locked_until"] and now - rec["locked_until"] > ATTEMPT_WINDOW:
        rec["count"] = 0
    rec["count"] += 1
    if rec["count"] >= policy["max_attempts"]:
        rec["locked_until"] = now + policy["lockout_seconds"]


def clear_login_attempts(username=None):
    _FAILED.pop(_attempt_key(username), None)


def verify_robot_code(robot_id, code, verifier):
    """Timing-safe, throttled robot pairing-code check.

    `verifier(code)` does the actual constant-time comparison against the stored
    code. Failed guesses are counted per (ip, robot); after ROBOT_MAX_ATTEMPTS the
    pair is locked for ROBOT_LOCKOUT_SECONDS, which makes brute force infeasible.
    """
    now = time.time()
    _prune(_ROBOT_FAILED, now)
    key = f"{client_ip()}:{robot_id}"
    rec = _ROBOT_FAILED[key]
    if rec["locked_until"] > now:
        return False
    if rec["locked_until"] and rec["locked_until"] <= now:
        rec["count"] = 0
        rec["locked_until"] = 0.0
    if verifier(code):
        _ROBOT_FAILED.pop(key, None)
        return True
    rec["count"] += 1
    if rec["count"] >= ROBOT_MAX_ATTEMPTS:
        rec["locked_until"] = now + ROBOT_LOCKOUT_SECONDS
    return False


def verify_current_password(user_model, user_id, password):
    if not password:
        raise ValueError("Current password is required")
    if not user_model.verify_password(user_id, password):
        raise ValueError("Current password is incorrect")


def apply_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if response.content_type and "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def session_lifetime():
    from datetime import timedelta

    return timedelta(hours=_policy()["session_hours"])
