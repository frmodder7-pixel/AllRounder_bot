"""Central configuration. All secrets come from environment variables
so nothing sensitive is ever committed to GitHub."""
import os
from pathlib import Path


def _load_local_env() -> None:
    """Load .env during local runs without overriding real environment vars."""
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip().lstrip("\ufeff")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key:
            os.environ.setdefault(key, value)


_load_local_env()


def _int(name: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(name, default) or default)
    except (TypeError, ValueError):
        return default


# Required
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# Your personal Telegram user id (get it by sending /id to the bot).
# Owner-only commands (/stats, /broadcast) check against this.
OWNER_ID = _int("OWNER_ID")

# Optional: free key from https://aistudio.google.com/app/apikey
# If set, the bot gains an AI brain (mention it or reply to it).
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image-preview").strip() or "gemini-2.5-flash-image-preview"
GEMINI_FALLBACK_MODELS = [
    model.strip()
    for model in os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-1.5-flash").split(",")
    if model.strip()
]

# Optional: free key from https://cricketdata.org for live /cricket scores.
CRICKET_API_KEY = os.environ.get("CRICKET_API_KEY", "").strip()

# Railway/Render inject PORT; the keep-alive web server binds to it.
PORT = _int("PORT", 10000)

# How many warns before an auto-ban.
WARN_LIMIT = _int("WARN_LIMIT", 3)

# Branding shown across the bot.
BRAND = "All Rounder Bot"
TAG = "by BLITEX"
SIGNATURE = f"— <b>{BRAND}</b> ✨ <i>{TAG}</i>"
