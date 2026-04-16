"""Tests for content drafting: prompt builder and write_draft runner."""

from pathlib import Path
from unittest.mock import patch

import pytest

from seo_pipeline.drafting.write_draft import (
    _slug_from_brief_path,
    main,
    write_draft,
)
from seo_pipeline.llm.prompts.draft import build_draft_prompt

SAMPLE_BRIEFING = """\
# Content Briefing: Test Keyword

## A. Meta-Daten & Steuerung

| Feld | Wert |
|------|------|
| **Haupt-Keyword** | test keyword (1000) |
| **URL-Slug** | /test-keyword |
| **Suchintention** | Informational |
| **Ziel-Wortanzahl** | 1500 |

## B. Keywords & Semantik

Primary: test keyword
Secondary: related term, another term
"""

CANNED_DRAFT = """\
# Draft: Test Keyword

| Feld | Wert |
|------|------|
| **Haupt-Keyword** | test keyword (1000) |
| **Neben-Keywords** | related term (500), another term (300) |
| **Title Tag** | Test Keyword: A Complete Guide |
| **Meta Description** | Learn everything about test keyword in this guide. |
| **URL-Slug** | /test-keyword |
| **Suchintention** | Informational |
| **Ziel-Wortanzahl** | 1500 |
| **Zielgruppe** | General audience |

---

# Test Keyword: The Complete Guide

This is a test draft about test keyword.
"""


class TestBuildDraftPrompt:
    """Tests for the draft prompt builder."""

    def test_returns_list_of_dicts(self) -> None:
        messages = build_draft_prompt(SAMPLE_BRIEFING, None, None)
        assert isinstance(messages, list)
        assert len(messages) == 2
        for msg in messages:
            assert isinstance(msg, dict)
            assert "role" in msg
            assert "content" in msg

    def test_system_and_user_roles(self) -> None:
        messages = build_draft_prompt(SAMPLE_BRIEFING, None, None)
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_briefing_in_user_message(self) -> None:
        messages = build_draft_prompt(SAMPLE_BRIEFING, None, None)
        user_content = messages[1]["content"]
        assert "test keyword" in user_content
        assert "Meta-Daten" in user_content

    def test_system_message_has_draft_instructions(self) -> None:
        messages = build_draft_prompt(SAMPLE_BRIEFING, None, None)
        system_content = messages[0]["content"]
        assert "SEO" in system_content
        assert "Draft" in system_content
        assert "Haupt-Keyword" in system_content

    def test_tov_in_system_message_when_provided(self) -> None:
        tov = "Write in a friendly, approachable tone."
        messages = build_draft_prompt(SAMPLE_BRIEFING, tov, None)
        system_content = messages[0]["content"]
        assert "Tone of Voice" in system_content
        assert tov in system_content
        # ToV must NOT be in user message (moved to system for priority)
        user_content = messages[1]["content"]
        assert tov not in user_content

    def test_tov_references_constraint_groups(self) -> None:
        tov = "Some ToV content."
        messages = build_draft_prompt(SAMPLE_BRIEFING, tov, None)
        system_content = messages[0]["content"]
        assert "A1-A7" in system_content
        assert "B1-B8" in system_content

    def test_tov_override_statement_in_system(self) -> None:
        tov = "Some ToV content."
        messages = build_draft_prompt(SAMPLE_BRIEFING, tov, None)
        system_content = messages[0]["content"]
        assert "ToV wins" in system_content

    def test_tov_omitted_when_none(self) -> None:
        messages = build_draft_prompt(SAMPLE_BRIEFING, None, None)
        system_content = messages[0]["content"]
        # No ToV priority block when no ToV provided
        assert "PRIORITY" not in system_content

    def test_instructions_included_when_provided(self) -> None:
        instr = "Use du instead of Sie."
        messages = build_draft_prompt(SAMPLE_BRIEFING, None, instr)
        user_content = messages[1]["content"]
        assert "Special Instructions" in user_content
        assert instr in user_content

    def test_instructions_omitted_when_none(self) -> None:
        messages = build_draft_prompt(SAMPLE_BRIEFING, None, None)
        user_content = messages[1]["content"]
        assert "Special Instructions" not in user_content

    def test_no_competing_quality_rules_in_system(self) -> None:
        """System prompt must not contain generic quality rules that
        compete with ToV constraints (issue #108)."""
        messages = build_draft_prompt(SAMPLE_BRIEFING, "Some ToV.", None)
        system_content = messages[0]["content"]
        # These generic rules were removed in favor of ToV reference
        assert "Vary sentence length" not in system_content
        assert "Avoid filler phrases" not in system_content
        assert "Match the tone and brand voice" not in system_content

    def test_both_tov_and_instructions(self) -> None:
        tov = "Formal German."
        instr = "Include personal anecdotes."
        messages = build_draft_prompt(SAMPLE_BRIEFING, tov, instr)
        # ToV in system, instructions in user
        system_content = messages[0]["content"]
        user_content = messages[1]["content"]
        assert tov in system_content
        assert instr in user_content


