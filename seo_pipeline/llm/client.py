"""Thin wrapper around litellm.completion() with structured output support."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from seo_pipeline.llm.config import LLMConfig

if TYPE_CHECKING:
    from pydantic import BaseModel


def _enforce_additional_properties_false(schema: Any) -> Any:
    """Recursively set additionalProperties: false on all object schemas.

    Required by Anthropic's structured output API.
    """
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            schema.setdefault("additionalProperties", False)
        for value in schema.values():
            _enforce_additional_properties_false(value)
    elif isinstance(schema, list):
        for item in schema:
            _enforce_additional_properties_false(item)
    return schema


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
        kwargs["response_format"] = {"type": "json_object"}

    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content

    if response_model is not None:
        # Strip markdown code fences that some models wrap JSON in
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[-1]
            if stripped.endswith("```"):
                stripped = stripped[: stripped.rfind("```")]
        return response_model.model_validate(json.loads(stripped))

    return content
