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
