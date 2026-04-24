"""Unit tests for :mod:`streamlit_app.runs`.

These tests use ``tmp_path`` to construct miniature ``output/`` trees and
verify that :func:`list_runs` discovers run directories, parses dates,
detects each of the five tracked artifacts, and sorts newest-first. No
Streamlit runtime is required.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from streamlit_app.runs import RunInfo, list_runs


def _touch(path: Path, body: str = "") -> None:
    """Create the parent dir (if needed) and write ``body`` to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_list_runs_empty_dir_returns_empty(tmp_path: Path) -> None:
    """An ``output/`` dir that exists but is empty yields no runs."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    assert list_runs(output_dir) == []


def test_list_runs_missing_dir_returns_empty(tmp_path: Path) -> None:
    """A non-existent ``output_dir`` is tolerated, not an error."""
    assert list_runs(tmp_path / "does-not-exist") == []


def test_list_runs_two_runs_complete_and_partial(tmp_path: Path) -> None:
    """One complete run + one partial run: flags match on-disk artifacts."""
    output_dir = tmp_path / "output"

    # --- Complete run: all five tracked artifacts present. -----------------
    complete_dir = output_dir / "2026-04-20_sintra-urlaub"
    _touch(complete_dir / "brief-sintra-urlaub.md", "# brief")
    _touch(complete_dir / "draft-sintra-urlaub.md", "# draft")
    _touch(complete_dir / "draft-sintra-urlaub.docx", "docx-bytes")
    _touch(complete_dir / "fact-check-report.md", "# fact-check")
    _touch(complete_dir / "tov-check-report.md", "# tov-check")

    # --- Partial run: only brief + draft md, nothing else. -----------------
    partial_dir = output_dir / "2026-04-15_porto-reisen"
    _touch(partial_dir / "brief-porto-reisen.md", "# brief")
    _touch(partial_dir / "draft-porto-reisen.md", "# draft")

    # --- Non-matching dirs should be ignored. ------------------------------
    (output_dir / "drafts").mkdir()
    (output_dir / "not-a-run").mkdir()
    _touch(output_dir / "stray-file.txt", "ignored")

    runs = list_runs(output_dir)
    assert len(runs) == 2

    # Newest-first ordering: 2026-04-20 before 2026-04-15.
    complete, partial = runs
    assert isinstance(complete, RunInfo) and isinstance(partial, RunInfo)

    # --- Complete run flags ------------------------------------------------
    assert complete.date == date(2026, 4, 20)
    assert complete.slug == "sintra-urlaub"
    assert complete.path == complete_dir.resolve()
    assert complete.has_brief is True
    assert complete.has_draft_md is True
    assert complete.has_draft_docx is True
    assert complete.has_fact_check is True
    assert complete.has_tov_check is True

    # --- Partial run flags -------------------------------------------------
    assert partial.date == date(2026, 4, 15)
    assert partial.slug == "porto-reisen"
    assert partial.has_brief is True
    assert partial.has_draft_md is True
    assert partial.has_draft_docx is False
    assert partial.has_fact_check is False
    assert partial.has_tov_check is False


def test_list_runs_ignores_invalid_date(tmp_path: Path) -> None:
    """Directories whose prefix isn't a real date are skipped."""
    output_dir = tmp_path / "output"
    # Feb 30 isn't a real date; directory should be ignored.
    (output_dir / "2026-02-30_bad-date").mkdir(parents=True)
    # Well-formed name but with missing slug portion.
    (output_dir / "2026-04-01_").mkdir(parents=True)
    # Malformed — no underscore separator.
    (output_dir / "2026-04-01").mkdir(parents=True)

    # Plus one valid run so we confirm the scanner still works.
    good = output_dir / "2026-04-02_valid-slug"
    good.mkdir(parents=True)

    runs = list_runs(output_dir)
    assert [r.slug for r in runs] == ["valid-slug"]


def test_list_runs_sorted_newest_first(tmp_path: Path) -> None:
    """Runs are returned in descending date order regardless of disk order."""
    output_dir = tmp_path / "output"
    for name in [
        "2026-04-10_alpha",
        "2026-05-01_bravo",
        "2026-04-20_charlie",
        "2026-04-20_alpha",  # same-day tie; slug should break it ascending
    ]:
        (output_dir / name).mkdir(parents=True)

    runs = list_runs(output_dir)
    dates = [r.date.isoformat() for r in runs]
    assert dates == ["2026-05-01", "2026-04-20", "2026-04-20", "2026-04-10"]

    # Tie-break on 2026-04-20: slug ascending.
    same_day = [r for r in runs if r.date == date(2026, 4, 20)]
    assert [r.slug for r in same_day] == ["alpha", "charlie"]


def test_list_runs_skips_files_at_top_level(tmp_path: Path) -> None:
    """Files (not directories) named like runs are ignored."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    # A file with a run-shaped name — must NOT be picked up as a run.
    (output_dir / "2026-04-20_not-a-dir").write_text("x", encoding="utf-8")
    assert list_runs(output_dir) == []


def test_run_info_completion_flags_mapping(tmp_path: Path) -> None:
    """``RunInfo.completion_flags`` mirrors the ``has_*`` attributes."""
    run_dir = tmp_path / "output" / "2026-04-20_x"
    _touch(run_dir / "brief-x.md")
    runs = list_runs(tmp_path / "output")
    assert len(runs) == 1
    flags = runs[0].completion_flags
    assert flags == {
        "brief": True,
        "draft_md": False,
        "draft_docx": False,
        "fact_check": False,
        "tov_check": False,
    }


def test_list_runs_default_uses_cwd_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Omitting ``output_dir`` resolves to ``Path.cwd() / 'output'``."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output" / "2026-04-20_foo").mkdir(parents=True)

    runs = list_runs()
    assert [r.slug for r in runs] == ["foo"]
