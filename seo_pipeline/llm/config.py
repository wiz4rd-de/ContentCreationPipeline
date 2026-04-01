"""LLM configuration with environment-based loading."""

import os
from pathlib import Path

from dotenv import dotenv_values

from seo_pipeline.models.common import PipelineBaseModel

# Provider-to-LiteLLM prefix mapping
_PROVIDER_PREFIX: dict[str, str] = {
    "anthropic": "",
    "openai": "",
    "google": "gemini/",
    "openai_compat": "openai/",
}

VALID_PROVIDERS = frozenset(_PROVIDER_PREFIX.keys())


class LLMConfig(PipelineBaseModel):
    """LLM provider configuration.

    Attributes:
        provider: One of 'anthropic', 'openai', 'google', 'openai_compat'.
        model: Model identifier (e.g. 'claude-sonnet-4-20250514', 'gpt-4o').
        api_key: API key. Not needed for local providers like Ollama.
        api_base: Base URL override. Required for openai_compat.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in the response.
    """

    provider: str
    model: str
    api_key: str | None = None
    api_base: str | None = None
    temperature: float = 0.3
    max_tokens: int = 4096

    def litellm_model(self) -> str:
        """Return the model string with the correct LiteLLM prefix."""
        prefix = _PROVIDER_PREFIX.get(self.provider, "")
        return f"{prefix}{self.model}"

    @classmethod
    def from_env(cls, env_file: str | None = None) -> "LLMConfig":
        """Load config from environment variables, falling back to api.env.

        Priority: OS env vars > api.env file values > class defaults.
        """
        file_env: dict[str, str | None] = {}
        if env_file:
            path = Path(env_file)
            if path.exists():
                file_env = dotenv_values(env_file)
        else:
            # Default: look for api.env in project root
            candidates = [
                Path.cwd() / "api.env",
                Path(__file__).resolve().parent.parent.parent / "api.env",
            ]
            for candidate in candidates:
                if candidate.exists():
                    file_env = dotenv_values(str(candidate))
                    break

        def _get(key: str, default: str | None = None) -> str | None:
            return os.environ.get(key) or file_env.get(key) or default

        provider = _get("LLM_PROVIDER")
        model = _get("LLM_MODEL")

        if not provider:
            raise ValueError(
                "LLM_PROVIDER must be set (env var or api.env). "
                f"Valid providers: {', '.join(sorted(VALID_PROVIDERS))}"
            )
        if provider not in VALID_PROVIDERS:
            raise ValueError(
                f"Unknown LLM_PROVIDER '{provider}'. "
                f"Valid providers: {', '.join(sorted(VALID_PROVIDERS))}"
            )
        if not model:
            raise ValueError("LLM_MODEL must be set (env var or api.env)")

        temperature_str = _get("LLM_TEMPERATURE")
        max_tokens_str = _get("LLM_MAX_TOKENS")

        return cls(
            provider=provider,
            model=model,
            api_key=_get("LLM_API_KEY"),
            api_base=_get("LLM_API_BASE"),
            temperature=float(temperature_str) if temperature_str else 0.3,
            max_tokens=int(max_tokens_str) if max_tokens_str else 4096,
        )
