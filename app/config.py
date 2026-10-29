"""Settings loaded from the project .env file or environment variables."""

import os
import ipaddress
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def positive_integer(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


HOST = os.getenv("NETDROP_HOST", "0.0.0.0").strip()
if not HOST:
    raise ValueError("NETDROP_HOST must not be empty")
PORT = positive_integer("NETDROP_PORT", 8000)
if PORT > 65535:
    raise ValueError("NETDROP_PORT must be between 1 and 65535")

STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
FILE_TTL_SECONDS = positive_integer("NETDROP_FILE_TTL_SECONDS", 1800)
MAX_UPLOAD_BYTES = positive_integer("NETDROP_MAX_UPLOAD_MB", 100) * 1024 * 1024

ROOM_IDLE_SECONDS = positive_integer("NETDROP_ROOM_IDLE_SECONDS", 1800)

CLEANUP_INTERVAL_SECONDS = positive_integer("NETDROP_CLEANUP_INTERVAL_SECONDS", 5)

# Each server owns its rooms. Switching mode opens the corresponding server.
SHARING_MODE = os.getenv("NETDROP_SHARING_MODE", "local").strip().lower()
if SHARING_MODE not in {"local", "online"}:
    raise ValueError("NETDROP_SHARING_MODE must be local or online")


def server_url(name, online=False):
    value = os.getenv(name, "").strip().rstrip("/")
    if not value:
        return ""
    parsed = urlsplit(value)
    if (any(character.isspace() for character in value) or "\\" in value
            or parsed.scheme not in ({"https"} if online else {"http", "https"})
            or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        raise ValueError(f"{name} must be a {'HTTPS' if online else 'HTTP(S)'} origin without a path or credentials")
    try:
        parsed.port
    except ValueError as error:
        raise ValueError(f"{name} has an invalid port") from error
    return value


LOCAL_URL = server_url("NETDROP_LOCAL_URL")
ONLINE_URL = server_url("NETDROP_ONLINE_URL", online=True)
if SHARING_MODE == "online" and not ONLINE_URL:
    raise ValueError("Online mode requires NETDROP_ONLINE_URL with the public HTTPS address")


def sharing_mode(request):
    """Public HTTPS deployments work even before optional addresses are set."""
    hostname = request.url.hostname or ""
    try:
        public_host = ipaddress.ip_address(hostname).is_global
    except ValueError:
        public_host = hostname != "localhost" and "." in hostname and not hostname.endswith((".local", ".lan", ".localhost"))
    return "online" if request.url.scheme == "https" and public_host else SHARING_MODE
