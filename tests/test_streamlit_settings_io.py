"""Unit tests for :mod:`streamlit_app.settings_io`.

These tests intentionally never touch the real ``api.env`` in the project
root: every call passes an explicit ``tmp_path``-backed path.
"""

from __future__ import annotations

import os

import pytest

from streamlit_app.settings_io import (
    ALL_KEYS,
    OPTIONAL_KEYS,
    REQUIRED_KEYS,
    SECRET_KEYS,
    apply_to_process_env,
    load_api_env,
    missing_required,
    save_api_env,
)


def test_required_keys_cover_llm_and_dataforseo() -> None:
    """Sanity check that REQUIRED_KEYS stays aligned with LLMConfig + DataForSEO."""
    for expected in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY"):
        assert expected in REQUIRED_KEYS
    for expected in ("DATAFORSEO_AUTH", "DATAFORSEO_BASE"):
        assert expected in REQUIRED_KEYS
    for expected in ("LLM_API_BASE", "LLM_TEMPERATURE", "LLM_MAX_TOKENS"):
        assert expected in OPTIONAL_KEYS
    assert set(ALL_KEYS) == set(REQUIRED_KEYS) | set(OPTIONAL_KEYS)
    assert SECRET_KEYS <= set(ALL_KEYS)


def test_load_api_env_returns_empty_when_file_missing(tmp_path) -> None:
    path = tmp_path / "api.env"
    assert load_api_env(path) == {}


def test_load_api_env_parses_simple_kv(tmp_path) -> None:
    path = tmp_path / "api.env"
    path.write_text(
        "# a comment\n"
        "\n"
        "LLM_PROVIDER=anthropic\n"
        "LLM_MODEL=claude-sonnet-4-20250514\n"
        "DATAFORSEO_AUTH=abc123==\n",
        encoding="utf-8",
    )
    result = load_api_env(path)
    assert result == {
        "LLM_PROVIDER": "anthropic",
        "LLM_MODEL": "claude-sonnet-4-20250514",
        "DATAFORSEO_AUTH": "abc123==",
    }


def test_load_api_env_strips_quotes(tmp_path) -> None:
    path = tmp_path / "api.env"
    path.write_text(
        'LLM_API_KEY="sk-secret"\n'
        "LLM_MODEL='gpt-4o'\n",
        encoding="utf-8",
    )
    result = load_api_env(path)
    assert result["LLM_API_KEY"] == "sk-secret"
    assert result["LLM_MODEL"] == "gpt-4o"


def test_load_api_env_skips_malformed_and_blank_lines(tmp_path) -> None:
    path = tmp_path / "api.env"
    path.write_text(
        "   \n"
        "# comment with = sign\n"
        "not a kv line\n"
        "=value_with_no_key\n"
        "KEY_OK=value_ok\n",
        encoding="utf-8",
    )
    assert load_api_env(path) == {"KEY_OK": "value_ok"}


def test_save_api_env_round_trips(tmp_path) -> None:
    path = tmp_path / "api.env"
    values = {
        "LLM_PROVIDER": "anthropic",
        "LLM_MODEL": "claude-sonnet-4-20250514",
        "LLM_API_KEY": "sk-test-123",
        "DATAFORSEO_AUTH": "dGVzdDp0ZXN0",
        "DATAFORSEO_BASE": "https://api.dataforseo.com/v3",
    }
    save_api_env(values, path)
    assert path.exists()
    assert load_api_env(path) == values


def test_save_api_env_preserves_comments_and_ordering(tmp_path) -> None:
    """save_api_env should replace existing key lines in place, preserving comments."""
    path = tmp_path / "api.env"
    path.write_text(
        "# Header comment\n"
        "LLM_PROVIDER=anthropic\n"
        "# Section marker\n"
        "LLM_MODEL=old-model\n"
        "# Another comment\n",
        encoding="utf-8",
    )
    save_api_env(
        {"LLM_PROVIDER": "openai", "LLM_MODEL": "gpt-4o", "LLM_API_KEY": "sk-new"},
        path,
    )
    text = path.read_text(encoding="utf-8")
    assert "# Header comment" in text
    assert "# Section marker" in text
    assert "# Another comment" in text
    assert "LLM_PROVIDER=openai" in text
    assert "LLM_MODEL=gpt-4o" in text
    # New key is appended.
    assert "LLM_API_KEY=sk-new" in text
    # Ordering: LLM_PROVIDER appears before LLM_MODEL (matches original file).
    assert text.index("LLM_PROVIDER=openai") < text.index("LLM_MODEL=gpt-4o")


def test_save_api_env_replaces_commented_out_keys(tmp_path) -> None:
    """A commented-out `# KEY=...` line gets replaced in place on set."""
    path = tmp_path / "api.env"
    path.write_text(
        "# LLM_PROVIDER=anthropic\n"
        "# LLM_MODEL=claude-sonnet-4-20250514\n",
        encoding="utf-8",
    )
    save_api_env({"LLM_PROVIDER": "openai", "LLM_MODEL": "gpt-4o"}, path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert "LLM_PROVIDER=openai" in lines
    assert "LLM_MODEL=gpt-4o" in lines
    # Commented-out originals are gone (replaced in place).
    assert "# LLM_PROVIDER=anthropic" not in lines
    assert "# LLM_MODEL=claude-sonnet-4-20250514" not in lines


def test_save_api_env_is_atomic_on_rewrite(tmp_path) -> None:
    """Re-saving should not leave behind stale temp files."""
    path = tmp_path / "api.env"
    save_api_env({"LLM_PROVIDER": "anthropic"}, path)
    save_api_env({"LLM_PROVIDER": "openai"}, path)
    assert load_api_env(path) == {"LLM_PROVIDER": "openai"}
    # No stray temp file left over.
    assert not (tmp_path / "api.env.tmp").exists()


def test_save_and_load_round_trip_survives_reload(tmp_path) -> None:
    """Simulates app restart: save, forget, reload."""
    path = tmp_path / "api.env"
    values = {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "m1", "LLM_API_KEY": "k1"}
    save_api_env(values, path)

    reloaded = load_api_env(path)
    for key, value in values.items():
        assert reloaded[key] == value


def test_apply_to_process_env_mutates_os_environ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Start from a clean slate for the keys we touch.
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    apply_to_process_env({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "claude-x"})
    assert os.environ["LLM_PROVIDER"] == "anthropic"
    assert os.environ["LLM_MODEL"] == "claude-x"


def test_apply_to_process_env_unsets_empty_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_API_BASE", "http://old.example")
    apply_to_process_env({"LLM_API_BASE": ""})
    assert "LLM_API_BASE" not in os.environ


def test_missing_required_reports_blank_and_missing(tmp_path) -> None:
    full = {
        "LLM_PROVIDER": "anthropic",
        "LLM_MODEL": "m",
        "LLM_API_KEY": "k",
        "DATAFORSEO_AUTH": "a",
        "DATAFORSEO_BASE": "b",
    }
    assert missing_required(full) == []

    partial = dict(full)
    partial["LLM_API_KEY"] = ""  # blank counts as missing
    partial.pop("DATAFORSEO_BASE")  # absent counts as missing
    assert set(missing_required(partial)) == {"LLM_API_KEY", "DATAFORSEO_BASE"}
