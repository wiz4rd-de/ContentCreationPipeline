"""Tests for seo_pipeline.llm.client — complete() with monkeypatched litellm."""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from seo_pipeline.llm.client import complete
from seo_pipeline.llm.config import LLMConfig
from seo_pipeline.models.llm_responses import QualitativeResponse


def _make_litellm_response(
    content: str,
    finish_reason: str = "stop",
    usage: SimpleNamespace | None = None,
) -> SimpleNamespace:
    """Build a fake litellm response object."""
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    if usage is None:
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50)
    return SimpleNamespace(choices=[choice], usage=usage)


@pytest.fixture(autouse=True)
def _disable_throttle(monkeypatch):
    """Disable rate-limit throttle in tests."""
    monkeypatch.setattr("seo_pipeline.llm.client._MIN_CALL_INTERVAL", 0.0)


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
            assert kwargs["max_tokens"] == 8192
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
            "entity_clusters": [
                {
                    "category": "Tools",
                    "entities": ["google", "semrush"],
                    "synonyms": [
                        {"entity": "google", "synonyms": ["Google Search"]},
                    ],
                },
            ],
            "geo_audit": {
                "must_haves": ["keyword research"],
                "hidden_gems": ["long-tail"],
                "hallucination_risks": ["wrong volumes"],
                "information_gaps": ["voice search"],
            },
            "content_format_recommendation": {
                "format": "Hybrid",
                "rationale": "Mix works best.",
            },
            "unique_angles": [
                {"angle": "AI-powered research", "rationale": "Emerging trend"},
            ],
            "aio_strategy": {
                "snippets": [
                    {
                        "topic": "keyword research",
                        "pattern": "Keyword research is...",
                        "target_section": "Introduction",
                    },
                ],
            },
        }

        def mock_completion(**kwargs):
            assert "response_format" in kwargs
            fmt = kwargs["response_format"]
            assert fmt["type"] == "json_schema"
            assert "json_schema" in fmt
            assert fmt["json_schema"]["strict"] is True
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
        assert result.entity_clusters[0].category == "Tools"
        assert result.geo_audit.must_haves == ["keyword research"]
        assert result.aio_strategy.snippets[0].topic == "keyword research"

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


class TestCompleteRetry:
    """complete() retries on rate-limit and transient errors."""

    def test_retries_on_429_then_succeeds(self, monkeypatch, llm_config):
        call_count = 0

        class RateLimitError(Exception):
            status_code = 429

        def mock_completion(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("rate limited")
            return _make_litellm_response("ok")

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)
        monkeypatch.setattr("seo_pipeline.llm.client._DEFAULT_RATE_LIMIT_WAIT", 0.01)

        result = complete(
            messages=[{"role": "user", "content": "test"}],
            config=llm_config,
        )
        assert result == "ok"
        assert call_count == 3

    def test_429_uses_retry_after_header(self, monkeypatch, llm_config):
        """When retry-after header is present, use that duration."""
        call_count = 0
        wait_times: list[float] = []
        original_sleep = __import__("time").sleep

        class FakeResponse:
            headers = {"retry-after": "0.01"}

        class RateLimitError(Exception):
            status_code = 429
            response = FakeResponse()

        def mock_completion(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RateLimitError("rate limited")
            return _make_litellm_response("ok")

        def mock_sleep(seconds):
            wait_times.append(seconds)
            original_sleep(seconds)

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)
        monkeypatch.setattr("seo_pipeline.llm.client.time.sleep", mock_sleep)

        result = complete(
            messages=[{"role": "user", "content": "test"}],
            config=llm_config,
        )
        assert result == "ok"
        assert wait_times == [0.01]

    def test_raises_non_retryable_error(self, monkeypatch, llm_config):
        class AuthError(Exception):
            status_code = 401

        def mock_completion(**kwargs):
            raise AuthError("unauthorized")

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        with pytest.raises(AuthError):
            complete(
                messages=[{"role": "user", "content": "test"}],
                config=llm_config,
            )

    def test_raises_after_max_retries(self, monkeypatch, llm_config):
        class RateLimitError(Exception):
            status_code = 429

        def mock_completion(**kwargs):
            raise RateLimitError("rate limited")

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)
        monkeypatch.setattr("seo_pipeline.llm.client._DEFAULT_RATE_LIMIT_WAIT", 0.01)
        monkeypatch.setattr("seo_pipeline.llm.client._MAX_RETRIES", 2)

        with pytest.raises(RateLimitError):
            complete(
                messages=[{"role": "user", "content": "test"}],
                config=llm_config,
            )


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


class TestTokenUsageLogging:
    """complete() prints token usage to STDOUT after each LLM call."""

    def test_prints_token_usage(self, monkeypatch, llm_config, capsys):
        usage = SimpleNamespace(prompt_tokens=150, completion_tokens=75)

        def mock_completion(**kwargs):
            return _make_litellm_response("ok", usage=usage)

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        complete(
            messages=[{"role": "user", "content": "test"}],
            config=llm_config,
        )
        captured = capsys.readouterr()
        assert "tokens used: input 150 / output 75" in captured.out

    def test_no_crash_when_usage_missing(self, monkeypatch, llm_config, capsys):
        """Defensive guard: no error when response.usage is absent."""

        def mock_completion(**kwargs):
            message = SimpleNamespace(content="ok")
            choice = SimpleNamespace(message=message, finish_reason="stop")
            # Response with no usage attribute
            return SimpleNamespace(choices=[choice])

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        result = complete(
            messages=[{"role": "user", "content": "test"}],
            config=llm_config,
        )
        assert result == "ok"
        captured = capsys.readouterr()
        assert "tokens used" not in captured.out

    def test_handles_missing_token_fields(self, monkeypatch, llm_config, capsys):
        """Usage object exists but individual token fields are missing."""
        usage = SimpleNamespace()  # no prompt_tokens or completion_tokens

        def mock_completion(**kwargs):
            return _make_litellm_response("ok", usage=usage)

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        complete(
            messages=[{"role": "user", "content": "test"}],
            config=llm_config,
        )
        captured = capsys.readouterr()
        assert "tokens used: input ? / output ?" in captured.out


class TestLabelPrinting:
    """complete() prints label before LLM call when provided."""

    def test_prints_label(self, monkeypatch, llm_config, capsys):
        def mock_completion(**kwargs):
            return _make_litellm_response("ok")

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        complete(
            messages=[{"role": "user", "content": "test"}],
            config=llm_config,
            label="fill_qualitative",
        )
        captured = capsys.readouterr()
        assert "calling LLM: fill_qualitative..." in captured.out

    def test_no_label_when_omitted(self, monkeypatch, llm_config, capsys):
        def mock_completion(**kwargs):
            return _make_litellm_response("ok")

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        complete(
            messages=[{"role": "user", "content": "test"}],
            config=llm_config,
        )
        captured = capsys.readouterr()
        assert "calling LLM:" not in captured.out

    def test_label_printed_before_token_usage(self, monkeypatch, llm_config, capsys):
        """Label line appears before token usage line in output."""
        def mock_completion(**kwargs):
            return _make_litellm_response("ok")

        import litellm
        monkeypatch.setattr(litellm, "completion", mock_completion)

        complete(
            messages=[{"role": "user", "content": "test"}],
            config=llm_config,
            label="write_draft",
        )
        captured = capsys.readouterr()
        label_pos = captured.out.index("calling LLM: write_draft...")
        token_pos = captured.out.index("tokens used:")
        assert label_pos < token_pos
