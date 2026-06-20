"""Key/value application settings (organization name, status labels & colors)."""
import ipaddress
import json

from ..database import get_db

ORG_MAX_LENGTH = 120

# Defaults are written on first run and used as fallbacks.
DEFAULTS = {
    "org_name": "North Depot Co.",
    "home_warehouse_name": "Robot Home",
    "status_labels": json.dumps({
        "working": "Working",
        "idle": "Idle",
        "charging": "Charging",
        "returning": "Returning",
        "error": "Error",
        "offline": "Offline",
    }),
    "status_colors": json.dumps({
        "working": "#1f9d55",
        "idle": "#ffd400",
        "charging": "#ff5b1a",
        "returning": "#3b82f6",
        "error": "#d94a2a",
        "offline": "#b8b2a5",
    }),
    "security_max_login_attempts": "8",
    "security_lockout_minutes": "5",
    "security_session_hours": "12",
    "security_ip_allowlist_enabled": "0",
    "security_ip_allowlist": "",
    "notify_sound": "1",
    "notify_sound_kind": "chime",
    "notify_volume": "70",
    "notify_desktop": "0",
    "notify_mobile": "0",
    "notify_kinds": json.dumps({"fleet": True, "store": True, "system": True}),
    "fleet_assign_backlog_on_pair": "0",
    "relay_enabled": "0",
}

NOTIFY_SOUNDS = ("chime", "beep", "ding", "alert")

SECURITY_KEYS = (
    "security_max_login_attempts",
    "security_lockout_minutes",
    "security_session_hours",
    "security_ip_allowlist_enabled",
    "security_ip_allowlist",
)


def ensure_defaults():
    """Insert any default setting that is not yet stored."""
    db = get_db()
    have = {r["key"] for r in db.execute("SELECT key FROM settings")}
    for key, value in DEFAULTS.items():
        if key not in have:
            db.execute("INSERT INTO settings(key, value) VALUES(?,?)", (key, value))
    db.commit()
    _merge_status_defaults()


def _merge_status_defaults():
    """Add labels/colors for any new robot statuses on existing installs."""
    labels = json.loads(get("status_labels"))
    colors = json.loads(get("status_colors"))
    base_labels = json.loads(DEFAULTS["status_labels"])
    base_colors = json.loads(DEFAULTS["status_colors"])
    changed = False
    for key, val in base_labels.items():
        if key not in labels:
            labels[key] = val
            changed = True
    for key, val in base_colors.items():
        if key not in colors:
            colors[key] = val
            changed = True
    if changed:
        set("status_labels", json.dumps(labels))
        set("status_colors", json.dumps(colors))


def get(key):
    row = get_db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else DEFAULTS.get(key)


