"""Host and database diagnostics for the System settings page."""
import ctypes
import os
import platform
import shutil
import sys
import time
from pathlib import Path

from flask import current_app


def _fmt_bytes(n):
    if n is None:
        return "—"
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _memory_stats():
    if sys.platform == "win32":
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return None
            total = int(stat.ullTotalPhys)
            avail = int(stat.ullAvailPhys)
            used = max(0, total - avail)
            pct = round(used * 100 / total) if total else 0
            return {"total_bytes": total, "used_bytes": used, "percent": pct}
        except Exception:
            return None

    if sys.platform == "linux":
        try:
            info = {}
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    key, val = line.split(":", 1)
                    info[key.strip()] = int(val.strip().split()[0]) * 1024
            total = info.get("MemTotal")
            avail = info.get("MemAvailable", info.get("MemFree"))
            if not total or avail is None:
                return None
            used = max(0, total - avail)
            return {
                "total_bytes": total,
                "used_bytes": used,
                "percent": round(used * 100 / total) if total else 0,
            }
        except OSError:
            return None
    return None


def _disk_stats(path):
    try:
        usage = shutil.disk_usage(path)
        used = usage.total - usage.free
        pct = round(used * 100 / usage.total) if usage.total else 0
        return {
            "total_bytes": usage.total,
            "used_bytes": used,
            "free_bytes": usage.free,
            "percent": pct,
        }
    except OSError:
        return None


def _file_size(path):
    try:
        return os.path.getsize(path) if path and os.path.isfile(path) else 0
    except OSError:
        return 0


def collect():
    """Return host + database snapshot for staff system overview."""
    cfg = current_app.config
    db_path = cfg.get("DATABASE") or ""
    db_file = Path(db_path)
    db_dir = str(db_file.parent) if db_file.parent else "."
    started = cfg.get("STARTED_AT", time.time())
    uptime = max(0, int(time.time() - started))
    memory = _memory_stats()
    disk = _disk_stats(db_dir)
    wal_path = f"{db_path}-wal"
    db_bytes = _file_size(db_path)
    wal_bytes = _file_size(wal_path)

    os_name = platform.system()
    os_release = platform.release()
    return {
        "host": {
            "hostname": platform.node(),
            "platform": f"{os_name} {os_release}".strip(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "cpu_cores": os.cpu_count() or 1,
            "uptime_seconds": uptime,
            "flask_env": os.environ.get("FLASK_ENV", "development"),
            "debug": bool(cfg.get("DEBUG")),
            "bind": f"{cfg.get('HOST', '0.0.0.0')}:{cfg.get('PORT', 8000)}",
            "memory": memory,
            "disk": disk,
        },
        "database": {
            "path": db_path,
            "size_bytes": db_bytes,
            "wal_bytes": wal_bytes,
            "total_bytes": db_bytes + wal_bytes,
            "size_label": _fmt_bytes(db_bytes + wal_bytes),
        },
        "formats": {
            "memory": _fmt_bytes(memory["used_bytes"]) + f" / {_fmt_bytes(memory['total_bytes'])}"
            if memory else None,
            "disk_free": _fmt_bytes(disk["free_bytes"]) if disk else None,
            "disk_total": _fmt_bytes(disk["total_bytes"]) if disk else None,
        },
    }
