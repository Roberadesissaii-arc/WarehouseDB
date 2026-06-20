"""Application configuration.

Select via the FLASK_ENV environment variable ("development" | "production").
Defaults to development.
"""
import os
from datetime import timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _load_local_env() -> None:
    """Load root .env or instance/warehousedb.env (existing env vars win)."""
    for env_path in (_ROOT / ".env", _ROOT / "instance" / "warehousedb.env"):
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if not key:
                continue
            os.environ.setdefault(key, val.strip().strip('"').strip("'"))


_load_local_env()


# Insecure defaults that must never reach production — see _register_security().
DEFAULT_SECRET_KEY = "dev-secret-change-me"
DEFAULT_STORE_API_KEY = "store-dev-key"
DEFAULT_SCAN_API_KEY = "scan-dev-key"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", DEFAULT_SECRET_KEY)
    DATABASE = os.environ.get("DATABASE")
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "8000"))
    STORE_API_KEY = os.environ.get("STORE_API_KEY", DEFAULT_STORE_API_KEY)
    SCAN_API_KEY = os.environ.get("SCAN_API_KEY", DEFAULT_SCAN_API_KEY)
    # Number of trusted reverse-proxy hops in front of the app. 0 (default) means
    # the app is reached directly, so X-Forwarded-For is NOT trusted. Set to 1
    # only when behind a proxy that overwrites X-Forwarded-For (e.g. Cloudflare).
    TRUST_PROXY_HOPS = int(os.environ.get("TRUST_PROXY", "0") or "0")
    SCAN_PUBLIC_URL = os.environ.get("SCAN_PUBLIC_URL", "http://localhost:5002").rstrip("/")
    DEBUG = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    # LAN warehouses often run HTTP on a private network — set SESSION_COOKIE_SECURE=true only behind HTTPS.
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "").lower() in ("1", "true", "yes")


_CONFIGS = {"development": DevelopmentConfig, "production": ProductionConfig}


def get_config():
    env = os.environ.get("FLASK_ENV", "development").lower()
    return _CONFIGS.get(env, DevelopmentConfig)
