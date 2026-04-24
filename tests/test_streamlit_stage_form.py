"""Unit tests for the non-Streamlit helpers in :mod:`streamlit_app._stage_form`.

The module's pure helpers (``resolve_slug``) and its gate check are the
only pieces safe to exercise outside a Streamlit runtime — the widget
helpers (``pick_run_dir``, ``render_artifact_*``) require an active
script-run context. Those are covered by the smoke test and by manual
exercise on the running app.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from streamlit_app._stage_form import gate_open, resolve_slug


class TestResolveSlug:
    def test_standard_yyyy_mm_dd_prefix(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "2026-04-20_sintra-urlaub"
        run_dir.mkdir()
        assert resolve_slug(run_dir) == "sintra-urlaub"

    def test_short_slug_is_preserved(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "2026-04-20_x"
        run_dir.mkdir()
        assert resolve_slug(run_dir) == "x"

    def test_missing_prefix_falls_back_to_dirname(
        self, tmp_path: Path,
    ) -> None:
        run_dir = tmp_path / "adhoc-directory"
        run_dir.mkdir()
        # No 'YYYY-MM-DD_' prefix — fallback returns whole name.
        assert resolve_slug(run_dir) == "adhoc-directory"

    def test_prefix_without_underscore_is_treated_as_no_prefix(
        self, tmp_path: Path,
    ) -> None:
        # 10 chars but no underscore at position 10 — treat as no prefix.
        run_dir = tmp_path / "2026-04-20x"
        run_dir.mkdir()
        assert resolve_slug(run_dir) == "2026-04-20x"


class TestGateOpen:
    def test_gate_open_true_when_all_required_keys_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        env_file = tmp_path / "api.env"
        env_file.write_text(
            "LLM_PROVIDER=anthropic\n"
            "LLM_MODEL=claude-sonnet-4-20250514\n"
            "LLM_API_KEY=sk-abc\n"
            "DATAFORSEO_AUTH=auth-token\n"
            "DATAFORSEO_BASE=https://api.example.com\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        assert gate_open() is True

    def test_gate_open_false_when_required_key_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        env_file = tmp_path / "api.env"
        env_file.write_text(
            # LLM_API_KEY intentionally missing
            "LLM_PROVIDER=anthropic\n"
            "LLM_MODEL=claude-sonnet-4-20250514\n"
            "DATAFORSEO_AUTH=auth-token\n"
            "DATAFORSEO_BASE=https://api.example.com\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        # Clear any stale env var from a prior test so the gate doesn't
        # mistakenly see a value from os.environ.
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        assert gate_open() is False

    def test_gate_open_false_when_env_file_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("DATAFORSEO_AUTH", raising=False)
        monkeypatch.delenv("DATAFORSEO_BASE", raising=False)
        assert gate_open() is False
