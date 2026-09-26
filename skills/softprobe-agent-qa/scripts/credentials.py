"""Explorer user credentials under ~/.softprobe/explorer/ (stdlib only)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

CREDENTIALS_DIR = Path.home() / ".softprobe" / "explorer"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
DEFAULT_EXPLORER_BASE = "https://explorer.softprobe.ai"


class MissingCredentialsError(RuntimeError):
    """Raised when Explorer credentials are missing or unusable."""


def credentials_path() -> Path:
    override = os.environ.get("SOFTPROBE_EXPLORER_CREDENTIALS")
    if override and override.strip():
        return Path(override.strip()).expanduser()
    return CREDENTIALS_FILE


def load_credentials() -> dict[str, Any]:
    env_token = os.environ.get("SOFTPROBE_EXPLORER_TOKEN", "").strip()
    if env_token:
        return {
            "access_token": env_token,
            "refresh_token": os.environ.get("SOFTPROBE_EXPLORER_REFRESH_TOKEN", "").strip() or None,
            "expires_at": None,
            "explorer_base": os.environ.get("SOFTPROBE_EXPLORER_BASE", DEFAULT_EXPLORER_BASE),
        }

    path = credentials_path()
    if not path.is_file():
        raise MissingCredentialsError(
            f"No Explorer credentials at {path}. Ask the human to run: "
            "python3 skills/softprobe-agent-qa/scripts/login.py"
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not str(raw.get("access_token") or "").strip():
        raise MissingCredentialsError(f"Invalid credentials file: {path}")
    return raw


def save_credentials(
    *,
    access_token: str,
    refresh_token: str | None = None,
    expires_at: int | float | None = None,
    email: str | None = None,
    explorer_base: str = DEFAULT_EXPLORER_BASE,
) -> Path:
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": access_token.strip(),
        "refresh_token": (refresh_token or "").strip() or None,
        "expires_at": int(expires_at) if expires_at else None,
        "email": (email or "").strip() or None,
        "explorer_base": explorer_base.rstrip("/"),
        "updated_at": int(time.time()),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    return path


def access_token_near_expiry(creds: dict[str, Any], skew_sec: int = 120) -> bool:
    expires_at = creds.get("expires_at")
    if expires_at is None:
        return False
    try:
        return int(expires_at) <= int(time.time()) + skew_sec
    except (TypeError, ValueError):
        return False


def mask_token(token: str) -> str:
    t = token.strip()
    if len(t) <= 12:
        return "***"
    return f"{t[:6]}…{t[-4:]}"
