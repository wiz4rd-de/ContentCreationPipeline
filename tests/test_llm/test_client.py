"""Tests for seo_pipeline.llm.client — complete() with monkeypatched litellm."""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from seo_pipeline.llm.client import complete
from seo_pipeline.llm.config import LLMConfig
from seo_pipeline.models.llm_responses import QualitativeResponse


def _make_litellm_response(content: str) -> SimpleNamespace:
    """Build a fake litellm response object."""
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


@pytest.fixture()
def llm_config():
    return LLMConfig(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        api_key="test-key",
    )


class TestCompleteRawString:
    """complete() returns raw string when no response_model."""

    def test_returns_string(self, monkeypatch, llm_config):
        expected = "This is a test response."

        def mock_completion(**kwargs):
            assert kwargs["model"] == "claude-sonnet-4-20250514"
            assert kwargs["api_key"] == "test-key"
            assert kwargs["temperature"] == 0.3
            assert kwargs["max_tokens"] == 4096
            assert "response_format" not in kwargs
            return _make_litellm_response(expected)

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        result = complete(
            messages=[{"role": "user", "content": "Hello"}],
            config=llm_config,
        )
        assert result == expected
        assert isinstance(result, str)


class TestCompleteStructured:
    """complete() returns validated Pydantic model with response_model."""

    def test_returns_pydantic_model(self, monkeypatch, llm_config):
        response_data = {
            "entity_clusters": [{"name": "test", "entities": ["a", "b"]}],
            "geo_audit": {"market": "de", "signals": []},
            "content_format_recommendation": {"format": "guide", "reason": "fits"},
            "unique_angles": [{"angle": "fresh take", "source": "data"}],
            "aio_strategy": {"approach": "concise", "target": "featured_snippet"},
        }

        def mock_completion(**kwargs):
            assert "response_format" in kwargs
            fmt = kwargs["response_format"]
            assert fmt["type"] == "json_schema"
            assert fmt["json_schema"]["name"] == "QualitativeResponse"
            return _make_litellm_response(json.dumps(response_data))

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        result = complete(
            messages=[{"role": "user", "content": "Analyze this"}],
            config=llm_config,
            response_model=QualitativeResponse,
        )
        assert isinstance(result, QualitativeResponse)
        assert len(result.entity_clusters) == 1
        assert result.geo_audit["market"] == "de"
        assert result.aio_strategy["approach"] == "concise"

    def test_invalid_json_raises(self, monkeypatch, llm_config):
        def mock_completion(**kwargs):
            return _make_litellm_response("not valid json")

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        with pytest.raises(json.JSONDecodeError):
            complete(
                messages=[{"role": "user", "content": "test"}],
                config=llm_config,
                response_model=QualitativeResponse,
            )


class TestCompleteProviderRouting:
    """Verify model string includes correct provider prefix."""

    @pytest.mark.parametrize(
        "provider,model,expected_litellm_model",
        [
            ("anthropic", "claude-sonnet-4-20250514", "claude-sonnet-4-20250514"),
            ("openai", "gpt-4o", "gpt-4o"),
            ("google", "gemini-1.5-pro", "gemini/gemini-1.5-pro"),
            ("openai_compat", "llama3", "openai/llama3"),
        ],
    )
    def test_provider_model_string(
        self, monkeypatch, provider, model, expected_litellm_model
    ):
        captured: dict[str, Any] = {}

        def mock_completion(**kwargs):
            captured.update(kwargs)
            return _make_litellm_response("ok")

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        cfg = LLMConfig(provider=provider, model=model, api_key="k")
        complete(
            messages=[{"role": "user", "content": "test"}],
            config=cfg,
        )
        assert captured["model"] == expected_litellm_model


class TestCompleteApiBase:
    """Verify api_base is passed through for openai_compat."""

    def test_api_base_passed(self, monkeypatch):
        captured: dict[str, Any] = {}

        def mock_completion(**kwargs):
            captured.update(kwargs)
            return _make_litellm_response("ok")

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        cfg = LLMConfig(
            provider="openai_compat",
            model="llama3",
            api_base="http://localhost:11434/v1",
        )
        complete(messages=[{"role": "user", "content": "test"}], config=cfg)
        assert captured["api_base"] == "http://localhost:11434/v1"

    def test_api_base_omitted_when_none(self, monkeypatch):
        captured: dict[str, Any] = {}

        def mock_completion(**kwargs):
            captured.update(kwargs)
            return _make_litellm_response("ok")

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        cfg = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="k",
        )
        complete(
            messages=[{"role": "user", "content": "test"}],
            config=cfg,
        )
        assert "api_base" not in captured


class TestCompleteDefaultConfig:
    """complete() loads config from env when config=None."""

    def test_default_config_from_env(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")

        def mock_completion(**kwargs):
            assert kwargs["model"] == "gpt-4o"
            return _make_litellm_response("ok")

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        result = complete(messages=[{"role": "user", "content": "test"}])
        assert result == "ok"
