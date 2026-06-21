"""Warehouse Relay — optional Cloudflare Tunnel (cloudflared) for a public warehouse URL.

When cloudflared is installed and relay is enabled in settings, WarehouseDB starts a
tunnel to this server. Quick tunnels get a random *.trycloudflare.com URL for the
process lifetime; named tunnels (e.g. ``warehouse`` from install) use a fixed hostname.
"""
from __future__ import annotations

import atexit
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, has_app_context

_TUNNEL_URL_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
_HOSTNAME_RE = re.compile(r"^\s*hostname:\s*(\S+)\s*$", re.MULTILINE)
_DEFAULT_TUNNEL_NAME = "warehouse"

_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_reader: threading.Thread | None = None
_state = {
    "running": False,
    "url": None,
    "mode": None,
    "tunnel_name": None,
    "error": None,
    "started_at": None,
}


_CLOUDFLARED_CANDIDATES = (
    "/usr/local/bin/cloudflared",
    "/usr/bin/cloudflared",
    "/bin/cloudflared",
    "/snap/bin/cloudflared",
)


def cloudflared_bin() -> str | None:
    """Absolute path to the cloudflared binary, or None if not found.

    A systemd service runs with a minimal PATH that usually excludes
    ``~/.local/bin``, so after checking PATH we also probe well-known
    install locations — otherwise the relay reports "not installed" even
    though cloudflared exists on the machine.
    """
    found = shutil.which("cloudflared")
    if found:
        return found
    candidates = [
        *_CLOUDFLARED_CANDIDATES,
        os.path.join(os.path.expanduser("~"), ".local", "bin", "cloudflared"),
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def cloudflared_installed() -> bool:
    return cloudflared_bin() is not None


def cloudflared_version() -> str | None:
    binary = cloudflared_bin()
    if not binary:
        return None
    try:
        out = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        line = (out.stdout or out.stderr or "").strip().splitlines()
        return line[0] if line else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _config_dir() -> Path:
    return Path.home() / ".cloudflared"


def _tunnel_name() -> str:
    return (os.environ.get("RELAY_TUNNEL_NAME") or _DEFAULT_TUNNEL_NAME).strip() or _DEFAULT_TUNNEL_NAME


def _named_tunnel_ready(name: str) -> bool:
    cred = _config_dir() / f"{name}.json"
    if cred.is_file():
        return True
    cfg = _config_dir() / "config.yml"
    if not cfg.is_file():
        return False
    try:
        text = cfg.read_text(encoding="utf-8")
    except OSError:
        return False
    return re.search(rf"^\s*tunnel:\s*{re.escape(name)}\s*$", text, re.MULTILINE) is not None


def _named_hostname(name: str) -> str | None:
    env_host = (os.environ.get("RELAY_PUBLIC_HOSTNAME") or "").strip()
    if env_host:
        return env_host.lstrip("https://").lstrip("http://").rstrip("/")
    cfg = _config_dir() / "config.yml"
    if not cfg.is_file():
        return None
    try:
        text = cfg.read_text(encoding="utf-8")
    except OSError:
        return None
    if not re.search(rf"^\s*tunnel:\s*{re.escape(name)}\s*$", text, re.MULTILINE):
        return None
    match = _HOSTNAME_RE.search(text)
    return match.group(1) if match else None


def _local_target() -> str:
    port = 8000
    if has_app_context():
        port = int(current_app.config.get("PORT") or 8000)
    return f"http://127.0.0.1:{port}"


def _reset_runtime(error: str | None = None) -> None:
    _state["running"] = False
    _state["url"] = None
    _state["mode"] = None
    _state["tunnel_name"] = None
    _state["started_at"] = None
    if error is not None:
        _state["error"] = error


def _set_url(url: str) -> None:
    _state["url"] = url
    _state["error"] = None


def _read_process_output(proc: subprocess.Popen, mode: str, fixed_url: str | None) -> None:
    if fixed_url:
        _set_url(fixed_url if fixed_url.startswith("http") else f"https://{fixed_url}")
        return
    stream = proc.stderr or proc.stdout
    if not stream:
        return
    for raw in stream:
        if not raw:
            break
        line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        match = _TUNNEL_URL_RE.search(line)
        if match:
            _set_url(match.group(0))
            return
    if proc.poll() is not None and proc.returncode not in (None, 0):
        _state["error"] = f"cloudflared exited ({proc.returncode})"


def _spawn(mode: str, args: list[str], fixed_url: str | None = None) -> None:
    global _proc, _reader
    stop()
    if not cloudflared_installed():
        _reset_runtime("cloudflared is not installed on this server")
        return

    popen_kwargs: dict = {
        "args": args,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        proc = subprocess.Popen(**popen_kwargs)
    except OSError as exc:
        _reset_runtime(str(exc))
        return

    _proc = proc
    _state["running"] = True
    _state["mode"] = mode
    _state["error"] = None
    _state["started_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if fixed_url:
        _set_url(fixed_url if fixed_url.startswith("http") else f"https://{fixed_url}")

    def _watch() -> None:
        _read_process_output(proc, mode, fixed_url)
        code = proc.wait()
        with _lock:
            if _proc is proc:
                _proc = None
                if code not in (0, None) and not _state["url"]:
                    _state["error"] = _state["error"] or f"cloudflared stopped ({code})"
                _state["running"] = False

    _reader = threading.Thread(target=_watch, name="warehouse-relay", daemon=True)
    _reader.start()


def start() -> None:
    """Start cloudflared when relay is enabled."""
    with _lock:
        if _proc and _proc.poll() is None:
            return
        binary = cloudflared_bin()
        if not binary:
            _reset_runtime("cloudflared is not installed — run deploy/install.sh or install it manually")
            return

        target = _local_target()
        name = _tunnel_name()
        if _named_tunnel_ready(name):
            host = _named_hostname(name)
            fixed = f"https://{host}" if host else None
            _state["tunnel_name"] = name
            _spawn("named", [binary, "tunnel", "run", name, "--no-autoupdate"], fixed_url=fixed)
            return

        _state["tunnel_name"] = None
        _spawn(
            "quick",
            [binary, "tunnel", "--url", target, "--no-autoupdate"],
            fixed_url=None,
        )


def stop() -> None:
    """Stop the managed cloudflared process."""
    global _proc, _reader
    with _lock:
        proc = _proc
        _proc = None
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=6)
            except subprocess.TimeoutExpired:
                proc.kill()
        _reader = None
        _reset_runtime()


def apply_enabled(enabled: bool) -> None:
    if enabled:
        start()
    else:
        stop()
        _state["error"] = None


def sync_with_settings() -> None:
    """Apply saved relay preference on app startup."""
    from .models import setting

    apply_enabled(setting.relay_enabled())


def get_status() -> dict:
    """Public relay status for settings UI and API."""
    from .models import setting

    enabled = setting.relay_enabled()
    installed = cloudflared_installed()
    name = _tunnel_name()
    named_ready = installed and _named_tunnel_ready(name)
    hostname = _named_hostname(name) if named_ready else None

    with _lock:
        running = bool(_proc and _proc.poll() is None)
        url = _state.get("url")
        mode = _state.get("mode")
        error = _state.get("error")
        started_at = _state.get("started_at")
        active_name = _state.get("tunnel_name")

    if enabled and installed and running and not url and mode == "quick":
        error = error or "Waiting for Cloudflare to assign a public URL…"
    if enabled and not installed:
        error = "Install cloudflared on this server to enable Warehouse Relay (see deploy/CLOUDFLARE-TUNNEL.md)."

    if mode == "named" and hostname and not url:
        url = f"https://{hostname}"

    locked = mode == "named" and bool(hostname or url)

    return {
        "enabled": enabled,
        "installed": installed,
        "version": cloudflared_version(),
        "running": running,
        "url": url,
        "url_locked": locked,
        "mode": mode or ("named" if named_ready else None),
        "tunnel_name": active_name or (name if named_ready else None),
        "named_tunnel_ready": named_ready,
        "expected_hostname": hostname,
        "error": error,
        "started_at": started_at,
        "local_target": _local_target() if has_app_context() else None,
        "help": (
            "Quick tunnel: random *.trycloudflare.com address for this server run — "
            "restarts when WarehouseDB restarts. Named tunnel (warehouse): fixed domain from install."
        ),
    }


def _shutdown() -> None:
    stop()


atexit.register(_shutdown)
