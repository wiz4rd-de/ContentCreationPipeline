"""Tests for assemble_competitors module -- golden file parity and unit tests."""

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from seo_pipeline.serp.assemble_competitors import (
    assemble_competitors,
    get_page_fields,
    load_page_data,
)

FIXTURES_DIR = (
    Path(__file__).parent.parent.parent
    / "test" / "fixtures" / "assemble-briefing-data"
)
GOLDEN_DIR = Path(__file__).parent.parent / "golden"
INTEGRATION_FIXTURES = (
    Path(__file__).parent.parent.parent
    / "test" / "fixtures" / "integration"
)

FIXTURE_NAMES = [
    "2026-03-09_test-keyword",
]


# --- Golden file roundtrip tests ---


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_golden_parity(fixture_name: str) -> None:
    """Output must match golden JSON byte-identically for each fixture."""
    fixture_dir = FIXTURES_DIR / fixture_name
    serp_path = fixture_dir / "serp-processed.json"
    pages_dir = fixture_dir / "pages"  # May not exist
    golden_path = GOLDEN_DIR / f"assemble-competitors--{fixture_name}.json"

    if not serp_path.exists():
        pytest.skip(f"Fixture {fixture_name} not found")

    serp = json.loads(serp_path.read_text(encoding="utf-8"))
    expected = golden_path.read_text(encoding="utf-8")

    # Extract date from fixture name (e.g., "2026-03-09_test-keyword" -> "2026-03-09")
    date = fixture_name.split("_")[0]
    result = assemble_competitors(serp, str(pages_dir), date=date)
    actual = json.dumps(result, indent=2, ensure_ascii=False)

    assert actual == expected, (
        f"Output differs from golden file for {fixture_name}"
    )


# --- CLI tests ---


