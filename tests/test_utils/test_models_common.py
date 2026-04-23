"""Tests for common.py models: Heading, LinkCount, HtmlSignals."""

import json
from pathlib import Path

import pytest

from seo_pipeline.models import Heading, HtmlSignals, LinkCount


class TestHeading:
    """Tests for the Heading model."""

    def test_heading_creation(self) -> None:
        """Test basic Heading model creation."""
        heading = Heading(level=2, text="Test Heading")
        assert heading.level == 2
        assert heading.text == "Test Heading"

    def test_heading_serialization(self) -> None:
        """Test Heading serialization to JSON."""
        heading = Heading(level=3, text="Another Heading")
        data = heading.model_dump()
        assert data == {"level": 3, "text": "Another Heading"}

    def test_heading_json_roundtrip(self) -> None:
        """Test Heading can round-trip through JSON."""
        heading = Heading(level=2, text="Strände und Buchten")
        json_str = heading.model_dump_json()
        parsed = json.loads(json_str)
        restored = Heading(**parsed)
        assert restored.level == heading.level
        assert restored.text == heading.text

    def test_heading_deserialization(self) -> None:
        """Test Heading deserialization from dict."""
        data = {"level": 2, "text": "Sample Heading"}
        heading = Heading(**data)
        assert heading.level == 2
        assert heading.text == "Sample Heading"

    def test_heading_with_special_characters(self) -> None:
        """Test Heading with special characters and umlauts."""
        heading = Heading(level=2, text="Haeufig gestellte Fragen")
        assert heading.text == "Haeufig gestellte Fragen"
        data = heading.model_dump()
        assert data["text"] == "Haeufig gestellte Fragen"


class TestLinkCount:
    """Tests for the LinkCount model."""

    def test_link_count_creation(self) -> None:
        """Test basic LinkCount model creation."""
        link_count = LinkCount(internal=42, external=18)
        assert link_count.internal == 42
        assert link_count.external == 18

    def test_link_count_serialization(self) -> None:
        """Test LinkCount serialization to JSON."""
        link_count = LinkCount(internal=100, external=50)
        data = link_count.model_dump()
        assert data == {"internal": 100, "external": 50}

    def test_link_count_json_roundtrip(self) -> None:
        """Test LinkCount can round-trip through JSON."""
        link_count = LinkCount(internal=25, external=75)
        json_str = link_count.model_dump_json()
        parsed = json.loads(json_str)
        restored = LinkCount(**parsed)
        assert restored.internal == link_count.internal
        assert restored.external == link_count.external

    def test_link_count_deserialization(self) -> None:
        """Test LinkCount deserialization from dict."""
        data = {"internal": 30, "external": 20}
        link_count = LinkCount(**data)
        assert link_count.internal == 30
        assert link_count.external == 20

    def test_link_count_zero_values(self) -> None:
        """Test LinkCount with zero links."""
        link_count = LinkCount(internal=0, external=0)
        assert link_count.internal == 0
        assert link_count.external == 0