def set(key, value):
    get_db().execute(
        "INSERT INTO settings(key, value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    get_db().commit()


def get_organization():
    """Organization branding for headers and backup metadata."""
    return {
        "org_name": get("org_name") or "",
        "updated_at": get("org_updated_at") or None,
        "max_length": ORG_MAX_LENGTH,
        "fallback_subtitle": "/// physical inventory & fleet control",
        "shown_on": [
            {"id": "board", "label": "Board header"},
            {"id": "settings", "label": "Settings header"},
            {"id": "guide", "label": "Staff guide header"},
            {"id": "export", "label": "JSON backup manifest"},
        ],
    }


def set_organization(name):
    """Persist organization name and stamp last-updated time."""
    from datetime import datetime, timezone

    clean = (name or "").strip()
    if len(clean) > ORG_MAX_LENGTH:
        raise ValueError(f"Organization name must be {ORG_MAX_LENGTH} characters or fewer")
    set("org_name", clean)
    set("org_updated_at", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    return clean


def get_fleet():
    """Fleet behaviour toggles for administrators."""
    return {
        "assign_backlog_on_pair": (get("fleet_assign_backlog_on_pair") or "0") == "1",
    }


def set_fleet(data):
    """Validate and persist fleet settings."""
    if not isinstance(data, dict):
        raise ValueError("fleet must be an object")
    if "assign_backlog_on_pair" in data:
        set("fleet_assign_backlog_on_pair", "1" if data["assign_backlog_on_pair"] else "0")
    return get_fleet()


def assign_backlog_on_pair():
    return get_fleet()["assign_backlog_on_pair"]


def relay_enabled():
    return (get("relay_enabled") or "0") == "1"


def get_relay():
    return {"enabled": relay_enabled()}


def set_relay(data):
    if not isinstance(data, dict):
        raise ValueError("relay must be an object")
    if "enabled" not in data:
        return get_relay()
    enabled = bool(data["enabled"])
    set("relay_enabled", "1" if enabled else "0")
    from ..warehouse_relay import apply_enabled

    apply_enabled(enabled)
    return get_relay()


def get_public():
    """Settings the frontend needs, with JSON fields parsed."""
    return {
        "org_name": get("org_name"),
        "home_warehouse_name": get("home_warehouse_name"),
        "status_labels": json.loads(get("status_labels")),
        "status_colors": json.loads(get("status_colors")),
        "notifications": get_notifications(),
        "fleet": get_fleet(),
        "relay": get_relay(),
    }


def get_notifications():
    """Alert sound / display preferences for the masthead alerts feed."""
    try:
        kinds = json.loads(get("notify_kinds"))
    except (TypeError, ValueError):
        kinds = {"fleet": True, "store": True, "system": True}
    try:
        volume = int(get("notify_volume") or 70)
    except (TypeError, ValueError):
        volume = 70
    return {
        "sound": (get("notify_sound") or "1") == "1",
        "sound_kind": get("notify_sound_kind") or "chime",
        "volume": max(0, min(100, volume)),
        "desktop": (get("notify_desktop") or "0") == "1",
        "mobile": (get("notify_mobile") or "0") == "1",
        "kinds": kinds,
    }


def set_notifications(data):
    """Validate and persist notification preferences."""
    if not isinstance(data, dict):
        raise ValueError("notifications must be an object")
    sound_kind = str(data.get("sound_kind") or "chime")
    if sound_kind not in NOTIFY_SOUNDS:
        raise ValueError(f"sound_kind must be one of: {', '.join(NOTIFY_SOUNDS)}")
    try:
        volume = int(data.get("volume", 70))
    except (TypeError, ValueError) as exc:
        raise ValueError("volume must be a number") from exc
    volume = max(0, min(100, volume))

    raw_kinds = data.get("kinds") or {}
    if not isinstance(raw_kinds, dict):
        raise ValueError("kinds must be an object")
    kinds = {k: bool(raw_kinds.get(k, True)) for k in ("fleet", "store", "system")}

    set("notify_sound", "1" if data.get("sound", True) else "0")
    set("notify_sound_kind", sound_kind)
    set("notify_volume", str(volume))
    set("notify_desktop", "1" if data.get("desktop") else "0")
    set("notify_mobile", "1" if data.get("mobile") else "0")
    set("notify_kinds", json.dumps(kinds))
    return get_notifications()


def get_security():
    """Security policy stored in settings (admin UI)."""
    return {
        "max_login_attempts": int(get("security_max_login_attempts") or 8),
        "lockout_minutes": int(get("security_lockout_minutes") or 5),
        "session_hours": int(get("security_session_hours") or 12),
        "ip_allowlist_enabled": (get("security_ip_allowlist_enabled") or "0") == "1",
        "ip_allowlist": get("security_ip_allowlist") or "",
    }


def set_security(data):
    """Validate and persist security settings."""
    try:
        attempts = int(data.get("max_login_attempts", 8))
        lockout = int(data.get("lockout_minutes", 5))
        hours = int(data.get("session_hours", 12))
    except (TypeError, ValueError) as exc:
        raise ValueError("Security numbers must be integers") from exc

    if not 3 <= attempts <= 20:
        raise ValueError("Max login attempts must be between 3 and 20")
    if not 1 <= lockout <= 60:
        raise ValueError("Lockout must be between 1 and 60 minutes")
    if not 1 <= hours <= 72:
        raise ValueError("Session timeout must be between 1 and 72 hours")

    enabled = bool(data.get("ip_allowlist_enabled"))
    raw_list = (data.get("ip_allowlist") or "").strip()
    if enabled and not raw_list:
        raise ValueError("Add at least one IP or subnet before enabling the allowlist")

    from ..security import parse_allowlist

    for entry in parse_allowlist(raw_list):
        if "/" in entry:
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError as exc:
                raise ValueError(f"Invalid subnet: {entry}") from exc
        elif entry.endswith("."):
            continue
        else:
            try:
                ipaddress.ip_address(entry)
            except ValueError as exc:
                raise ValueError(f"Invalid IP address: {entry}") from exc

    set("security_max_login_attempts", str(attempts))
    set("security_lockout_minutes", str(lockout))
    set("security_session_hours", str(hours))
    set("security_ip_allowlist_enabled", "1" if enabled else "0")
    set("security_ip_allowlist", raw_list[:4000])