class TestCli:
    """Command-line interface tests."""

    def test_cli_basic(self) -> None:
        """CLI produces valid JSON output."""
        serp_path = FIXTURES_DIR / "2026-03-09_test-keyword" / "serp-processed.json"
        pages_dir = FIXTURES_DIR / "2026-03-09_test-keyword" / "pages"

        if not serp_path.exists():
            pytest.skip("Fixture not found")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "seo_pipeline.serp.assemble_competitors",
                str(serp_path),
                str(pages_dir),
                "--date", "2026-03-09",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        output = json.loads(result.stdout)
        assert output["target_keyword"] == "test keyword"
        assert output["date"] == "2026-03-09"
        assert len(output["competitors"]) == 3

    def test_cli_with_output_file(self) -> None:
        """CLI can write to output file."""
        serp_path = FIXTURES_DIR / "2026-03-09_test-keyword" / "serp-processed.json"
        pages_dir = FIXTURES_DIR / "2026-03-09_test-keyword" / "pages"

        if not serp_path.exists():
            pytest.skip("Fixture not found")

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "seo_pipeline.serp.assemble_competitors",
                    str(serp_path),
                    str(pages_dir),
                    "--date", "2026-03-09",
                    "--output", str(output_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            assert result.stdout == ""
            assert output_path.exists()

            output = json.loads(output_path.read_text(encoding="utf-8"))
            assert output["target_keyword"] == "test keyword"

    def test_cli_missing_serp_file(self) -> None:
        """CLI exits with error if SERP file not found."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "seo_pipeline.serp.assemble_competitors",
                "/nonexistent/path.json",
                "/nonexistent/pages/",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "Error reading" in result.stderr or "Usage:" in result.stderr

    def test_cli_missing_arguments(self) -> None:
        """CLI exits with error if required arguments missing."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "seo_pipeline.serp.assemble_competitors",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "usage:" in result.stderr.lower()


# --- Unit tests for get_page_fields ---


class TestGetPageFields:
    """Unit tests for the get_page_fields function."""

    def test_none_input(self) -> None:
        """None input returns all null fields."""
        result = get_page_fields(None)
        assert result == {
            "word_count": None,
            "h1": None,
            "headings": None,
            "link_count": None,
            "meta_description": None,
        }

    def test_error_page_data(self) -> None:
        """Page with error flag returns all null fields."""
        page_data = {"error": "404"}
        result = get_page_fields(page_data)
        assert result == {
            "word_count": None,
            "h1": None,
            "headings": None,
            "link_count": None,
            "meta_description": None,
        }

    def test_partial_page_data(self) -> None:
        """Missing fields default to None."""
        page_data = {"word_count": 1000}
        result = get_page_fields(page_data)
        assert result["word_count"] == 1000
        assert result["h1"] is None
        assert result["headings"] is None
        assert result["link_count"] is None
        assert result["meta_description"] is None

    def test_full_page_data(self) -> None:
        """All fields extracted correctly."""
        page_data = {
            "word_count": 2500,
            "h1": "Main Heading",
            "headings": [
                {"level": 2, "text": "Section"},
                {"level": 3, "text": "Subsection"},
            ],
            "link_count": {"internal": 15, "external": 5},
            "meta_description": "Page description",
        }
        result = get_page_fields(page_data)
        assert result["word_count"] == 2500
        assert result["h1"] == "Main Heading"
        assert len(result["headings"]) == 2
        assert result["link_count"]["internal"] == 15
        assert result["meta_description"] == "Page description"


# --- Unit tests for load_page_data ---


class TestLoadPageData:
    """Unit tests for the load_page_data function."""

    def test_nonexistent_directory(self) -> None:
        """Nonexistent directory returns empty dict."""
        result = load_page_data("/nonexistent/path")
        assert result == {}

    def test_empty_directory(self) -> None:
        """Empty directory returns empty dict."""
        with TemporaryDirectory() as tmpdir:
            result = load_page_data(tmpdir)
            assert result == {}

    def test_loads_json_files(self) -> None:
        """JSON files are loaded and keyed by filename without extension."""
        with TemporaryDirectory() as tmpdir:
            # Create test files
            page1 = Path(tmpdir) / "example.com.json"
            page1.write_text(json.dumps({"word_count": 1000}))

            page2 = Path(tmpdir) / "test.de.json"
            page2.write_text(json.dumps({"word_count": 2000}))

            result = load_page_data(tmpdir)
            assert "example.com" in result
            assert "test.de" in result
            assert result["example.com"]["word_count"] == 1000
            assert result["test.de"]["word_count"] == 2000

    def test_skips_non_json_files(self) -> None:
        """Non-JSON files are ignored."""
        with TemporaryDirectory() as tmpdir:
            Path(tmpdir).joinpath("readme.txt").write_text("ignore me")
            Path(tmpdir).joinpath("example.com.json").write_text(
                json.dumps({"word_count": 1000})
            )

            result = load_page_data(tmpdir)
            assert len(result) == 1
            assert "example.com" in result

    def test_skips_malformed_json(self) -> None:
        """Malformed JSON files are skipped."""
        with TemporaryDirectory() as tmpdir:
            Path(tmpdir).joinpath("good.json").write_text(
                json.dumps({"word_count": 1000})
            )
            Path(tmpdir).joinpath("bad.json").write_text("not valid json")

            result = load_page_data(tmpdir)
            assert len(result) == 1
            assert "good" in result
            assert "bad" not in result


# --- Unit tests for assemble_competitors ---


class TestAssembleCompetitors:
    """Unit tests for the assemble_competitors function."""

    def test_basic_merge(self) -> None:
        """Competitors are merged with page data and qualitative nulls."""
        serp = {
            "target_keyword": "test",
            "se_results_count": 1000,
            "location_code": 2276,
            "language_code": "en",
            "item_types_present": ["organic"],
            "serp_features": {},
            "competitors": [
                {
                    "rank": 1,
                    "rank_absolute": 1,
                    "url": "https://example.com",
                    "domain": "example.com",
                    "title": "Example",
                    "description": "Desc",
                    "is_featured_snippet": False,
                    "is_video": False,
                    "has_rating": False,
                    "rating": None,
                    "timestamp": None,
                    "cited_in_ai_overview": False,
                }
            ],
        }

        result = assemble_competitors(serp, "/nonexistent/pages", date="2026-03-09")

        assert result["target_keyword"] == "test"
        assert result["date"] == "2026-03-09"
        assert len(result["competitors"]) == 1

        comp = result["competitors"][0]
        assert comp["rank"] == 1
        assert comp["domain"] == "example.com"
        # Page fields should be null (no pages dir)
        assert comp["word_count"] is None
        assert comp["h1"] is None
        # Qualitative fields should be null
        assert comp["format"] is None
        assert comp["topics"] is None
        assert comp["unique_angle"] is None
        assert comp["strengths"] is None
        assert comp["weaknesses"] is None

    def test_top_level_qualitative_nulls(self) -> None:
        """Top-level qualitative fields are null."""
        serp = {
            "target_keyword": "test",
            "se_results_count": 1000,
            "location_code": 2276,
            "language_code": "en",
            "item_types_present": [],
            "serp_features": {},
            "competitors": [],
        }

        result = assemble_competitors(serp, "/nonexistent/pages", date="2026-01-01")

        assert result["common_themes"] is None
        assert result["content_gaps"] is None
        assert result["opportunities"] is None

    def test_page_field_merging(self) -> None:
        """Page fields are correctly merged from page data."""
        serp = {
            "target_keyword": "test",
            "se_results_count": 1000,
            "location_code": 2276,
            "language_code": "en",
            "item_types_present": [],
            "serp_features": {},
            "competitors": [
                {
                    "rank": 1,
                    "rank_absolute": 1,
                    "url": "https://example.com",
                    "domain": "example.com",
                    "title": "Example",
                    "description": "Desc",
                    "is_featured_snippet": False,
                    "is_video": False,
                    "has_rating": False,
                    "rating": None,
                    "timestamp": None,
                    "cited_in_ai_overview": False,
                }
            ],
        }

        with TemporaryDirectory() as tmpdir:
            # Create page file
            page_file = Path(tmpdir) / "example.com.json"
            page_file.write_text(
                json.dumps({
                    "word_count": 2000,
                    "h1": "Main Title",
                    "headings": [{"level": 2, "text": "Section"}],
                    "link_count": {"internal": 10, "external": 5},
                    "meta_description": "SEO description",
                })
            )

            result = assemble_competitors(serp, tmpdir, date="2026-01-01")
            comp = result["competitors"][0]

            assert comp["word_count"] == 2000
            assert comp["h1"] == "Main Title"
            assert comp["headings"][0]["text"] == "Section"
            assert comp["link_count"]["internal"] == 10
            assert comp["meta_description"] == "SEO description"

    def test_default_date_is_today(self) -> None:
        """Default date is today if not provided."""
        serp = {
            "target_keyword": "test",
            "se_results_count": 1000,
            "location_code": 2276,
            "language_code": "en",
            "item_types_present": [],
            "serp_features": {},
            "competitors": [],
        }

        result = assemble_competitors(serp, "/nonexistent/pages")
        # Check that date is in YYYY-MM-DD format
        assert len(result["date"]) == 10
        assert result["date"].count("-") == 2

    def test_multiple_competitors(self) -> None:
        """Multiple competitors are all processed."""
        serp = {
            "target_keyword": "test",
            "se_results_count": 1000,
            "location_code": 2276,
            "language_code": "en",
            "item_types_present": [],
            "serp_features": {},
            "competitors": [
                {
                    "rank": i + 1,
                    "rank_absolute": i + 1,
                    "url": f"https://site{i}.com",
                    "domain": f"site{i}.com",
                    "title": f"Site {i}",
                    "description": f"Description {i}",
                    "is_featured_snippet": False,
                    "is_video": False,
                    "has_rating": False,
                    "rating": None,
                    "timestamp": None,
                    "cited_in_ai_overview": False,
                }
                for i in range(5)
            ],
        }

        result = assemble_competitors(serp, "/nonexistent/pages", date="2026-01-01")
        assert len(result["competitors"]) == 5
        for i, comp in enumerate(result["competitors"]):
            assert comp["rank"] == i + 1
            assert comp["domain"] == f"site{i}.com"

    def test_preserves_serp_structure(self) -> None:
        """SERP features and structure are preserved."""
        serp = {
            "target_keyword": "test keyword",
            "se_results_count": 1500000,
            "location_code": 2276,
            "language_code": "de",
            "item_types_present": ["organic", "people_also_ask"],
            "serp_features": {
                "ai_overview": {
                    "present": True,
                    "title": "AI Overview",
                },
            },
            "competitors": [],
        }

        result = assemble_competitors(serp, "/nonexistent/pages", date="2026-01-01")
        assert result["target_keyword"] == "test keyword"
        assert result["se_results_count"] == 1500000
        assert result["location_code"] == 2276
        assert result["language_code"] == "de"
        assert "people_also_ask" in result["item_types_present"]
        assert result["serp_features"]["ai_overview"]["present"] is True
