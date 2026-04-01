"""Thin wrapper around litellm.completion() with structured output support."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from seo_pipeline.llm.config import LLMConfig

if TYPE_CHECKING:
    from pydantic import BaseModel


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
        schema = response_model.model_json_schema()
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": response_model.__name__, "schema": schema},
        }

    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content

    if response_model is not None:
        return response_model.model_validate(json.loads(content))

    return content
