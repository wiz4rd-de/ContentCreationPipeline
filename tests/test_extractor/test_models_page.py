"""Tests for page extraction models and their serialization."""

import json
from pathlib import Path

import pytest

from seo_pipeline.models import ExtractedPage, ExtractedPageError


@pytest.fixture
def page_fixtures_dir() -> Path:
    """Return path to page fixtures directory."""
    return Path(__file__).parent.parent.parent / "test" / "fixtures"


class TestExtractedPage:
    """Tests for the ExtractedPage model."""

    def test_minimal_page(self):
        """Test ExtractedPage with only required field."""
        page = ExtractedPage(url="https://example.com")
        assert page.url == "https://example.com"
        assert page.title == ""
        assert page.meta_description == ""
        assert page.headings == []
        assert page.word_count == 0

    def test_full_page(self):
        """Test ExtractedPage with all fields populated."""
        page = ExtractedPage(
            url="https://example.com/page",
            title="Example Page",
            meta_description="A description",
            canonical_url="https://example.com/page",
            og_title="OG Title",
            og_description="OG Description",
            h1="Main Heading",
            headings=[],
            word_count=100,
            link_count={"internal": 5, "external": 2},
            main_content_text="Some content",
            main_content_preview="Some content...",
            readability_title="Readability Title",
            html_signals={
                "faq_sections": 0,
                "tables": 1,
                "ordered_lists": 0,
                "unordered_lists": 2,
                "video_embeds": 0,
                "forms": 0,
                "images_in_content": 3,
            },
        )
        assert page.url == "https://example.com/page"
        assert page.title == "Example Page"
        assert page.word_count == 100

    def test_page_with_headings(self):
        """Test ExtractedPage with heading data."""
        page = ExtractedPage(
            url="https://example.com",
            headings=[
                {"level": 2, "text": "Section One"},
                {"level": 2, "text": "Section Two"},
            ],
        )
        assert len(page.headings) == 2
        assert page.headings[0].level == 2
        assert page.headings[0].text == "Section One"

    def test_roundtrip_analyze_content_topics_page_alpha(self, page_fixtures_dir):
        """Test roundtrip serialization matches page-alpha.json."""
        fixture_file = (
            page_fixtures_dir / "analyze-content-topics" / "pages" / "page-alpha.json"
        )
        with open(fixture_file) as f:
            original_data = json.load(f)

        # Deserialize from fixture
        page = ExtractedPage(**original_data)

        # Serialize back
        serialized = page.model_dump(mode="json")

        # Should match original (with defaults added)
        assert serialized["url"] == original_data["url"]
        assert serialized["main_content_text"] == original_data["main_content_text"]
        assert serialized["headings"] == original_data["headings"]
        assert serialized["html_signals"] == original_data["html_signals"]

    def test_roundtrip_analyze_content_topics_page_beta(self, page_fixtures_dir):
        """Test roundtrip serialization matches page-beta.json."""
        fixture_file = (
            page_fixtures_dir / "analyze-content-topics" / "pages" / "page-beta.json"
        )
        with open(fixture_file) as f:
            original_data = json.load(f)

        page = ExtractedPage(**original_data)
        serialized = page.model_dump(mode="json")

        assert serialized["url"] == original_data["url"]
        assert serialized["html_signals"] == original_data["html_signals"]

    def test_roundtrip_analyze_page_structure_page_alpha(self, page_fixtures_dir):
        """Test roundtrip serialization matches page-alpha.json."""
        fixture_file = (
            page_fixtures_dir / "analyze-page-structure" / "pages" / "page-alpha.json"
        )
        with open(fixture_file) as f:
            original_data = json.load(f)

        page = ExtractedPage(**original_data)
        serialized = page.model_dump(mode="json")

        assert serialized["url"] == original_data["url"]
        assert serialized["headings"] == original_data["headings"]

    def test_integration_fixture_roundtrip(self, page_fixtures_dir):
        """Test roundtrip serialization with integration fixture."""
        fixture_file = (
            page_fixtures_dir / "integration" / "pages" / "alpha.example.com.json"
        )
        with open(fixture_file) as f:
            original_data = json.load(f)

        page = ExtractedPage(**original_data)
        serialized = page.model_dump(mode="json")

        # Verify roundtrip preserves key fields
        assert serialized["url"] == original_data["url"]
        assert serialized["main_content_text"] == original_data["main_content_text"]


class TestExtractedPageError:
    """Tests for the ExtractedPageError model."""

    def test_error_creation(self):
        """Test ExtractedPageError instantiation."""
        error = ExtractedPageError(
            error="Failed to fetch URL",
            url="https://example.com",
        )
        assert error.error == "Failed to fetch URL"
        assert error.url == "https://example.com"

    def test_roundtrip_error_fixture(self, page_fixtures_dir):
        """Test roundtrip serialization with error fixture."""
        fixture_file = page_fixtures_dir / "extract-page" / "page-error.json"
        with open(fixture_file) as f:
            original_data = json.load(f)

        error = ExtractedPageError(**original_data)
        serialized = error.model_dump(mode="json")

        assert serialized == original_data

    def test_error_roundtrip_arbitrary_message(self):
        """Test roundtrip with arbitrary error message."""
        original = {
            "error": "Connection timeout: took 15000ms",
            "url": "https://slow-site.example.com",
        }
        error = ExtractedPageError(**original)
        serialized = error.model_dump(mode="json")

        assert serialized == original
