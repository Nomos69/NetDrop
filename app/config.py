"""Settings loaded from the project .env file or environment variables."""

import os
import ipaddress
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = (Path(os.getenv("LOCALAPPDATA", Path.home() / ".local")) / "NetDrop"
            if getattr(sys, "frozen", False) else BASE_DIR / "data")
load_dotenv((DATA_DIR if getattr(sys, "frozen", False) else BASE_DIR) / ".env")


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

STATIC_DIR = BUNDLE_DIR / "static"
UPLOAD_DIR = DATA_DIR / "uploads"
FILE_TTL_SECONDS = positive_integer("NETDROP_FILE_TTL_SECONDS", 1800)
MAX_UPLOAD_BYTES = positive_integer("NETDROP_MAX_UPLOAD_BYTES", 50_000_000)

ROOM_TTL_SECONDS = positive_integer("NETDROP_ROOM_TTL_SECONDS", 3 * 24 * 60 * 60)
INVITATION_TTL_SECONDS = positive_integer("NETDROP_INVITATION_TTL_SECONDS", 24 * 60 * 60)

# Brevo HTTPS API credentials stay on the server; SMTP keys do not work here.
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "").strip()
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "NetDrop").strip() or "NetDrop"

CLEANUP_INTERVAL_SECONDS = positive_integer("NETDROP_CLEANUP_INTERVAL_SECONDS", 5)

# Each server owns its rooms. Switching mode opens the corresponding server.
SHARING_MODE = os.getenv("NETDROP_SHARING_MODE", "online").strip().lower()
if SHARING_MODE not in {"local", "online"}:
    raise ValueError("NETDROP_SHARING_MODE must be local or online")

LOCAL_DISCOVERY = os.getenv("NETDROP_LOCAL_DISCOVERY", "1").strip().lower() in {"1", "true", "yes"}


def lan_hostname(name):
    value = os.getenv(name, "").strip()
    if not value:
        return ""
    if "." in value or not value.replace("-", "").isalnum():
        raise ValueError(f"{name} must be a single mDNS label without dots")
    if value.startswith("-") or value.endswith("-"):
        raise ValueError(f"{name} must not start or end with a hyphen")
    return value


LAN_HOSTNAME = lan_hostname("NETDROP_LAN_HOSTNAME")


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

def https_download_url(name, default):
    value = os.getenv(name, default).strip()
    parsed = urlsplit(value)
    if (any(character.isspace() for character in value) or "\\" in value
            or parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password):
        raise ValueError(f"{name} must be an HTTPS URL")
    try:
        parsed.port
    except ValueError as error:
        raise ValueError(f"{name} has an invalid port") from error
    return value


LOCAL_INSTALLER_URL = https_download_url(
    "NETDROP_LOCAL_INSTALLER_URL",
    "https://github.com/Nomos69/NetDrop/releases/latest/download/NetDrop-Local-Setup.exe",
)
UBUNTU_INSTALLER_URL = https_download_url(
    "NETDROP_UBUNTU_INSTALLER_URL",
    "https://github.com/Nomos69/NetDrop/releases/latest/download/NetDrop-Local-Ubuntu.deb",
)


def sharing_mode(request):
    """Public hosts use online mode; private and local hosts use the configured mode."""
    hostname = request.url.hostname or ""
    try:
        public_host = ipaddress.ip_address(hostname).is_global
    except ValueError:
        public_host = hostname != "localhost" and "." in hostname and not hostname.endswith((".local", ".lan", ".localhost"))
    return "online" if public_host else SHARING_MODE


def local_origin(request):
    return LOCAL_URL or str(request.base_url).rstrip("/")
