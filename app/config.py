"""Settings loaded from the project .env file or environment variables."""

import os
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

def server_url(name):
    value = os.getenv(name, "").strip().rstrip("/")
    if not value:
        return ""
    parsed = urlsplit(value)
    if (any(character.isspace() for character in value) or "\\" in value
            or parsed.scheme != "https"
            or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        raise ValueError(f"{name} must be an HTTPS origin without a path or credentials")
    try:
        parsed.port
    except ValueError as error:
        raise ValueError(f"{name} has an invalid port") from error
    return value


ONLINE_URL = server_url("NETDROP_ONLINE_URL")
if not ONLINE_URL:
    raise ValueError("NETDROP_ONLINE_URL is required and must be the public HTTPS address")
