"""Tests for assemble_briefing_md module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from seo_pipeline.analysis.assemble_briefing_md import assemble_briefing_md, main

FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "test"
    / "fixtures"
    / "assemble-briefing-data"
    / "2026-03-09_test-keyword"
)

CANNED_MARKDOWN = (
    "# Content Briefing: Test Keyword\n"
    "\nThis is the assembled briefing.\n"
)

# Qualitative data that satisfies the pre-condition check (all 5 fields non-null)
POPULATED_QUALITATIVE = {
    "entity_clusters": [{"category": "Tools", "entities": ["google"]}],
    "geo_audit": {
        "must_haves": ["basics"],
        "hidden_gems": ["advanced"],
        "hallucination_risks": ["none"],
        "information_gaps": ["voice"],
    },
    "content_format_recommendation": {"format": "Hybrid", "rationale": "test"},
    "unique_angles": [{"angle": "AI tools", "rationale": "new"}],
    "aio_strategy": {
        "snippets": [
            {
                "topic": "kw",
                "pattern": "...",
                "target_section": "intro",
            },
        ],
    },
    "briefing": None,
}


@pytest.fixture()
def work_dir(tmp_path: Path) -> Path:
    """Copy fixture briefing-data.json with populated qualitative fields."""
    raw = json.loads((FIXTURE_DIR / "briefing-data.json").read_text(encoding="utf-8"))
    raw["qualitative"] = POPULATED_QUALITATIVE.copy()
    (tmp_path / "briefing-data.json").write_text(
        json.dumps(raw, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def work_dir_null_qualitative(tmp_path: Path) -> Path:
    """Fixture with null qualitative fields (should fail pre-condition)."""
    raw = json.loads((FIXTURE_DIR / "briefing-data.json").read_text(encoding="utf-8"))
    # qualitative fields are already null in the fixture
    (tmp_path / "briefing-data.json").write_text(
        json.dumps(raw, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return tmp_path


class TestAssembleBriefingMd:
    """Tests for assemble_briefing_md()."""

    def test_writes_brief_md(self, work_dir: Path) -> None:
        with patch(
            "seo_pipeline.analysis.assemble_briefing_md.complete",
            return_value=CANNED_MARKDOWN,
        ):
            assemble_briefing_md(str(work_dir))

        md_path = work_dir / "brief-test-keyword.md"
        assert md_path.exists()
        assert md_path.read_text(encoding="utf-8") == CANNED_MARKDOWN

    def test_updates_qualitative_briefing(self, work_dir: Path) -> None:
        with patch(
            "seo_pipeline.analysis.assemble_briefing_md.complete",
            return_value=CANNED_MARKDOWN,
        ):
            assemble_briefing_md(str(work_dir))

        briefing = json.loads(
            (work_dir / "briefing-data.json").read_text(encoding="utf-8"),
        )
        assert briefing["qualitative"]["briefing"] == "brief-test-keyword.md"

    def test_calls_complete_without_response_model(self, work_dir: Path) -> None:
        with patch(
            "seo_pipeline.analysis.assemble_briefing_md.complete",
            return_value=CANNED_MARKDOWN,
        ) as mock_complete:
            assemble_briefing_md(str(work_dir))

        mock_complete.assert_called_once()
        call_kwargs = mock_complete.call_args
        # No response_model for plain text
        assert "response_model" not in call_kwargs.kwargs

    def test_missing_briefing_data_exits(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            assemble_briefing_md(str(tmp_path))

    def test_null_qualitative_fields_exits(
        self, work_dir_null_qualitative: Path,
    ) -> None:
        with pytest.raises(SystemExit):
            assemble_briefing_md(str(work_dir_null_qualitative))

    def test_template_loaded_and_passed(self, work_dir: Path, tmp_path: Path) -> None:
        template_path = tmp_path / "template.md"
        template_path.write_text("# Template\nStructure here.", encoding="utf-8")

        with patch(
            "seo_pipeline.analysis.assemble_briefing_md.complete",
            return_value=CANNED_MARKDOWN,
        ) as mock_complete:
            assemble_briefing_md(str(work_dir), str(template_path))

        call_args = mock_complete.call_args
        messages = call_args.kwargs["messages"]
        user_content = messages[1]["content"]
        assert "Template" in user_content

    def test_tov_loaded_and_passed(self, work_dir: Path, tmp_path: Path) -> None:
        tov_path = tmp_path / "tov.md"
        tov_path.write_text("Professional and friendly.", encoding="utf-8")

        with patch(
            "seo_pipeline.analysis.assemble_briefing_md.complete",
            return_value=CANNED_MARKDOWN,
        ) as mock_complete:
            assemble_briefing_md(str(work_dir), None, str(tov_path))

        call_args = mock_complete.call_args
        messages = call_args.kwargs["messages"]
        user_content = messages[1]["content"]
        assert "Professional and friendly" in user_content

    def test_briefing_json_trailing_newline(self, work_dir: Path) -> None:
        with patch(
            "seo_pipeline.analysis.assemble_briefing_md.complete",
            return_value=CANNED_MARKDOWN,
        ):
            assemble_briefing_md(str(work_dir))

        raw = (work_dir / "briefing-data.json").read_text(encoding="utf-8")
        assert raw.endswith("\n")
        json.loads(raw)

    def test_output_in_stdout(
        self, work_dir: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        with patch(
            "seo_pipeline.analysis.assemble_briefing_md.complete",
            return_value=CANNED_MARKDOWN,
        ):
            assemble_briefing_md(str(work_dir))

        captured = capsys.readouterr()
        assert "brief-test-keyword.md" in captured.out
        assert "qualitative.briefing" in captured.out


class TestAssembleBriefingMdCLI:
    """Tests for CLI entry point."""

    def test_cli_runs(self, work_dir: Path) -> None:
        with patch(
            "seo_pipeline.analysis.assemble_briefing_md.complete",
            return_value=CANNED_MARKDOWN,
        ):
            main(["--dir", str(work_dir)])

        assert (work_dir / "brief-test-keyword.md").exists()

    def test_cli_with_template_and_tov(
        self, work_dir: Path, tmp_path: Path,
    ) -> None:
        template_path = tmp_path / "template.md"
        template_path.write_text("# T", encoding="utf-8")
        tov_path = tmp_path / "tov.md"
        tov_path.write_text("Tone", encoding="utf-8")

        with patch(
            "seo_pipeline.analysis.assemble_briefing_md.complete",
            return_value=CANNED_MARKDOWN,
        ):
            main([
                "--dir", str(work_dir),
                "--template", str(template_path),
                "--tov", str(tov_path),
            ])

        assert (work_dir / "brief-test-keyword.md").exists()

    def test_cli_missing_arg(self) -> None:
        with pytest.raises(SystemExit):
            main([])
