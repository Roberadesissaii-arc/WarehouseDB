"""Web-triggered install of the sibling apps (Store / Scan) — no root.

The WarehouseDB service runs as an unprivileged user. These installs only ever
run that user's own tools (git + the app's `install.sh --web`, which never calls
sudo), so the public web app can never escalate to root. The add-on apps run as
per-user systemd services.
"""
import os
import subprocess
import threading
from pathlib import Path

_WH_ROOT = Path(__file__).resolve().parent.parent      # .../WarehouseDB
_PARENT = _WH_ROOT.parent                              # the projects dir
_GH = "https://github.com/Roberadesissaii-arc"

ADDONS = {
    "store": {"name": "Warehouse Store", "dir": "Warehouse_store", "repo": f"{_GH}/Warehouse_store.git"},
    "scan": {"name": "Warehouse Scan", "dir": "Warehouse_scan", "repo": f"{_GH}/Warehouse_scan.git"},
}

_lock = threading.Lock()
_status: dict = {}


def get_status(addon_id: str) -> dict:
    with _lock:
        return dict(_status.get(addon_id) or {"state": "idle", "message": "", "url": None})


def _set(addon_id: str, **kw) -> None:
    with _lock:
        cur = _status.setdefault(addon_id, {"state": "idle", "message": "", "url": None})
        cur.update(kw)


def start_install(addon_id: str) -> dict:
    if addon_id not in ADDONS:
        raise ValueError("unknown app")
    with _lock:
        cur = _status.get(addon_id)
        if cur and cur.get("state") == "installing":
            return dict(cur)
        _status[addon_id] = {"state": "installing", "message": "Starting…", "url": None}
    threading.Thread(target=_run, args=(addon_id,), daemon=True).start()
    return get_status(addon_id)


def _tail(text: str, n: int = 6) -> str:
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return " · ".join(lines[-n:])


def _run(addon_id: str) -> None:
    info = ADDONS[addon_id]
    target = _PARENT / info["dir"]
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    try:
        if not (target / "install.sh").exists():
            _set(addon_id, message="Downloading…")
            r = subprocess.run(
                ["git", "clone", "--depth=1", info["repo"], str(target)],
                capture_output=True, text=True, timeout=600,
            )
            if r.returncode != 0:
                _set(addon_id, state="error", message=_tail(r.stderr or r.stdout) or "Download failed")
                return
        _set(addon_id, message="Installing & building (1–3 min)…")
        r = subprocess.run(
            ["bash", str(target / "install.sh"), "--web"],
            cwd=str(target), capture_output=True, text=True, timeout=1800, env=env,
        )
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        if r.returncode != 0:
            _set(addon_id, state="error", message=_tail(out) or "Install failed")
            return
        url = None
        for line in out.splitlines():
            if line.startswith("WEB_INSTALL_OK"):
                parts = line.split(None, 1)
                url = parts[1].strip() if len(parts) > 1 else None
        _set(addon_id, state="done", message="Installed and running.", url=url)
    except subprocess.TimeoutExpired:
        _set(addon_id, state="error", message="Timed out — check the server logs.")
    except Exception as exc:  # noqa: BLE001
        _set(addon_id, state="error", message=f"Install error: {exc}")
