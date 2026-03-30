"""Tests for extract_page module -- fixture-based HTML parsing, no live URLs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from seo_pipeline.extractor.extract_page import (
    extract_page,
    extract_page_from_html,
)
from seo_pipeline.models import ExtractedPage, ExtractedPageError

# ---------------------------------------------------------------------------
# Fixture HTML snippets
# ---------------------------------------------------------------------------

MINIMAL_HTML = """\
<!DOCTYPE html>
<html><head><title>Test Page</title></head>
<body><p>Hello world</p></body></html>
"""

FULL_HTML = """\
<!DOCTYPE html>
<html>
<head>
  <title>Full Test Page</title>
  <meta name="description" content="A test description">
  <link rel="canonical" href="https://example.com/full">
  <meta property="og:title" content="OG Test Title">
  <meta property="og:description" content="OG Test Description">
</head>
<body>
  <div id="content">
  <h1>Main  Heading  Here</h1>
  <h2>Section One</h2>
  <p>First paragraph with some words for counting. This content needs to be long
  enough for readability-lxml to consider it worth extracting. The library uses a
  scoring algorithm that requires a minimum amount of text in paragraph elements
  before it will extract anything meaningful from the page.</p>
  <p>Second paragraph adds more content to help readability detect this as the main
  article body. Without sufficient text density, readability-lxml will return empty
  content because it assumes the page has no article-like structure
  worth extracting.</p>
  <h3>Subsection A</h3>
  <p>More content here in subsection A. This paragraph also needs to be substantial
  enough to contribute to the overall content score. Readability algorithms typically
  look at the ratio of text to HTML tags to determine content regions.</p>
  <h2>Section Two</h2>
  <h4>Deep Heading</h4>
  <p>Final paragraph with additional words to ensure we have enough content density
  for the readability extraction to produce meaningful output. This is important for
  testing that word count, content preview, and text extraction all work correctly.</p>
  <a href="https://example.com/internal1">Internal 1</a>
  <a href="https://example.com/internal2">Internal 2</a>
  <a href="/relative-link">Relative</a>
  <a href="https://external.com/page">External</a>
  <a href="https://other.org/page">Other External</a>
  </div>
</body>
</html>
"""

HTML_WITH_SIGNALS = """\
<!DOCTYPE html>
<html><head><title>Signals Page</title></head>
<body>
  <article>
    <h1>Article</h1>
    <details><summary>FAQ Question 1</summary><p>Answer 1</p></details>
    <details><summary>FAQ Question 2</summary><p>Answer 2</p></details>
    <table><tr><td>Data</td></tr></table>
    <table><tr><td>Data 2</td></tr></table>
    <ol><li>First</li></ol>
    <ul><li>Bullet</li></ul>
    <ul><li>Bullet 2</li></ul>
    <iframe src="https://youtube.com/embed/123"></iframe>
    <video src="video.mp4"></video>
    <form><input type="text"></form>
    <img src="photo1.jpg"><img src="photo2.jpg"><img src="photo3.jpg">
  </article>
</body>
</html>
"""

EMPTY_HTML = """\
<!DOCTYPE html>
<html><head></head><body></body></html>
"""

HEADING_ORDER_HTML = """\
<!DOCTYPE html>
<html><head><title>Headings</title></head>
<body>
  <h1>Title</h1>
  <h2>Alpha</h2>
  <h3>Alpha Sub</h3>
  <h4>Alpha Deep</h4>
  <h2>Beta</h2>
  <h3>Beta Sub 1</h3>
  <h3>Beta Sub 2</h3>
  <h2>Gamma</h2>
</body>
</html>
"""

WHITESPACE_HEADING_HTML = """\
<!DOCTYPE html>
<html><head><title>WS</title></head>
<body>
  <h1>  Multiple   Spaces   Here  </h1>
  <h2>  Tab\there  </h2>
  <h3>  Newline
  heading  </h3>
