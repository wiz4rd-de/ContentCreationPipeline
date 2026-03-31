"""Tests for summarize_briefing module."""

import json
from pathlib import Path

import pytest

from seo_pipeline.analysis.summarize_briefing import (
    _format_summary,
    main,
    summarize_briefing,
)

_DIVIDER = "\u2500" * 35


def _make_briefing(**overrides: object) -> dict:
    """Build a minimal briefing data dict with optional overrides."""
    base = {
        "meta": {"seed_keyword": "test keyword"},
        "keyword_data": {
            "total_keywords": 10,
            "filtered_count": 8,
            "clusters": [{"name": "c1"}, {"name": "c2"}],
            "removal_summary": {"foreign": 1, "duplicate": 1, "irrelevant": 0},
        },
        "serp_data": {
            "competitors": [{"url": "a.com"}, {"url": "b.com"}],
            "serp_features": {
                "ai_overview": True,
                "featured_snippet": False,
                "people_also_ask": True,
            },
            "aio": {"present": True},
        },
        "competitor_analysis": {
            "common_modules": ["FAQ", "Table"],
            "rare_modules": ["Calculator"],
            "avg_word_count": 1500,
        },
        "faq_data": {
            "questions": [{"q": "What?"}, {"q": "How?"}],
        },
    }
    base.update(overrides)
    return base


class TestFormatSummary:
    """Tests for _format_summary()."""

    def test_full_summary(self) -> None:
        data = _make_briefing()
        result = _format_summary(data)
        assert result.startswith("Briefing Summary: test keyword\n")
        assert _DIVIDER in result
        assert "Keywords:    10 total, 8 after filtering" in result
        assert "Clusters:    2" in result
        assert "Competitors: 2 (1500 avg words)" in result
        assert "FAQ:         2 questions" in result
        assert "SERP:        ai_overview, people_also_ask" in result
        assert "AIO:         yes" in result
        assert "Modules:     common: FAQ, Table, rare: Calculator" in result
        assert "Removals:    1 foreign, 1 duplicate" in result

    def test_empty_data(self) -> None:
        result = _format_summary({})
        assert "Briefing Summary: n/a" in result
        assert "Keywords:    0 total, 0 after filtering" in result
        assert "Clusters:    0" in result
        assert "Competitors: 0 (n/a avg words)" in result
        assert "FAQ:         0 questions" in result
        assert "SERP:        none" in result
        assert "AIO:         no" in result
        assert "Modules:     common: n/a, rare: n/a" in result
        assert "Removals:    none" in result

    def test_no_aio(self) -> None:
        data = _make_briefing()
        data["serp_data"]["aio"] = {"present": False}
        result = _format_summary(data)
        assert "AIO:         no" in result

    def test_null_aio(self) -> None:
        data = _make_briefing()
        data["serp_data"]["aio"] = None
        result = _format_summary(data)
        assert "AIO:         no" in result

    def test_no_serp_features(self) -> None:
        data = _make_briefing()
        data["serp_data"]["serp_features"] = {}
        result = _format_summary(data)
        assert "SERP:        none" in result

    def test_all_false_serp_features(self) -> None:
        data = _make_briefing()
        data["serp_data"]["serp_features"] = {"a": False, "b": False}
        result = _format_summary(data)
        assert "SERP:        none" in result

    def test_removal_summary_all_zero(self) -> None:
        data = _make_briefing()
        data["keyword_data"]["removal_summary"] = {"foreign": 0, "duplicate": 0}
        result = _format_summary(data)
        assert "Removals:    none" in result

    def test_no_removal_summary(self) -> None:
        data = _make_briefing()
        data["keyword_data"]["removal_summary"] = None
        result = _format_summary(data)
        assert "Removals:    none" in result

    def test_null_competitor_analysis(self) -> None:
        data = _make_briefing(competitor_analysis=None)
        result = _format_summary(data)
        assert "Modules:     common: n/a, rare: n/a" in result
        assert "n/a avg words" in result

    def test_null_keyword_data(self) -> None:
        data = _make_briefing(keyword_data=None)
        result = _format_summary(data)
        assert "Keywords:    0 total, 0 after filtering" in result
        assert "Clusters:    0" in result

    def test_divider_is_35_box_drawing_chars(self) -> None:
        result = _format_summary(_make_briefing())
        lines = result.split("\n")
        assert lines[1] == _DIVIDER
        assert len(lines[1]) == 35

    def test_no_trailing_newline(self) -> None:
        """Summary string itself has no trailing newline (print adds it)."""
        result = _format_summary(_make_briefing())
        assert not result.endswith("\n")


class TestSummarizeBriefingFunction:
    """Tests for summarize_briefing() file-based function."""

    def test_reads_file_and_returns_summary(self, tmp_path: Path) -> None:
        data = _make_briefing()
        path = tmp_path / "briefing-data.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = summarize_briefing(str(path))
        assert "Briefing Summary: test keyword" in result

    def test_missing_file_exits(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            summarize_briefing(str(tmp_path / "missing.json"))


class TestSummarizeBriefingCLI:
    """Tests for CLI entry point."""

    def test_cli_prints_summary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        data = _make_briefing()
        path = tmp_path / "briefing-data.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        main(["--file", str(path)])
        captured = capsys.readouterr()
        assert "Briefing Summary: test keyword" in captured.out

    def test_cli_missing_arg(self) -> None:
        with pytest.raises(SystemExit):
            main([])
