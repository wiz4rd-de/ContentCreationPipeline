"""Tests for qualitative prompt builders."""

import json
from pathlib import Path

import pytest

from seo_pipeline.llm.prompts.qualitative import (
    build_briefing_assembly_prompt,
    build_qualitative_prompt,
)
from seo_pipeline.models.analysis import BriefingData

FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "test"
    / "fixtures"
    / "assemble-briefing-data"
    / "2026-03-09_test-keyword"
)


@pytest.fixture()
def briefing_data() -> BriefingData:
    """Load the test fixture briefing data."""
    raw = json.loads((FIXTURE_DIR / "briefing-data.json").read_text(encoding="utf-8"))
    return BriefingData.model_validate(raw)


class TestBuildQualitativePrompt:
    """Tests for build_qualitative_prompt()."""

    def test_returns_list_of_dicts(self, briefing_data: BriefingData) -> None:
        messages = build_qualitative_prompt(briefing_data)
        assert isinstance(messages, list)
        assert len(messages) == 2

    def test_has_system_and_user_roles(self, briefing_data: BriefingData) -> None:
        messages = build_qualitative_prompt(briefing_data)
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_messages_have_content(self, briefing_data: BriefingData) -> None:
        messages = build_qualitative_prompt(briefing_data)
        for msg in messages:
            assert "content" in msg
            assert len(msg["content"]) > 0

    def test_seed_keyword_in_user_message(self, briefing_data: BriefingData) -> None:
        messages = build_qualitative_prompt(briefing_data)
        assert "test keyword" in messages[1]["content"]

    def test_all_five_fields_mentioned(self, briefing_data: BriefingData) -> None:
        messages = build_qualitative_prompt(briefing_data)
        user_content = messages[1]["content"]
        assert "entity_clusters" in user_content
        assert "geo_audit" in user_content
        assert "content_format_recommendation" in user_content
        assert "unique_angles" in user_content
        assert "aio_strategy" in user_content

    def test_contains_section_labels(self, briefing_data: BriefingData) -> None:
        messages = build_qualitative_prompt(briefing_data)
        user_content = messages[1]["content"]
        assert "2.1A" in user_content
        assert "2.1B" in user_content
        assert "2.1C" in user_content
        assert "2.1D" in user_content
        assert "2.1E" in user_content

    def test_briefing_data_serialized_in_user_message(
        self, briefing_data: BriefingData,
    ) -> None:
        messages = build_qualitative_prompt(briefing_data)
        user_content = messages[1]["content"]
        # The serialized JSON should include the seed keyword
        assert '"test keyword"' in user_content

    def test_system_forbids_modifying_numbers(
        self, briefing_data: BriefingData,
    ) -> None:
        messages = build_qualitative_prompt(briefing_data)
        system_content = messages[0]["content"]
        assert "NOT re-count" in system_content or "do NOT" in system_content.lower()


class TestBuildBriefingAssemblyPrompt:
    """Tests for build_briefing_assembly_prompt()."""

    def test_returns_list_of_dicts(self, briefing_data: BriefingData) -> None:
        messages = build_briefing_assembly_prompt(briefing_data, None, None)
        assert isinstance(messages, list)
        assert len(messages) == 2

    def test_has_system_and_user_roles(self, briefing_data: BriefingData) -> None:
        messages = build_briefing_assembly_prompt(briefing_data, None, None)
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_seed_keyword_in_user_message(self, briefing_data: BriefingData) -> None:
        messages = build_briefing_assembly_prompt(briefing_data, None, None)
        assert "test keyword" in messages[1]["content"]

    def test_template_included_when_provided(
        self, briefing_data: BriefingData,
    ) -> None:
        template = "# My Template\n\nSection structure here."
        messages = build_briefing_assembly_prompt(briefing_data, template, None)
        assert "My Template" in messages[1]["content"]

    def test_tov_included_when_provided(self, briefing_data: BriefingData) -> None:
        tov = "Friendly, professional tone."
        messages = build_briefing_assembly_prompt(briefing_data, None, tov)
        assert "Friendly, professional tone" in messages[1]["content"]

    def test_template_and_tov_absent_when_none(
        self, briefing_data: BriefingData,
    ) -> None:
        messages = build_briefing_assembly_prompt(briefing_data, None, None)
        user_content = messages[1]["content"]
        assert "Content Template" not in user_content
        assert "Tone of Voice" not in user_content

    def test_briefing_sections_referenced(self, briefing_data: BriefingData) -> None:
        messages = build_briefing_assembly_prompt(briefing_data, None, None)
        user_content = messages[1]["content"]
        assert "Strategische Ausrichtung" in user_content
        assert "Keywords & Semantik" in user_content
        assert "Seitenaufbau" in user_content
        assert "Differenzierungs-Chancen" in user_content
        assert "AI-Overview-Optimierung" in user_content
        assert "FAQ-Sektion" in user_content
        assert "Content-Struktur" in user_content
        assert "Informationsluecken" in user_content
        assert "Keyword-Referenz" in user_content

    def test_system_forbids_modifying_numbers(
        self, briefing_data: BriefingData,
    ) -> None:
        messages = build_briefing_assembly_prompt(briefing_data, None, None)
        system_content = messages[0]["content"]
        assert "NOT re-count" in system_content or "do NOT" in system_content.lower()
