"""Robot firmware catalog — latest release shipped with WarehouseDB."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST = _ROOT / "Arduino" / "firmware.json"


def _parse_version(raw: str | None) -> tuple[int, ...]:
    if not raw:
        return ()
    parts: list[int] = []
    for chunk in str(raw).strip().split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def update_available(installed: str | None, latest: str | None) -> bool:
    if not latest:
        return False
    if not installed:
        return True
    return _parse_version(installed) < _parse_version(latest)


@lru_cache(maxsize=1)
def _load_manifest() -> dict:
    if not _MANIFEST.is_file():
        return {}
    try:
        data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def latest_release() -> dict:
    """Latest firmware metadata from Arduino/firmware.json."""
    data = _load_manifest()
    version = (data.get("version") or "").strip() or None
    return {
        "version": version,
        "released_at": data.get("released_at"),
        "notes": data.get("notes") or "",
        "sketch_root": data.get("sketch_root") or "Arduino",
    }


def sketch_folder(unit_code: str | None) -> str:
    code = (unit_code or "unknown").strip() or "unknown"
    root = latest_release()["sketch_root"]
    return f"{root}/WarehouseDB_{code}"


def robot_firmware_status(installed: str | None, unit_code: str | None) -> dict:
    latest = latest_release()
    latest_ver = latest["version"]
    return {
        "installed": installed or None,
        "latest": latest_ver,
        "update_available": update_available(installed, latest_ver),
        "released_at": latest.get("released_at"),
        "notes": latest.get("notes") or "",
        "sketch_folder": sketch_folder(unit_code),
    }
