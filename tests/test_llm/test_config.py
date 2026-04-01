"""Tests for seo_pipeline.llm.config — LLMConfig and env loading."""

import pytest

from seo_pipeline.llm.config import VALID_PROVIDERS, LLMConfig


class TestLLMConfigModel:
    """Basic model instantiation and validation."""

    def test_minimal_config(self):
        cfg = LLMConfig(provider="anthropic", model="claude-sonnet-4-20250514")
        assert cfg.provider == "anthropic"
        assert cfg.model == "claude-sonnet-4-20250514"
        assert cfg.api_key is None
        assert cfg.api_base is None
        assert cfg.temperature == 0.3
        assert cfg.max_tokens == 8192

    def test_full_config(self):
        cfg = LLMConfig(
            provider="openai_compat",
            model="llama3",
            api_key="test-key",
            api_base="http://localhost:11434/v1",
            temperature=0.7,
            max_tokens=2048,
        )
        assert cfg.api_key == "test-key"
        assert cfg.api_base == "http://localhost:11434/v1"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 2048


class TestLiteLLMModelPrefix:
    """Provider-to-model-prefix mapping."""

    def test_anthropic_no_prefix(self):
        cfg = LLMConfig(provider="anthropic", model="claude-sonnet-4-20250514")
        assert cfg.litellm_model() == "claude-sonnet-4-20250514"

    def test_openai_no_prefix(self):
        cfg = LLMConfig(provider="openai", model="gpt-4o")
        assert cfg.litellm_model() == "gpt-4o"

    def test_google_gemini_prefix(self):
        cfg = LLMConfig(provider="google", model="gemini-1.5-pro")
        assert cfg.litellm_model() == "gemini/gemini-1.5-pro"

    def test_openai_compat_prefix(self):
        cfg = LLMConfig(provider="openai_compat", model="llama3")
        assert cfg.litellm_model() == "openai/llama3"


class TestFromEnv:
    """Environment-based config loading."""

    def test_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("LLM_MODEL", "claude-sonnet-4-20250514")
        monkeypatch.setenv("LLM_API_KEY", "sk-test-123")
        monkeypatch.setenv("LLM_TEMPERATURE", "0.5")
        monkeypatch.setenv("LLM_MAX_TOKENS", "8192")

        cfg = LLMConfig.from_env(env_file="/nonexistent/path")
        assert cfg.provider == "anthropic"
        assert cfg.model == "claude-sonnet-4-20250514"
        assert cfg.api_key == "sk-test-123"
        assert cfg.temperature == 0.5
        assert cfg.max_tokens == 8192

    def test_from_env_file(self, monkeypatch, tmp_path):
        # Clear any OS env vars
        for key in (
            "LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY",
            "LLM_API_BASE", "LLM_TEMPERATURE", "LLM_MAX_TOKENS",
        ):
            monkeypatch.delenv(key, raising=False)

        env_file = tmp_path / "api.env"
        env_file.write_text(
            "LLM_PROVIDER=openai\n"
            "LLM_MODEL=gpt-4o\n"
            "LLM_API_KEY=sk-openai-test\n"
        )

        cfg = LLMConfig.from_env(env_file=str(env_file))
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4o"
        assert cfg.api_key == "sk-openai-test"
        assert cfg.temperature == 0.3  # default
        assert cfg.max_tokens == 8192  # default

    def test_env_vars_override_file(self, monkeypatch, tmp_path):
        env_file = tmp_path / "api.env"
        env_file.write_text(
            "LLM_PROVIDER=openai\n"
            "LLM_MODEL=gpt-4o\n"
        )
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("LLM_MODEL", "claude-sonnet-4-20250514")

        cfg = LLMConfig.from_env(env_file=str(env_file))
        assert cfg.provider == "anthropic"
        assert cfg.model == "claude-sonnet-4-20250514"

    def test_missing_provider_raises(self, monkeypatch):
        for key in ("LLM_PROVIDER", "LLM_MODEL"):
            monkeypatch.delenv(key, raising=False)

        with pytest.raises(ValueError, match="LLM_PROVIDER must be set"):
            LLMConfig.from_env(env_file="/nonexistent/path")

    def test_missing_model_raises(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.delenv("LLM_MODEL", raising=False)

        with pytest.raises(ValueError, match="LLM_MODEL must be set"):
            LLMConfig.from_env(env_file="/nonexistent/path")

    def test_invalid_provider_raises(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "invalid_provider")
        monkeypatch.setenv("LLM_MODEL", "some-model")

        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            LLMConfig.from_env(env_file="/nonexistent/path")


class TestValidProviders:
    """Ensure all 4 providers are in the valid set."""

    def test_all_four_providers(self):
        assert VALID_PROVIDERS == {"anthropic", "openai", "google", "openai_compat"}