class TestSlugFromBriefPath:
    """Tests for slug extraction from briefing filenames."""

    def test_standard_brief_filename(self) -> None:
        assert _slug_from_brief_path(Path("brief-test-keyword.md")) == "test-keyword"

    def test_brief_with_complex_slug(self) -> None:
        path = Path("brief-some-long-slug.md")
        assert _slug_from_brief_path(path) == "some-long-slug"

    def test_fallback_for_nonstandard_name(self) -> None:
        assert _slug_from_brief_path(Path("mybriefing.md")) == "mybriefing"

    def test_nested_path(self) -> None:
        path = Path("output/2026-01-01_keyword/brief-keyword.md")
        assert _slug_from_brief_path(path) == "keyword"


class TestWriteDraft:
    """Tests for write_draft() function."""

    def test_writes_draft_file(self, tmp_path: Path) -> None:
        brief_file = tmp_path / "brief-test-keyword.md"
        brief_file.write_text(SAMPLE_BRIEFING, encoding="utf-8")

        with patch(
            "seo_pipeline.drafting.write_draft.complete",
            return_value=CANNED_DRAFT,
        ):
            write_draft(str(brief_file))

        draft_path = tmp_path / "draft-test-keyword.md"
        assert draft_path.exists()
        assert draft_path.read_text(encoding="utf-8") == CANNED_DRAFT

    def test_output_in_same_directory(self, tmp_path: Path) -> None:
        subdir = tmp_path / "output" / "2026-01-01_kw"
        subdir.mkdir(parents=True)
        brief_file = subdir / "brief-my-slug.md"
        brief_file.write_text(SAMPLE_BRIEFING, encoding="utf-8")

        with patch(
            "seo_pipeline.drafting.write_draft.complete",
            return_value=CANNED_DRAFT,
        ):
            write_draft(str(brief_file))

        draft_path = subdir / "draft-my-slug.md"
        assert draft_path.exists()

    def test_calls_complete_without_response_model(self, tmp_path: Path) -> None:
        brief_file = tmp_path / "brief-kw.md"
        brief_file.write_text(SAMPLE_BRIEFING, encoding="utf-8")

        with patch(
            "seo_pipeline.drafting.write_draft.complete",
            return_value=CANNED_DRAFT,
        ) as mock_complete:
            write_draft(str(brief_file))

        mock_complete.assert_called_once()
        call_kwargs = mock_complete.call_args
        # No response_model should be passed (plain text output)
        assert "response_model" not in call_kwargs.kwargs

    def test_passes_tov_to_system_prompt(self, tmp_path: Path) -> None:
        brief_file = tmp_path / "brief-kw.md"
        brief_file.write_text(SAMPLE_BRIEFING, encoding="utf-8")
        tov_file = tmp_path / "tov.md"
        tov_file.write_text("Be friendly.", encoding="utf-8")

        with patch(
            "seo_pipeline.drafting.write_draft.complete",
            return_value=CANNED_DRAFT,
        ) as mock_complete:
            write_draft(str(brief_file), tov_path=str(tov_file))

        messages = mock_complete.call_args.kwargs["messages"]
        system_msg = messages[0]["content"]
        assert "Be friendly." in system_msg

    def test_passes_instructions_to_prompt(self, tmp_path: Path) -> None:
        brief_file = tmp_path / "brief-kw.md"
        brief_file.write_text(SAMPLE_BRIEFING, encoding="utf-8")

        with patch(
            "seo_pipeline.drafting.write_draft.complete",
            return_value=CANNED_DRAFT,
        ) as mock_complete:
            write_draft(str(brief_file), instructions="Keep it short.")

        messages = mock_complete.call_args.kwargs["messages"]
        user_msg = messages[1]["content"]
        assert "Keep it short." in user_msg

    def test_missing_brief_exits(self) -> None:
        with pytest.raises(SystemExit):
            write_draft("/nonexistent/brief-foo.md")

    def test_log_output(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        brief_file = tmp_path / "brief-kw.md"
        brief_file.write_text(SAMPLE_BRIEFING, encoding="utf-8")

        with caplog.at_level("INFO"), patch(
            "seo_pipeline.drafting.write_draft.complete",
            return_value=CANNED_DRAFT,
        ):
            write_draft(str(brief_file))

        assert "draft-kw.md" in caplog.text


class TestWriteDraftCLI:
    """Tests for CLI entry point."""

    def test_cli_runs(self, tmp_path: Path) -> None:
        brief_file = tmp_path / "brief-cli-test.md"
        brief_file.write_text(SAMPLE_BRIEFING, encoding="utf-8")

        with patch(
            "seo_pipeline.drafting.write_draft.complete",
            return_value=CANNED_DRAFT,
        ):
            main(["--brief", str(brief_file)])

        assert (tmp_path / "draft-cli-test.md").exists()

    def test_cli_with_tov_and_instructions(self, tmp_path: Path) -> None:
        brief_file = tmp_path / "brief-full.md"
        brief_file.write_text(SAMPLE_BRIEFING, encoding="utf-8")
        tov_file = tmp_path / "tov.md"
        tov_file.write_text("Formal tone.", encoding="utf-8")

        with patch(
            "seo_pipeline.drafting.write_draft.complete",
            return_value=CANNED_DRAFT,
        ):
            main([
                "--brief", str(brief_file),
                "--tov", str(tov_file),
                "--instructions", "Keep paragraphs short.",
            ])

        assert (tmp_path / "draft-full.md").exists()

    def test_cli_missing_required_arg(self) -> None:
        with pytest.raises(SystemExit):
            main([])
