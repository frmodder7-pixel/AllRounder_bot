"""Shared Gemini helper. Used by the AI brain AND by /joke, /shayari etc.
to generate unlimited fresh content. Returns None on any failure so callers
can fall back to built-in content."""
import logging
import time
from collections import defaultdict, deque
from base64 import b64decode, b64encode
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


def _image_model_name() -> str:
    return _clean_model(config.GEMINI_IMAGE_MODEL)


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


def _extract_image(data: dict) -> Optional[tuple[bytes, str]]:
    for candidate in data.get("candidates", []):
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if not inline:
                continue
            raw = inline.get("data")
            mime_type = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            if raw:
                return b64decode(raw), mime_type
    return None


async def generate_image(prompt: str) -> Optional[tuple[bytes, str]]:
    """Generate an image with Gemini and return (bytes, mime_type), or None."""
    if not config.GEMINI_API_KEY:
        _remember_error("GEMINI_API_KEY is not set")
        return None
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": config.GEMINI_API_KEY,
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    model = _image_model_name()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as c:
            r = await c.post(_url(model), headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        image = _extract_image(data)
        if image:
            _remember_error("")
            return image
        _remember_error("image response had no image data")
        log.warning("Gemini image request returned no image: model=%s", model)
    except httpx.HTTPStatusError as exc:
        error = f"HTTP {exc.response.status_code}: {_api_error(exc.response)}"
        _remember_error(error)
        log.warning("Gemini image request failed: model=%s %s", model, error)
    except httpx.TimeoutException:
        _remember_error("image request timed out")
        log.warning("Gemini image request timed out: model=%s", model)
    except Exception as exc:
        _remember_error(type(exc).__name__)
        log.exception("Gemini image request failed unexpectedly: model=%s", model)
    return None


async def edit_image(prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[tuple[bytes, str]]:
    """Edit/restyle an image with Gemini and return (bytes, mime_type), or None."""
    if not config.GEMINI_API_KEY:
        _remember_error("GEMINI_API_KEY is not set")
        return None
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": config.GEMINI_API_KEY,
    }
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": mime_type, "data": b64encode(image_bytes).decode("ascii")}},
            ]
        }],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    model = _image_model_name()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as c:
            r = await c.post(_url(model), headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        image = _extract_image(data)
        if image:
            _remember_error("")
            return image
        _remember_error("edited image response had no image data")
        log.warning("Gemini image edit returned no image: model=%s", model)
    except httpx.HTTPStatusError as exc:
        error = f"HTTP {exc.response.status_code}: {_api_error(exc.response)}"
        _remember_error(error)
        log.warning("Gemini image edit failed: model=%s %s", model, error)
    except httpx.TimeoutException:
        _remember_error("image edit request timed out")
        log.warning("Gemini image edit timed out: model=%s", model)
    except Exception as exc:
        _remember_error(type(exc).__name__)
        log.exception("Gemini image edit failed unexpectedly: model=%s", model)
    return None
