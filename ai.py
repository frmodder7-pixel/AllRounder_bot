"""Shared Gemini helper. Used by the AI brain AND by /joke, /shayari etc.
to generate unlimited fresh content. Returns None on any failure so callers
can fall back to built-in content."""
import httpx

import config

_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)


def is_enabled() -> bool:
    return bool(config.GEMINI_API_KEY)


async def ask(prompt: str, max_tokens: int = 400, temperature: float = 0.9):
    """Call Gemini and return text, or None if it's disabled/fails."""
    if not config.GEMINI_API_KEY:
        return None
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as c:
            r = await c.post(f"{_URL}?key={config.GEMINI_API_KEY}", json=payload)
            r.raise_for_status()
            data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None