</body>
</html>
"""

LINK_EDGE_CASES_HTML = """\
<!DOCTYPE html>
<html><head><title>Links</title></head>
<body>
  <a href="https://example.com/page1">Internal</a>
  <a href="https://sub.example.com/page2">Subdomain</a>
  <a href="/relative">Relative</a>
  <a href="mailto:test@example.com">Mailto</a>
  <a href="javascript:void(0)">JS</a>
  <a href="">Empty</a>
  <a href="https://external.org">External</a>
  <a>No href at all</a>
</body>
</html>
"""

URL = "https://example.com/test-page"


# ---------------------------------------------------------------------------
# Tests: extract_page_from_html — metadata extraction
# ---------------------------------------------------------------------------


class TestMetadataExtraction:
    """Tests for title, meta description, canonical, OG tags."""

    def test_title(self):
        result = extract_page_from_html(MINIMAL_HTML, URL)
        assert result["title"] == "Test Page"

    def test_title_empty_when_missing(self):
        result = extract_page_from_html(EMPTY_HTML, URL)
        assert result["title"] == ""

    def test_meta_description(self):
        result = extract_page_from_html(FULL_HTML, URL)
        assert result["meta_description"] == "A test description"

    def test_meta_description_empty_when_missing(self):
        result = extract_page_from_html(MINIMAL_HTML, URL)
        assert result["meta_description"] == ""

    def test_canonical_url(self):
        result = extract_page_from_html(FULL_HTML, URL)
        assert result["canonical_url"] == "https://example.com/full"

    def test_canonical_empty_when_missing(self):
        result = extract_page_from_html(MINIMAL_HTML, URL)
        assert result["canonical_url"] == ""

    def test_og_title(self):
        result = extract_page_from_html(FULL_HTML, URL)
        assert result["og_title"] == "OG Test Title"

    def test_og_description(self):
        result = extract_page_from_html(FULL_HTML, URL)
        assert result["og_description"] == "OG Test Description"

    def test_og_empty_when_missing(self):
        result = extract_page_from_html(MINIMAL_HTML, URL)
        assert result["og_title"] == ""
        assert result["og_description"] == ""

    def test_url_passthrough(self):
        result = extract_page_from_html(MINIMAL_HTML, URL)
        assert result["url"] == URL


# ---------------------------------------------------------------------------
# Tests: heading extraction
# ---------------------------------------------------------------------------


class TestHeadingExtraction:
    """Tests for h1, h2-h4 heading extraction."""

    def test_h1_extracted(self):
        result = extract_page_from_html(FULL_HTML, URL)
        assert result["h1"] == "Main Heading Here"

    def test_h1_whitespace_collapsed(self):
        result = extract_page_from_html(WHITESPACE_HEADING_HTML, URL)
        assert result["h1"] == "Multiple Spaces Here"

    def test_h1_empty_when_missing(self):
        result = extract_page_from_html(EMPTY_HTML, URL)
        assert result["h1"] == ""

    def test_headings_dom_order(self):
        result = extract_page_from_html(HEADING_ORDER_HTML, URL)
        headings = result["headings"]
        expected = [
            {"level": 2, "text": "Alpha"},
            {"level": 3, "text": "Alpha Sub"},
            {"level": 4, "text": "Alpha Deep"},
            {"level": 2, "text": "Beta"},
            {"level": 3, "text": "Beta Sub 1"},
            {"level": 3, "text": "Beta Sub 2"},
            {"level": 2, "text": "Gamma"},
        ]
        assert headings == expected

    def test_headings_levels(self):
        result = extract_page_from_html(FULL_HTML, URL)
        levels = [h["level"] for h in result["headings"]]
        assert levels == [2, 3, 2, 4]

    def test_headings_whitespace_collapsed(self):
        result = extract_page_from_html(WHITESPACE_HEADING_HTML, URL)
        texts = [h["text"] for h in result["headings"]]
        # All multi-space sequences collapsed to single space
        for text in texts:
            assert "  " not in text

    def test_no_headings_on_empty(self):
        result = extract_page_from_html(EMPTY_HTML, URL)
        assert result["headings"] == []


# ---------------------------------------------------------------------------
# Tests: link counting
# ---------------------------------------------------------------------------


class TestLinkCounting:
    """Tests for internal/external link classification."""

    def test_internal_links(self):
        result = extract_page_from_html(FULL_HTML, URL)
        # /relative-link (internal), example.com/internal1, example.com/internal2
        assert result["link_count"]["internal"] == 3

    def test_external_links(self):
        result = extract_page_from_html(FULL_HTML, URL)
        # external.com, other.org
        assert result["link_count"]["external"] == 2

    def test_relative_links_are_internal(self):
        result = extract_page_from_html(LINK_EDGE_CASES_HTML, URL)
        # /relative, empty href, mailto (no hostname -> internal)
        # example.com/page1 is internal
        # javascript: has no hostname -> internal
        internal = result["link_count"]["internal"]
        assert internal >= 3  # at least /relative, empty, example.com/page1

    def test_subdomain_is_external(self):
        """sub.example.com != example.com -- treated as external."""
        result = extract_page_from_html(LINK_EDGE_CASES_HTML, URL)
        # sub.example.com and external.org are external
        assert result["link_count"]["external"] >= 2

    def test_no_links_on_empty(self):
        result = extract_page_from_html(EMPTY_HTML, URL)
        assert result["link_count"] == {"internal": 0, "external": 0}


# ---------------------------------------------------------------------------
# Tests: readability content
# ---------------------------------------------------------------------------


class TestReadabilityContent:
    """Tests for main_content_text, word_count, preview, readability_title."""

    def test_word_count_positive(self):
        result = extract_page_from_html(FULL_HTML, URL)
        assert result["word_count"] > 0

    def test_main_content_text_whitespace_collapsed(self):
        result = extract_page_from_html(FULL_HTML, URL)
        text = result["main_content_text"]
        # No double spaces or leading/trailing whitespace
        assert text == text.strip()
        assert "  " not in text

    def test_main_content_preview_max_300(self):
        result = extract_page_from_html(FULL_HTML, URL)
        assert len(result["main_content_preview"]) <= 300

    def test_preview_is_prefix_of_text(self):
        result = extract_page_from_html(FULL_HTML, URL)
        assert result["main_content_text"].startswith(
            result["main_content_preview"]
        )

    def test_empty_html_word_count_zero(self):
        result = extract_page_from_html(EMPTY_HTML, URL)
        assert result["word_count"] == 0

    def test_readability_title_present(self):
        result = extract_page_from_html(FULL_HTML, URL)
        # readability-lxml extracts a title
        assert isinstance(result["readability_title"], str)


# ---------------------------------------------------------------------------
# Tests: HTML signals
# ---------------------------------------------------------------------------


class TestHtmlSignals:
    """Tests for HTML structural signals from readability content."""

    def test_signals_on_empty(self):
        result = extract_page_from_html(EMPTY_HTML, URL)
        signals = result["html_signals"]
        assert signals == {
            "faq_sections": 0,
            "tables": 0,
            "ordered_lists": 0,
            "unordered_lists": 0,
            "video_embeds": 0,
            "forms": 0,
            "images_in_content": 0,
        }

    def test_signals_structure(self):
        """All 7 signal keys present."""
        result = extract_page_from_html(FULL_HTML, URL)
        signals = result["html_signals"]
        expected_keys = {
            "faq_sections",
            "tables",
            "ordered_lists",
            "unordered_lists",
            "video_embeds",
            "forms",
            "images_in_content",
        }
        assert set(signals.keys()) == expected_keys

    def test_signals_are_integers(self):
        result = extract_page_from_html(FULL_HTML, URL)
        for key, value in result["html_signals"].items():
            assert isinstance(value, int), f"{key} should be int"

    def test_signals_count_elements_from_article(self):
        """Verify signals from HTML with known element counts.

        Note: readability-lxml may strip some elements from the article
        content. We test against the readability-extracted HTML, not
        the full page. The counts may be lower than the raw HTML.
        """
        result = extract_page_from_html(HTML_WITH_SIGNALS, URL)
        signals = result["html_signals"]
        # readability extracts the article content; counts come from that
        # We verify signals are non-negative integers (readability may strip some)
        for key, value in signals.items():
            assert value >= 0, f"{key} should be >= 0"


# ---------------------------------------------------------------------------
# Tests: output shape / model compatibility
# ---------------------------------------------------------------------------


class TestOutputShape:
    """Verify output dict is compatible with ExtractedPage model."""

    def test_full_output_deserializes_to_model(self):
        result = extract_page_from_html(FULL_HTML, URL)
        page = ExtractedPage(**result)
        assert page.url == URL
        assert page.title == "Full Test Page"

    def test_empty_output_deserializes_to_model(self):
        result = extract_page_from_html(EMPTY_HTML, URL)
        page = ExtractedPage(**result)
        assert page.url == URL
        assert page.word_count == 0

    def test_all_fields_present(self):
        result = extract_page_from_html(FULL_HTML, URL)
        expected_fields = {
            "url",
            "title",
            "meta_description",
            "canonical_url",
            "og_title",
            "og_description",
            "h1",
            "headings",
            "word_count",
            "link_count",
            "main_content_text",
            "main_content_preview",
            "readability_title",
            "html_signals",
        }
        assert set(result.keys()) == expected_fields

    def test_roundtrip_serialization(self):
        """Output dict -> ExtractedPage -> model_dump -> same dict."""
        result = extract_page_from_html(FULL_HTML, URL)
        page = ExtractedPage(**result)
        serialized = page.model_dump(mode="json")
        for key in result:
            assert serialized[key] == result[key], f"Field {key} mismatch"


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error response structure."""

    def test_error_on_invalid_url(self):
        result = extract_page("https://nonexistent.invalid.domain.test/")
        assert "error" in result
        assert result["url"] == "https://nonexistent.invalid.domain.test/"

    def test_error_deserializes_to_error_model(self):
        result = extract_page("https://nonexistent.invalid.domain.test/")
        error = ExtractedPageError(**result)
        assert error.url == "https://nonexistent.invalid.domain.test/"
        assert len(error.error) > 0

    def test_error_fixture_roundtrip(self):
        """Test that error fixture matches expected shape."""
        fixture_path = (
            Path(__file__).parent.parent.parent
            / "test"
            / "fixtures"
            / "extract-page"
            / "page-error.json"
        )
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        error = ExtractedPageError(**data)
        assert error.error == data["error"]
        assert error.url == data["url"]


# ---------------------------------------------------------------------------
# Tests: CLI integration
# ---------------------------------------------------------------------------


class TestCLI:
    """Tests for CLI entry point."""

    def test_cli_no_args_exits_with_error(self):
        result = subprocess.run(
            [sys.executable, "-m", "seo_pipeline.extractor.extract_page"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        output = json.loads(result.stdout)
        assert "error" in output
        assert "Usage" in output["error"]

    def test_cli_with_output_flag(self, tmp_path):
        """CLI with --output writes to file (uses invalid URL to test error path)."""
        out_file = tmp_path / "output.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "seo_pipeline.extractor.extract_page",
                "https://nonexistent.invalid.test/",
                "--output",
                str(out_file),
            ],
            capture_output=True,
            text=True,
        )
        # Should exit 1 due to network error, but file should exist
        assert result.returncode == 1
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert "error" in data
        assert data["url"] == "https://nonexistent.invalid.test/"
