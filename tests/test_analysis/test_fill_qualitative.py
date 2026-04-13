"""Tests for fill_qualitative module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from seo_pipeline.analysis.fill_qualitative import fill_qualitative, main
from seo_pipeline.models.llm_responses import QualitativeResponse

FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "test"
    / "fixtures"
    / "assemble-briefing-data"
    / "2026-03-09_test-keyword"
)

# Canned response that matches QualitativeResponse schema
CANNED_QUALITATIVE = QualitativeResponse.model_validate({
    "entity_clusters": [
        {
            "category": "Tools",
            "entities": ["google", "semrush"],
            "synonyms": [{"entity": "google", "synonyms": ["Google Search"]}],
        },
    ],
    "geo_audit": {
        "must_haves": ["keyword research basics"],
        "hidden_gems": ["long-tail strategy"],
        "hallucination_risks": ["incorrect volume claims"],
        "information_gaps": ["voice search optimization"],
    },
    "content_format_recommendation": {
        "format": "Hybrid",
        "rationale": "Mix of guide and list works best.",
    },
    "unique_angles": [
        {"angle": "AI-powered keyword research", "rationale": "Emerging trend"},
    ],
    "aio_strategy": {
        "snippets": [
            {
                "topic": "keyword research",
                "pattern": "Keyword research is the process of...",
                "target_section": "Introduction",
            },
        ],
    },
})


@pytest.fixture()
def work_dir(tmp_path: Path) -> Path:
    """Copy the fixture briefing-data.json into a temp directory."""
    src = FIXTURE_DIR / "briefing-data.json"
    dst = tmp_path / "briefing-data.json"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


class TestFillQualitative:
    """Tests for fill_qualitative()."""

    def test_writes_qualitative_json(self, work_dir: Path) -> None:
        with patch(
            "seo_pipeline.analysis.fill_qualitative.complete",
            return_value=CANNED_QUALITATIVE,
        ):
            fill_qualitative(str(work_dir))

        qual_path = work_dir / "qualitative.json"
        assert qual_path.exists()
        data = json.loads(qual_path.read_text(encoding="utf-8"))
        assert "entity_clusters" in data
        assert "geo_audit" in data
        assert "content_format_recommendation" in data
        assert "unique_angles" in data
        assert "aio_strategy" in data

    def test_qualitative_json_has_correct_structure(self, work_dir: Path) -> None:
        with patch(
            "seo_pipeline.analysis.fill_qualitative.complete",
            return_value=CANNED_QUALITATIVE,
        ):
            fill_qualitative(str(work_dir))

        data = json.loads(
            (work_dir / "qualitative.json").read_text(encoding="utf-8"),
        )
        assert isinstance(data["entity_clusters"], list)
        assert data["entity_clusters"][0]["category"] == "Tools"
        assert data["geo_audit"]["must_haves"] == ["keyword research basics"]
        assert data["content_format_recommendation"]["format"] == "Hybrid"

    def test_merges_into_briefing_data(self, work_dir: Path) -> None:
        with patch(
            "seo_pipeline.analysis.fill_qualitative.complete",
            return_value=CANNED_QUALITATIVE,
        ):
            fill_qualitative(str(work_dir))

        briefing = json.loads(
            (work_dir / "briefing-data.json").read_text(encoding="utf-8"),
        )
        qual = briefing["qualitative"]
        assert qual["entity_clusters"] is not None
        assert qual["geo_audit"] is not None
        assert qual["content_format_recommendation"] is not None

    def test_calls_complete_with_response_model(self, work_dir: Path) -> None:
        with patch(
            "seo_pipeline.analysis.fill_qualitative.complete",
            return_value=CANNED_QUALITATIVE,
        ) as mock_complete:
            fill_qualitative(str(work_dir))

        mock_complete.assert_called_once()
        call_kwargs = mock_complete.call_args
        assert call_kwargs.kwargs.get("response_model") is QualitativeResponse

    def test_missing_briefing_data_exits(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            fill_qualitative(str(tmp_path))

    def test_qualitative_json_trailing_newline(self, work_dir: Path) -> None:
        with patch(
            "seo_pipeline.analysis.fill_qualitative.complete",
            return_value=CANNED_QUALITATIVE,
        ):
            fill_qualitative(str(work_dir))

        raw = (work_dir / "qualitative.json").read_text(encoding="utf-8")
        assert raw.endswith("\n")
        # Parseable JSON
        json.loads(raw)

    def test_output_in_log(
        self, work_dir: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level("INFO"), patch(
            "seo_pipeline.analysis.fill_qualitative.complete",
            return_value=CANNED_QUALITATIVE,
        ):
            fill_qualitative(str(work_dir))

        assert "qualitative.json" in caplog.text
        assert "patched" in caplog.text


class TestFillQualitativeCLI:
    """Tests for CLI entry point."""

    def test_cli_runs(self, work_dir: Path) -> None:
        with patch(
            "seo_pipeline.analysis.fill_qualitative.complete",
            return_value=CANNED_QUALITATIVE,
        ):
            main(["--dir", str(work_dir)])

        assert (work_dir / "qualitative.json").exists()

    def test_cli_missing_arg(self) -> None:
        with pytest.raises(SystemExit):
            main([])
