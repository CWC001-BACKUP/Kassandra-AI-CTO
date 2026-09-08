"""OpenAI-compatible chat completion client."""

from __future__ import annotations

import logging

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    def __init__(self, message: str, status_code: int = 503):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def is_llm_configured(settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    return bool(cfg.llm_api_key and cfg.llm_base_url and cfg.llm_model)


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    settings: Settings | None = None,
) -> str:
    """Send a chat completion request to an OpenAI-compatible API."""
    cfg = settings or get_settings()
    if not is_llm_configured(cfg):
        raise LLMError(
            "LLM is not configured. Set LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL in .env",
            503,
        )

    base = cfg.llm_base_url.rstrip("/")
    url = f"{base}/chat/completions"

    payload = {
        "model": cfg.llm_model,
        "messages": messages,
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {cfg.llm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.exception("LLM request failed")
        raise LLMError("Could not reach the LLM provider", 503) from exc

    if response.status_code != 200:
        detail = response.text[:300]
        logger.warning("LLM error %s: %s", response.status_code, detail)
        raise LLMError(f"LLM provider returned {response.status_code}", 502)

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("Unexpected LLM response format", 502) from exc
