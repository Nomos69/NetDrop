"""Settings loaded from the project .env file or environment variables."""

import os
from pathlib import Path

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

CLEANUP_INTERVAL_SECONDS = positive_integer("NETDROP_CLEANUP_INTERVAL_SECONDS", 5)