class TestHtmlSignals:
    """Tests for the HtmlSignals model."""

    def test_html_signals_creation(self) -> None:
        """Test basic HtmlSignals model creation."""
        signals = HtmlSignals(
            faq_sections=2,
            tables=1,
            ordered_lists=0,
            unordered_lists=2,
            video_embeds=0,
            forms=0,
            images_in_content=5,
        )
        assert signals.faq_sections == 2
        assert signals.tables == 1
        assert signals.ordered_lists == 0
        assert signals.unordered_lists == 2
        assert signals.video_embeds == 0
        assert signals.forms == 0
        assert signals.images_in_content == 5

    def test_html_signals_serialization(self) -> None:
        """Test HtmlSignals serialization to JSON."""
        signals = HtmlSignals(
            faq_sections=1,
            tables=2,
            ordered_lists=1,
            unordered_lists=3,
            video_embeds=2,
            forms=1,
            images_in_content=10,
        )
        data = signals.model_dump()
        expected = {
            "faq_sections": 1,
            "tables": 2,
            "ordered_lists": 1,
            "unordered_lists": 3,
            "video_embeds": 2,
            "forms": 1,
            "images_in_content": 10,
        }
        assert data == expected

    def test_html_signals_field_order(self) -> None:
        """Test that HtmlSignals fields are in the correct order for JSON serialization.

        This verifies that the field order matches the fixture JSON key order.
        """
        signals = HtmlSignals(
            faq_sections=2,
            tables=1,
            ordered_lists=0,
            unordered_lists=2,
            video_embeds=0,
            forms=0,
            images_in_content=5,
        )
        json_str = signals.model_dump_json()
        data = json.loads(json_str)

        # Verify the order by checking keys in sequence
        keys = list(data.keys())
        expected_order = [
            "faq_sections",
            "tables",
            "ordered_lists",
            "unordered_lists",
            "video_embeds",
            "forms",
            "images_in_content",
        ]
        assert keys == expected_order

    def test_html_signals_json_roundtrip(self) -> None:
        """Test HtmlSignals can round-trip through JSON."""
        signals = HtmlSignals(
            faq_sections=3,
            tables=2,
            ordered_lists=1,
            unordered_lists=4,
            video_embeds=1,
            forms=2,
            images_in_content=8,
        )
        json_str = signals.model_dump_json()
        parsed = json.loads(json_str)
        restored = HtmlSignals(**parsed)
        assert restored.faq_sections == signals.faq_sections
        assert restored.tables == signals.tables
        assert restored.ordered_lists == signals.ordered_lists
        assert restored.unordered_lists == signals.unordered_lists
        assert restored.video_embeds == signals.video_embeds
        assert restored.forms == signals.forms
        assert restored.images_in_content == signals.images_in_content

    def test_html_signals_deserialization(self) -> None:
        """Test HtmlSignals deserialization from dict."""
        data = {
            "faq_sections": 2,
            "tables": 1,
            "ordered_lists": 0,
            "unordered_lists": 2,
            "video_embeds": 0,
            "forms": 0,
            "images_in_content": 5,
        }
        signals = HtmlSignals(**data)
        assert signals.faq_sections == 2
        assert signals.tables == 1
        assert signals.ordered_lists == 0
        assert signals.unordered_lists == 2
        assert signals.video_embeds == 0
        assert signals.forms == 0
        assert signals.images_in_content == 5

    def test_html_signals_all_zeros(self) -> None:
        """Test HtmlSignals with all zero values."""
        signals = HtmlSignals(
            faq_sections=0,
            tables=0,
            ordered_lists=0,
            unordered_lists=0,
            video_embeds=0,
            forms=0,
            images_in_content=0,
        )
        assert signals.faq_sections == 0
        assert signals.tables == 0
        assert signals.ordered_lists == 0
        assert signals.unordered_lists == 0
        assert signals.video_embeds == 0
        assert signals.forms == 0
        assert signals.images_in_content == 0

    def test_html_signals_matches_fixture(self) -> None:
        """Test HtmlSignals against the page-alpha fixture data.

        This ensures the model correctly deserializes the test fixture.
        """
        fixture_path = Path(
            "/Users/marco.funk/Code/ContentCreationPipeline/tests/fixtures/"
            "analyze-page-structure/pages/page-alpha.json"
        )

        if not fixture_path.exists():
            pytest.skip(f"Fixture file not found: {fixture_path}")

        with open(fixture_path) as f:
            fixture = json.load(f)

        html_signals_data = fixture.get("html_signals")
        if html_signals_data is None:
            pytest.skip("html_signals not found in fixture")

        signals = HtmlSignals(**html_signals_data)
        assert signals.faq_sections == 2
        assert signals.tables == 1
        assert signals.ordered_lists == 0
        assert signals.unordered_lists == 2
        assert signals.video_embeds == 0
        assert signals.forms == 0
        assert signals.images_in_content == 5


class TestHeadingsListIntegration:
    """Tests for lists of Heading objects (common usage pattern)."""

    def test_heading_list_serialization(self) -> None:
        """Test serialization of a list of Heading objects."""
        headings = [
            Heading(level=2, text="Strände und Buchten"),
            Heading(level=2, text="Haeufig gestellte Fragen"),
            Heading(level=3, text="Wie komme ich nach Mallorca?"),
        ]

        data = [h.model_dump() for h in headings]
        assert len(data) == 3
        assert data[0]["level"] == 2
        assert data[0]["text"] == "Strände und Buchten"
        assert data[1]["level"] == 2
        assert data[1]["text"] == "Haeufig gestellte Fragen"
        assert data[2]["level"] == 3
        assert data[2]["text"] == "Wie komme ich nach Mallorca?"

    def test_heading_list_deserialization(self) -> None:
        """Test deserialization of a list of Heading objects."""
        data = [
            {"level": 2, "text": "Section 1"},
            {"level": 3, "text": "Subsection 1.1"},
            {"level": 2, "text": "Section 2"},
        ]

        headings = [Heading(**d) for d in data]
        assert len(headings) == 3
        assert headings[0].text == "Section 1"
        assert headings[1].level == 3
        assert headings[2].text == "Section 2"

    def test_heading_list_from_fixture(self) -> None:
        """Test Heading list deserialization from fixture."""
        fixture_path = Path(
            "/Users/marco.funk/Code/ContentCreationPipeline/tests/fixtures/"
            "analyze-page-structure/pages/page-alpha.json"
        )

        if not fixture_path.exists():
            pytest.skip(f"Fixture file not found: {fixture_path}")

        with open(fixture_path) as f:
            fixture = json.load(f)

        headings_data = fixture.get("headings", [])
        headings = [Heading(**h) for h in headings_data]

        assert len(headings) == 5
        assert headings[0].level == 2
        assert headings[0].text == "Strände und Buchten"
        assert headings[1].level == 2
        assert headings[1].text == "Haeufig gestellte Fragen"
        assert headings[2].level == 3
        assert headings[2].text == "Wie komme ich nach Mallorca?"
        assert headings[3].level == 3
        assert headings[3].text == "Wann ist die beste Reisezeit?"
        assert headings[4].level == 2
        assert headings[4].text == "Aktivitaeten und Sport"
