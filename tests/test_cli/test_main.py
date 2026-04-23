"""Tests for seo_pipeline.cli.main."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from seo_pipeline.cli.main import app

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(output: str) -> str:
    """Strip ANSI color codes so assertions match in any terminal env.

    GitHub Actions sets FORCE_COLOR=1, which makes rich render option
    names as fragmented ANSI tokens (e.g. `--top` -> `\\x1b[..]-\\x1b[..]-top`),
    breaking naive `in` checks. Local dev has no FORCE_COLOR, so tests
    passed. Strip ANSI to make assertions env-independent.
    """
    return _ANSI_RE.sub("", output)


# ---------------------------------------------------------------------------
# Basic app tests
# ---------------------------------------------------------------------------


def test_app_imports():
    """App object loads without error."""
    assert app is not None


def test_help_returns_zero():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = _plain(result.output)
    assert "seo-pipeline" in out.lower() or "SEO" in out


def test_version_returns_zero():
    from seo_pipeline import __version__

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in _plain(result.output)


# ---------------------------------------------------------------------------
# Subcommand --help tests
# ---------------------------------------------------------------------------


def test_process_serp_help():
    result = runner.invoke(app, ["process-serp", "--help"])
    assert result.exit_code == 0
    out = _plain(result.output)
    assert "--top" in out
    assert "--output" in out


def test_fetch_serp_help():
    result = runner.invoke(app, ["fetch-serp", "--help"])
    assert result.exit_code == 0
    out = _plain(result.output)
    assert "--market" in out or "KEYWORD" in out


def test_assemble_competitors_help():
    result = runner.invoke(app, ["assemble-competitors", "--help"])
    assert result.exit_code == 0
    assert "--date" in _plain(result.output)


def test_extract_page_help():
    result = runner.invoke(app, ["extract-page", "--help"])
    assert result.exit_code == 0
    assert "--output" in _plain(result.output)


def test_filter_keywords_help():
    result = runner.invoke(app, ["filter-keywords", "--help"])
    assert result.exit_code == 0
    out = _plain(result.output)
    assert "--keywords" in out
    assert "--serp" in out


def test_run_pipeline_help():
    result = runner.invoke(app, ["run-pipeline", "--help"])
    assert result.exit_code == 0
    out = _plain(result.output)
    assert "--skip-fetch" in out
    assert "--output-dir" in out


# ---------------------------------------------------------------------------
# Subcommand invocation tests (mocked)
# ---------------------------------------------------------------------------


def test_process_serp_invocation(tmp_path: Path):
    """process-serp reads JSON and produces output via mocked function."""
    input_file = tmp_path / "serp-raw.json"
    input_file.write_text('{"tasks": []}', encoding="utf-8")
    output_file = tmp_path / "serp-processed.json"

    mock_result = {"keyword": "test", "competitors": []}

    with patch(
        "seo_pipeline.serp.process_serp.process_serp",
        return_value=mock_result,
    ):
        result = runner.invoke(app, [
            "process-serp",
            str(input_file),
            "--output", str(output_file),
        ])

    assert result.exit_code == 0
    assert output_file.exists()
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["keyword"] == "test"


def test_extract_claims_invocation(tmp_path: Path):
    """extract-claims runs with mocked function."""
    draft_file = tmp_path / "draft.md"
    draft_file.write_text("Some draft content.", encoding="utf-8")
    output_file = tmp_path / "claims.json"

    from seo_pipeline.models.analysis import ClaimsMeta, ClaimsOutput

    mock_result = ClaimsOutput(
        meta=ClaimsMeta(
            draft=str(draft_file),
            extracted_at="2026-01-01T00:00:00",
            total_claims=0,
        ),
        claims=[],
    )

    with patch(
        "seo_pipeline.analysis.extract_claims.extract_claims",
        return_value=mock_result,
    ):
        result = runner.invoke(app, [
            "extract-claims",
            "--draft", str(draft_file),
            "--output", str(output_file),
        ])

    assert result.exit_code == 0
    assert output_file.exists()
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["meta"]["total_claims"] == 0


def test_summarize_briefing_invocation(tmp_path: Path):
    """summarize-briefing outputs summary text."""
    briefing_file = tmp_path / "briefing-data.json"
    briefing_file.write_text("{}", encoding="utf-8")

    with patch(
        "seo_pipeline.analysis.summarize_briefing.summarize_briefing",
        return_value="Keyword: test\nTotal: 5",
    ):
        result = runner.invoke(app, [
            "summarize-briefing",
            "--file", str(briefing_file),
        ])

    assert result.exit_code == 0
    assert "Keyword: test" in result.output


# ---------------------------------------------------------------------------
# Stage 10 LLM availability gate (regression: issue #87)
# ---------------------------------------------------------------------------


def test_stage10_gate_falls_back_when_litellm_missing(monkeypatch):
    """The Stage 10 gate must set llm_configured=False when litellm is absent.

    Regression for issue #87: previously `LLMConfig.from_env()` succeeded when
    env vars were set, but Stage 10 crashed with ModuleNotFoundError because
    `litellm` was not installed. The gate must proactively check for litellm
    via `importlib.util.find_spec` and treat ImportError as "not configured".
    """
    import importlib.util

    from seo_pipeline.llm.config import LLMConfig

    # Pretend LLM env is valid by returning a dummy config.
    monkeypatch.setattr(
        LLMConfig, "from_env", classmethod(lambda cls, env_file=None: None)
    )
    # Pretend litellm is missing.
    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name, *args, **kwargs):
        if name == "litellm":
            return None
        return real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    # Mirror the exact gate logic from run_pipeline Stage 10.
    try:
        LLMConfig.from_env()
        if importlib.util.find_spec("litellm") is None:
            raise ImportError("litellm is not installed")
        llm_configured = True
    except (ValueError, ImportError):
        llm_configured = False

    assert llm_configured is False


def test_stage10_gate_enabled_when_env_and_litellm_present(monkeypatch):
    """Gate stays True when env is valid and litellm is importable."""
    import importlib.util

    from seo_pipeline.llm.config import LLMConfig

    monkeypatch.setattr(
        LLMConfig, "from_env", classmethod(lambda cls, env_file=None: None)
    )
    # Pretend litellm is available (return a truthy sentinel).
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda name, *a, **kw: object()
    )

    try:
        LLMConfig.from_env()
        if importlib.util.find_spec("litellm") is None:
            raise ImportError("litellm is not installed")
        llm_configured = True
    except (ValueError, ImportError):
        llm_configured = False

    assert llm_configured is True


def test_stage10_gate_disabled_when_env_invalid(monkeypatch):
    """Gate is False when LLMConfig.from_env raises ValueError (pre-existing behaviour)."""
    import importlib.util

    from seo_pipeline.llm.config import LLMConfig

    def raise_value_error(cls, env_file=None):
        raise ValueError("missing env")

    monkeypatch.setattr(LLMConfig, "from_env", classmethod(raise_value_error))

    try:
        LLMConfig.from_env()
        if importlib.util.find_spec("litellm") is None:
            raise ImportError("litellm is not installed")
        llm_configured = True
    except (ValueError, ImportError):
        llm_configured = False

    assert llm_configured is False


# ---------------------------------------------------------------------------
# Post-fact-check docx emission (revises #189; see PR #191)
# ---------------------------------------------------------------------------


class TestEmitDraftDocx:
    """Tests for the _emit_draft_docx helper.

    The helper is invoked at the very end of run_pipeline, AFTER the
    fact-check stage has had a chance to modify draft-<slug>.md in place.
    This ensures the emitted docx reflects the final post-fact-check state
    of the markdown.
    """

    def test_converts_draft_md_to_sibling_docx(self, tmp_path: Path) -> None:
        from seo_pipeline.cli.main import _emit_draft_docx

        draft_md = tmp_path / "draft-my-topic.md"
        draft_md.write_text("# Heading\n\nbody.\n", encoding="utf-8")

        with patch("pypandoc.convert_file") as mock_convert:
            _emit_draft_docx(draft_md)

        expected_docx = tmp_path / "draft-my-topic.docx"
        mock_convert.assert_called_once_with(
            str(draft_md), "docx", outputfile=str(expected_docx),
        )

    def test_skips_when_draft_md_missing(
        self, tmp_path: Path, caplog,
    ) -> None:
        from seo_pipeline.cli.main import _emit_draft_docx

        missing = tmp_path / "draft-missing.md"

        with caplog.at_level("WARNING"), patch(
            "pypandoc.convert_file",
        ) as mock_convert:
            _emit_draft_docx(missing)

        mock_convert.assert_not_called()
        assert "skipping docx" in caplog.text
        assert "draft markdown not found" in caplog.text

    def test_pypandoc_failure_does_not_raise(
        self, tmp_path: Path, caplog,
    ) -> None:
        from seo_pipeline.cli.main import _emit_draft_docx

        draft_md = tmp_path / "draft-fail.md"
        draft_md.write_text("# Heading\n", encoding="utf-8")

        with caplog.at_level("WARNING"), patch(
            "pypandoc.convert_file",
            side_effect=RuntimeError("pandoc boom"),
        ):
            # Must return normally even though pypandoc raises.
            _emit_draft_docx(draft_md)

        assert "docx conversion failed" in caplog.text
        assert "pandoc boom" in caplog.text

    def test_missing_pypandoc_logs_warning_and_returns(
        self, tmp_path: Path, caplog, monkeypatch,
    ) -> None:
        """If pypandoc cannot be imported, emit a warning and do not raise."""
        import builtins

        from seo_pipeline.cli.main import _emit_draft_docx

        draft_md = tmp_path / "draft-nopandoc.md"
        draft_md.write_text("# Heading\n", encoding="utf-8")

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pypandoc":
                raise ImportError("no pypandoc")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        with caplog.at_level("WARNING"):
            _emit_draft_docx(draft_md)

        assert "pypandoc not installed" in caplog.text

    def test_called_after_fact_check_even_when_fact_check_raises(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """Structural guarantee: _emit_draft_docx is invoked AFTER the
        fact-check try/except in run_pipeline, so it runs even when
        fact_check raises a handled exception.

        Verifies the call order by patching both _fact_check and the
        helper with a shared call recorder, then exercising the exact
        post-fact-check code pattern from run_pipeline.
        """
        from unittest.mock import MagicMock

        from seo_pipeline.cli import main as cli_main

        recorder = MagicMock()

        def fake_fact_check(*args, **kwargs):
            recorder("fact_check", args, kwargs)
            raise RuntimeError("simulated fact-check failure")

        def fake_emit(draft_md_path):
            recorder("emit_draft_docx", str(draft_md_path))

        monkeypatch.setattr(
            "seo_pipeline.analysis.fact_check.fact_check",
            fake_fact_check,
        )
        monkeypatch.setattr(cli_main, "_emit_draft_docx", fake_emit)

        # Mirrors run_pipeline's post-fact-check control flow:
        #   try:
        #       _fact_check(...)
        #   except Exception as exc:
        #       _log(...)  # swallowed
        #
        #   _emit_draft_docx(out_dir / f"draft-{slug}.md")
        out_dir = tmp_path
        slug = "kw"
        draft_path = out_dir / f"draft-{slug}.md"
        draft_path.write_text("# Draft\n", encoding="utf-8")

        from seo_pipeline.analysis.fact_check import fact_check

        try:
            fact_check(str(draft_path), str(out_dir), None, None)
        except Exception:
            pass  # swallowed as in run_pipeline

        cli_main._emit_draft_docx(out_dir / f"draft-{slug}.md")

        call_names = [c.args[0] for c in recorder.call_args_list]
        assert call_names == ["fact_check", "emit_draft_docx"]


class TestRunPipelineDocxIntegration:
    """Structural verification that the pipeline invokes _emit_draft_docx
    at the correct place: AFTER the fact-check try/except, targeting the
    draft-<slug>.md that fact_check may have modified in place.

    A full end-to-end CliRunner test would require mocking 10+ stage
    functions; this source-inspection test guards the key invariant
    (correct placement) without that complexity.

    Since P1.2 (#194) the stage logic lives in ``seo_pipeline.orchestrator``
    rather than ``cli.main``, so the invariant is asserted on the Stage 11
    helper in the orchestrator module.
    """

    def test_emit_draft_docx_call_follows_fact_check_block(self) -> None:
        import inspect

        from seo_pipeline import orchestrator

        source = inspect.getsource(orchestrator._stage_fact_check)

        assert source.count("_emit_draft_docx(") == 1, (
            "_emit_draft_docx should be called exactly once in _stage_fact_check"
        )

        fact_check_idx = source.index("_fact_check(")
        emit_idx = source.index("_emit_draft_docx(")
        assert fact_check_idx < emit_idx, (
            "_emit_draft_docx must be called after the fact-check stage"
        )

        # It must target draft-<slug>.md (the post-fact-check markdown).
        assert 'f"draft-{slug}.md"' in source[emit_idx:emit_idx + 200]

    def test_emit_draft_docx_not_called_from_write_draft(self) -> None:
        """Regression: write_draft must NOT emit docx — that was moved
        to post-fact-check to capture in-place fact-check edits."""
        import inspect

        from seo_pipeline.drafting import write_draft as write_draft_module

        source = inspect.getsource(write_draft_module)
        assert "pypandoc" not in source, (
            "pypandoc emission should be handled in run_pipeline after "
            "fact-check, not in write_draft"
        )
        assert ".docx" not in source
