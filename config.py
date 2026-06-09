"""Central configuration. All secrets come from environment variables
so nothing sensitive is ever committed to GitHub."""
import os


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

# Render injects PORT; the keep-alive web server binds to it.
PORT = _int("PORT", 10000)

# How many warns before an auto-ban.
WARN_LIMIT = _int("WARN_LIMIT", 3)

# Branding shown across the bot.
BRAND = "All Rounder Bot"
TAG = "by BLITEX"
SIGNATURE = f"— <b>{BRAND}</b> ✨ <i>{TAG}</i>"
