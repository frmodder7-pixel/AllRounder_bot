"""Shared Gemini helper. Used by the AI brain AND by /joke, /shayari etc.
to generate unlimited fresh content. Returns None on any failure so callers
can fall back to built-in content."""
import logging
import time
from collections import defaultdict, deque
from typing import Optional
from urllib.parse import quote

import httpx

import config

log = logging.getLogger("allrounder.ai")
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_LAST_ERROR: Optional[str] = None
_ACTIVE_MODEL: Optional[str] = None
_RATE_LIMITS = defaultdict(deque)


def is_enabled() -> bool:
    return bool(config.GEMINI_API_KEY)


def last_error() -> Optional[str]:
    return _LAST_ERROR


def allow_request(key: str, limit: int = 6, period: int = 60) -> bool:
    """Small in-memory limiter for Gemini calls."""
    now = time.monotonic()
    bucket = _RATE_LIMITS[key]
    while bucket and now - bucket[0] > period:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def _remember_error(message: str) -> None:
    global _LAST_ERROR
    _LAST_ERROR = message


def _model_name() -> str:
    model = (config.GEMINI_MODEL or "gemini-2.5-flash").strip()
    if model.startswith("models/"):
        model = model.split("/", 1)[1]
    return model


def active_model() -> str:
    return _ACTIVE_MODEL or _model_name()


def _clean_model(model: str) -> str:
    model = (model or "").strip()
    if model.startswith("models/"):
        model = model.split("/", 1)[1]
    return model


def _candidate_models() -> list[str]:
    models = [_clean_model(active_model()), _clean_model(config.GEMINI_MODEL)]
    models.extend(_clean_model(model) for model in config.GEMINI_FALLBACK_MODELS)
    seen = set()
    return [model for model in models if model and not (model in seen or seen.add(model))]


def _url(model: str) -> str:
    return f"{_BASE_URL}/{quote(model, safe='-_.')}:generateContent"


def _extract_text(data: dict) -> Optional[str]:
    for candidate in data.get("candidates", []):
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if text.strip():
            return text.strip()
    return None


def _api_error(response: httpx.Response) -> str:
    try:
        data = response.json()
        return (data.get("error") or {}).get("message") or response.text[:300]
    except Exception:
        return response.text[:300]


def _should_try_next_model(status_code: int, message: str) -> bool:
    if status_code in (400, 403, 404):
        lowered = message.lower()
        return any(word in lowered for word in ("model", "not found", "unsupported", "permission"))
    return False


async def ask(prompt: str, max_tokens: int = 400, temperature: float = 0.9):
    """Call Gemini and return text, or None if it's disabled/fails."""
    if not config.GEMINI_API_KEY:
        _remember_error("GEMINI_API_KEY is not set")
        return None
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": config.GEMINI_API_KEY,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as c:
        for model in _candidate_models():
            try:
                r = await c.post(_url(model), headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
                text = _extract_text(data)
                if text:
                    global _ACTIVE_MODEL
                    _ACTIVE_MODEL = model
                    _remember_error("")
                    return text
                feedback = data.get("promptFeedback") or {}
                reason = feedback.get("blockReason") or "response had no text"
                _remember_error(str(reason))
                log.warning("Gemini returned no text: model=%s reason=%s", model, reason)
            except httpx.HTTPStatusError as exc:
                message = _api_error(exc.response)
                error = f"HTTP {exc.response.status_code}: {message}"
                _remember_error(error)
                log.warning("Gemini request failed: model=%s %s", model, error)
                if _should_try_next_model(exc.response.status_code, message):
                    continue
                return None
            except httpx.TimeoutException:
                _remember_error("request timed out")
                log.warning("Gemini request timed out: model=%s", model)
                return None
            except Exception as exc:
                _remember_error(type(exc).__name__)
                log.exception("Gemini request failed unexpectedly: model=%s", model)
                return None
    return None
