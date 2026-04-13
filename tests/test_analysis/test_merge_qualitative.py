"""Tests for merge_qualitative module."""

import json
from pathlib import Path

import pytest

from seo_pipeline.analysis.merge_qualitative import main, merge_qualitative


@pytest.fixture()
def briefing_dir(tmp_path: Path) -> Path:
    """Create a temp directory with briefing-data.json and qualitative.json."""
    briefing = {
        "meta": {"seed_keyword": "test"},
        "qualitative": {
            "entity_clusters": None,
            "unique_angles": None,
            "content_format_recommendation": None,
            "geo_audit": None,
            "aio_strategy": None,
            "briefing": None,
        },
    }
    qualitative = {
        "entity_clusters": [
            {
                "category": "Tools",
                "entities": ["google"],
                "synonyms": [{"entity": "google", "synonyms": ["Google Search"]}],
            },
        ],
        "unique_angles": [
            {"angle": "AI-powered research", "rationale": "Emerging trend"},
        ],
        "content_format_recommendation": None,
        "geo_audit": {
            "must_haves": ["basics"],
            "hidden_gems": ["long-tail"],
            "hallucination_risks": ["wrong data"],
            "information_gaps": ["voice search"],
        },
        "aio_strategy": None,
        "briefing": "Final briefing text",
    }
    (tmp_path / "briefing-data.json").write_text(
        json.dumps(briefing, indent=2) + "\n", encoding="utf-8",
    )
    (tmp_path / "qualitative.json").write_text(
        json.dumps(qualitative, indent=2) + "\n", encoding="utf-8",
    )
    return tmp_path


class TestMergeQualitative:
    """Tests for merge_qualitative()."""

    def test_merges_non_null_fields(self, briefing_dir: Path) -> None:
        merge_qualitative(str(briefing_dir))
        result = json.loads(
            (briefing_dir / "briefing-data.json").read_text(encoding="utf-8"),
        )
        qual = result["qualitative"]
        # Non-null fields patched
        assert qual["entity_clusters"][0]["category"] == "Tools"
        assert qual["unique_angles"][0]["angle"] == "AI-powered research"
        assert qual["geo_audit"]["must_haves"] == ["basics"]
        assert qual["briefing"] == "Final briefing text"

    def test_preserves_null_fields(self, briefing_dir: Path) -> None:
        merge_qualitative(str(briefing_dir))
        result = json.loads(
            (briefing_dir / "briefing-data.json").read_text(encoding="utf-8"),
        )
        qual = result["qualitative"]
        # Null fields remain null
        assert qual["content_format_recommendation"] is None
        assert qual["aio_strategy"] is None

    def test_preserves_other_sections(self, briefing_dir: Path) -> None:
        merge_qualitative(str(briefing_dir))
        result = json.loads(
            (briefing_dir / "briefing-data.json").read_text(encoding="utf-8"),
        )
        assert result["meta"]["seed_keyword"] == "test"

    def test_missing_briefing_exits(self, tmp_path: Path) -> None:
        (tmp_path / "qualitative.json").write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit):
            merge_qualitative(str(tmp_path))

    def test_missing_qualitative_exits(self, tmp_path: Path) -> None:
        (tmp_path / "briefing-data.json").write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit):
            merge_qualitative(str(tmp_path))

    def test_empty_qualitative(self, tmp_path: Path) -> None:
        """Empty qualitative.json patches zero fields."""
        briefing = {"qualitative": {"entity_clusters": None}}
        (tmp_path / "briefing-data.json").write_text(
            json.dumps(briefing, indent=2) + "\n", encoding="utf-8",
        )
        (tmp_path / "qualitative.json").write_text("{}\n", encoding="utf-8")
        merge_qualitative(str(tmp_path))
        result = json.loads(
            (tmp_path / "briefing-data.json").read_text(encoding="utf-8"),
        )
        assert result["qualitative"]["entity_clusters"] is None

    def test_all_null_qualitative(self, tmp_path: Path) -> None:
        """All-null qualitative.json patches zero fields."""
        briefing = {"qualitative": {"a": None, "b": None}}
        qualitative = {"a": None, "b": None}
        (tmp_path / "briefing-data.json").write_text(
            json.dumps(briefing) + "\n", encoding="utf-8",
        )
        (tmp_path / "qualitative.json").write_text(
            json.dumps(qualitative) + "\n", encoding="utf-8",
        )
        merge_qualitative(str(tmp_path))
        result = json.loads(
            (tmp_path / "briefing-data.json").read_text(encoding="utf-8"),
        )
        assert result["qualitative"]["a"] is None
        assert result["qualitative"]["b"] is None

    def test_output_is_json_with_trailing_newline(self, briefing_dir: Path) -> None:
        merge_qualitative(str(briefing_dir))
        raw = (briefing_dir / "briefing-data.json").read_text(encoding="utf-8")
        assert raw.endswith("\n")
        # Parseable JSON
        json.loads(raw)

    def test_patched_count_in_stdout(
        self, briefing_dir: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        merge_qualitative(str(briefing_dir))
        captured = capsys.readouterr()
        assert "patched 4 field(s)" in captured.out


class TestMergeQualitativeCLI:
    """Tests for CLI entry point."""

    def test_cli_runs(
        self, briefing_dir: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        main(["--dir", str(briefing_dir)])
        captured = capsys.readouterr()
        assert "patched" in captured.out

    def test_cli_missing_arg(self) -> None:
        with pytest.raises(SystemExit):
            main([])
