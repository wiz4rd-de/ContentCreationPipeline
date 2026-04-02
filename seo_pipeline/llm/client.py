"""Thin wrapper around litellm.completion() with structured output support."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any

from seo_pipeline.llm.config import LLMConfig

logger = logging.getLogger(__name__)

# Rate limiting — space calls to stay under provider limits
_MIN_CALL_INTERVAL = 15.0  # seconds between calls (60s / 5 req + grace)
_last_call_time: float = 0.0

# Retry settings — handles 429s that still slip through and transient errors
_MAX_RETRIES = 5
_DEFAULT_RATE_LIMIT_WAIT = 65.0  # token-based rate limits reset per minute
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}
_TRANSIENT_BACKOFF = 2.0  # initial backoff for 5xx errors

if TYPE_CHECKING:
    from pydantic import BaseModel


def _enforce_strict_schema(schema: Any) -> Any:
    """Recursively enforce strict JSON schema constraints.

    - Sets additionalProperties: false on all object schemas.
    - Ensures all properties are listed in required.
    Required by Anthropic's structured output API.
    """
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
            if "properties" in schema:
                schema["required"] = list(schema["properties"].keys())
        for value in schema.values():
            _enforce_strict_schema(value)
    elif isinstance(schema, list):
        for item in schema:
            _enforce_strict_schema(item)
    return schema


def _throttle() -> None:
    """Sleep if needed to respect _MIN_CALL_INTERVAL between LLM calls."""
    global _last_call_time
    now = time.monotonic()
    elapsed = now - _last_call_time
    if _last_call_time > 0 and elapsed < _MIN_CALL_INTERVAL:
        wait = _MIN_CALL_INTERVAL - elapsed
        logger.info("Rate-limiting: waiting %.1fs before next LLM call", wait)
        time.sleep(wait)
    _last_call_time = time.monotonic()


def _get_wait_seconds(exc: Exception, transient_backoff: float) -> float:
    """Determine how long to wait before retrying.

    For 429: use retry-after header if present, else _DEFAULT_RATE_LIMIT_WAIT.
    For 5xx: use exponential backoff.
    """
    status = getattr(exc, "status_code", None)
    if status == 429:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None) if response else None
        if headers:
            retry_after = headers.get("retry-after")
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        return _DEFAULT_RATE_LIMIT_WAIT
    return transient_backoff


def _completion_with_retry(litellm: Any, kwargs: dict) -> Any:
    """Call litellm.completion with retry on rate-limit and transient errors.

    429s wait for the retry-after duration (or 12s default).
    5xx errors use exponential backoff (2s, 4s, 8s, ...).
    """
    transient_backoff = _TRANSIENT_BACKOFF
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return litellm.completion(**kwargs)
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            if status not in _RETRYABLE_STATUS_CODES or attempt == _MAX_RETRIES:
                raise
            wait = _get_wait_seconds(exc, transient_backoff)
            logger.warning(
                "LLM call returned %s, waiting %.1fs before retry (attempt %d/%d)",
                status, wait, attempt, _MAX_RETRIES,
            )
            time.sleep(wait)
            if status != 429:
                transient_backoff *= 2
    raise RuntimeError("retry loop exited unexpectedly")


def complete(
    messages: list[dict],
    config: LLMConfig | None = None,
    response_model: type[BaseModel] | None = None,
) -> str | BaseModel:
    """Call an LLM via LiteLLM and return a string or validated Pydantic model.

    Args:
        messages: Chat messages (system/user/assistant dicts).
        config: LLM configuration. Loaded from env if None.
        response_model: If provided, parse the response as JSON and validate
            against this Pydantic model.

    Returns:
        Validated Pydantic model instance if response_model is given,
        otherwise the raw response string.

    Raises:
        ImportError: If litellm is not installed
            (install with ``pip install seo-pipeline[llm]``).
    """
    import litellm

    if config is None:
        config = LLMConfig.from_env()

    kwargs: dict = {
        "model": config.litellm_model(),
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }

    if config.api_key:
        kwargs["api_key"] = config.api_key
    if config.api_base:
        kwargs["api_base"] = config.api_base

    if response_model is not None:
        schema = _enforce_strict_schema(
            response_model.model_json_schema()
        )
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "strict": True,
                "schema": schema,
            },
        }

    _throttle()
    response = _completion_with_retry(litellm, kwargs)
    choice = response.choices[0]
    content = choice.message.content

    if choice.finish_reason == "length":
        raise ValueError(
            f"LLM response truncated (finish_reason='length'). "
            f"Increase LLM_MAX_TOKENS (currently {config.max_tokens})."
        )

    if response_model is not None:
        # Strip markdown code fences that some models wrap JSON in
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[-1]
            if stripped.endswith("```"):
                stripped = stripped[: stripped.rfind("```")]
        # Fix trailing commas before } or ] (common Gemini issue)
        stripped = re.sub(r",\s*([}\]])", r"\1", stripped)
        # Fix single-quoted strings → double quotes
        # Fix JS-style comments
        stripped = re.sub(r"//.*$", "", stripped, flags=re.MULTILINE)
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            logger.error(
                "Failed to parse LLM response as JSON. First 500 chars:\n%s",
                stripped[:500],
            )
            raise
        return response_model.model_validate(parsed)

    return content
