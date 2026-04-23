"""Tests for SERP processing module -- golden file parity and unit tests."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from seo_pipeline.serp.process_serp import (
    clean_aio_text,
    process_serp,
)

FIXTURES_DIR = (
    Path(__file__).parent.parent.parent
    / "tests" / "fixtures" / "process-serp"
)
GOLDEN_DIR = Path(__file__).parent.parent / "golden"

# All 5 fixture names (without extension)
FIXTURE_NAMES = [
    "serp-aio-encoding-artifacts",
    "serp-aio-no-text",
    "serp-no-aio-no-paa",
    "serp-paa-no-expanded",
    "serp-with-aio",
]


# --- Golden file roundtrip tests ---


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_golden_parity(fixture_name: str) -> None:
    """Output must match golden JSON byte-identically for each fixture."""
    fixture_path = FIXTURES_DIR / f"{fixture_name}.json"
    golden_path = GOLDEN_DIR / f"process-serp--{fixture_name}.json"

    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    expected = golden_path.read_text(encoding="utf-8")

    result = process_serp(raw)
    actual = json.dumps(result, indent=2, ensure_ascii=False)

    assert actual == expected, (
        f"Output differs from golden file for {fixture_name}"
    )


# --- clean_aio_text unit tests ---


class TestCleanAioText:
    """Unit tests for the clean_aio_text function."""

    def test_removes_zero_width_space(self) -> None:
        assert clean_aio_text("hello\u200bworld") == "helloworld"

    def test_removes_zwnj(self) -> None:
        assert clean_aio_text("hello\u200cworld") == "helloworld"

    def test_removes_zwj(self) -> None:
        assert clean_aio_text("hello\u200dworld") == "helloworld"

    def test_removes_bom(self) -> None:
        assert clean_aio_text("hello\ufeffworld") == "helloworld"

    def test_degree_celsius_normalization(self) -> None:
        # Ring operator with space
        assert clean_aio_text("23 \u2218 C today") == "23 °C today"

    def test_degree_fahrenheit_normalization(self) -> None:
        assert clean_aio_text("72 \u2218F today") == "72 °F today"

    def test_degree_sign_normalization(self) -> None:
        # Actual degree sign (U+00B0) also gets normalized
        assert clean_aio_text("23 \u00b0 C today") == "23 °C today"

    def test_html_entity_amp(self) -> None:
        assert clean_aio_text("A &amp; B") == "A & B"

    def test_html_entity_nbsp(self) -> None:
        assert clean_aio_text("A&nbsp;B") == "A B"

    def test_html_entity_lt_gt(self) -> None:
        assert clean_aio_text("&lt;div&gt;") == "<div>"

    def test_collapse_spaces(self) -> None:
        assert clean_aio_text("hello   world") == "hello world"

    def test_preserve_newlines(self) -> None:
        assert clean_aio_text("line1\nline2") == "line1\nline2"

    def test_trim_lines(self) -> None:
        assert clean_aio_text("  hello  \n  world  ") == "hello\nworld"

    def test_collapse_blank_lines(self) -> None:
        assert clean_aio_text("a\n\n\n\nb") == "a\n\nb"

    def test_empty_string(self) -> None:
        assert clean_aio_text("") == ""

    def test_combined_artifacts(self) -> None:
        """Test multiple artifacts in one string (encoding fixture)."""
        text = (
            "Morgen werden 18 \u2218 F erwartet."
            "\u200bEin weiterer\u200d schöner Tag."
        )
        expected = "Morgen werden 18 °F erwartet.Ein weiterer schöner Tag."
        assert clean_aio_text(text) == expected


# --- process_serp function tests ---


class TestProcessSerp:
    """Unit tests for the process_serp function."""

    def test_raises_on_missing_result(self) -> None:
        with pytest.raises(ValueError, match="No result found"):
            process_serp({})

    def test_raises_on_empty_tasks(self) -> None:
        with pytest.raises(ValueError, match="No result found"):
            process_serp({"tasks": []})

    def test_raises_on_empty_result(self) -> None:
        with pytest.raises(ValueError, match="No result found"):
            process_serp({"tasks": [{"result": []}]})

    def test_minimal_valid_input(self) -> None:
        raw = {"tasks": [{"result": [{"keyword": "test", "se_results_count": 0,
                "location_code": 1, "language_code": "en"}]}]}
        result = process_serp(raw)
        assert result["target_keyword"] == "test"
        assert result["competitors"] == []

    def test_top_n_limits_competitors(self) -> None:
        organic = [
            {"type": "organic", "rank_group": i, "rank_absolute": i,
             "url": f"https://example.com/{i}", "domain": "example.com",
             "title": f"Page {i}", "description": None,
             "is_featured_snippet": False, "is_video": False,
             "rating": None, "timestamp": None}
            for i in range(1, 6)
        ]
        raw = {"tasks": [{"result": [{"keyword": "test", "se_results_count": 5,
                "location_code": 1, "language_code": "en", "items": organic}]}]}
        result = process_serp(raw, top_n=3)
        assert len(result["competitors"]) == 3
        assert result["competitors"][2]["rank"] == 3

    def test_ai_overview_absent(self) -> None:
        raw = {"tasks": [{"result": [{"keyword": "q", "se_results_count": 0,
                "location_code": 1, "language_code": "en", "items": []}]}]}
        result = process_serp(raw)
        aio = result["serp_features"]["ai_overview"]
        assert aio["present"] is False
        assert aio["title"] is None
        assert aio["text"] is None
        assert aio["references"] == []
        assert aio["references_count"] == 0

    def test_ai_overview_field_order_absent(self) -> None:
        """Absent AIO field order: present, title, text, refs, count."""
        raw = {"tasks": [{"result": [{"keyword": "q", "se_results_count": 0,
                "location_code": 1, "language_code": "en", "items": []}]}]}
        result = process_serp(raw)
        keys = list(result["serp_features"]["ai_overview"].keys())
        assert keys == ["present", "title", "text", "references", "references_count"]

    def test_ai_overview_field_order_present(self) -> None:
        """Present AIO field order: present, refs, title, text, count."""
        fixture = json.loads(
            (FIXTURES_DIR / "serp-with-aio.json").read_text(encoding="utf-8")
        )
        result = process_serp(fixture)
        keys = list(result["serp_features"]["ai_overview"].keys())
        assert keys == ["present", "references", "title", "text", "references_count"]

    def test_featured_snippet_absent(self) -> None:
        raw = {"tasks": [{"result": [{"keyword": "q", "se_results_count": 0,
                "location_code": 1, "language_code": "en", "items": []}]}]}
        result = process_serp(raw)
        fs = result["serp_features"]["featured_snippet"]
        assert fs == {"present": False}

    def test_knowledge_graph_absent(self) -> None:
        raw = {"tasks": [{"result": [{"keyword": "q", "se_results_count": 0,
                "location_code": 1, "language_code": "en", "items": []}]}]}
        result = process_serp(raw)
        kg = result["serp_features"]["knowledge_graph"]
        assert kg == {"present": False}

    def test_commercial_signals_all_false(self) -> None:
        raw = {"tasks": [{"result": [{"keyword": "q", "se_results_count": 0,
                "location_code": 1, "language_code": "en", "items": []}]}]}
        result = process_serp(raw)
        cs = result["serp_features"]["commercial_signals"]
        assert cs == {
            "paid_ads_present": False,
            "shopping_present": False,
            "commercial_units_present": False,
            "popular_products_present": False,
        }

    def test_local_signals_all_false(self) -> None:
        raw = {"tasks": [{"result": [{"keyword": "q", "se_results_count": 0,
                "location_code": 1, "language_code": "en", "items": []}]}]}
        result = process_serp(raw)
        ls = result["serp_features"]["local_signals"]
        assert ls == {
            "local_pack_present": False,
            "map_present": False,
            "hotels_pack_present": False,
        }

    def test_other_features_sorted(self) -> None:
        items = [
            {"type": "twitter"},
            {"type": "images"},
            {"type": "organic"},  # dedicated, should be excluded
        ]
        raw = {"tasks": [{"result": [{"keyword": "q", "se_results_count": 0,
                "location_code": 1, "language_code": "en", "items": items}]}]}
        result = process_serp(raw)
        other = result["serp_features"]["other_features_present"]
        assert other == ["images", "twitter"]

    def test_competitor_cited_in_ai_overview(self) -> None:
        """Domains in AIO references get cited_in_ai_overview=True."""
        fixture = json.loads(
            (FIXTURES_DIR / "serp-with-aio.json").read_text(encoding="utf-8")
        )
        result = process_serp(fixture)
        assert result["competitors"][0]["cited_in_ai_overview"] is True
        assert result["competitors"][1]["cited_in_ai_overview"] is True

    def test_competitor_not_cited(self) -> None:
        """Competitors not in AIO get cited_in_ai_overview=False."""
        fixture = json.loads(
            (FIXTURES_DIR / "serp-no-aio-no-paa.json").read_text(encoding="utf-8")
        )
        result = process_serp(fixture)
        assert result["competitors"][0]["cited_in_ai_overview"] is False

    def test_paa_with_expanded(self) -> None:
        fixture = json.loads(
            (FIXTURES_DIR / "serp-with-aio.json").read_text(encoding="utf-8")
        )
        result = process_serp(fixture)
        paa = result["serp_features"]["people_also_ask"]
        assert len(paa) == 3
        assert paa[0]["answer"] is not None
        assert paa[2]["answer"] is None  # empty expanded_element

    def test_paa_no_expanded(self) -> None:
        fixture = json.loads(
            (FIXTURES_DIR / "serp-paa-no-expanded.json").read_text(encoding="utf-8")
        )
        result = process_serp(fixture)
        paa = result["serp_features"]["people_also_ask"]
        assert len(paa) == 2  # third item has title=null, should be skipped
        assert all(q["answer"] is None for q in paa)

    def test_competitor_rating_null(self) -> None:
        fixture = json.loads(
            (FIXTURES_DIR / "serp-with-aio.json").read_text(encoding="utf-8")
        )
        result = process_serp(fixture)
        comp = result["competitors"][0]
        assert comp["has_rating"] is False
        assert comp["rating"] is None


# --- CLI integration test ---


class TestCli:
    """Integration tests for the CLI entry point."""

    def test_cli_output_matches_golden(self, tmp_path: Path) -> None:
        fixture = FIXTURES_DIR / "serp-with-aio.json"
        golden = GOLDEN_DIR / "process-serp--serp-with-aio.json"
        output = tmp_path / "output.json"

        subprocess.run(
            [sys.executable, "-m", "seo_pipeline.serp.process_serp",
             str(fixture), "--output", str(output)],
            check=True,
        )

        assert output.read_text(encoding="utf-8") == golden.read_text(encoding="utf-8")

    def test_cli_stdout(self) -> None:
        fixture = FIXTURES_DIR / "serp-with-aio.json"
        golden = GOLDEN_DIR / "process-serp--serp-with-aio.json"

        result = subprocess.run(
            [sys.executable, "-m", "seo_pipeline.serp.process_serp", str(fixture)],
            capture_output=True,
            text=True,
            check=True,
        )

        # stdout includes a trailing newline from print()
        assert result.stdout.rstrip("\n") == golden.read_text(encoding="utf-8")

    def test_cli_no_file_exits_1(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "seo_pipeline.serp.process_serp"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_cli_top_flag(self, tmp_path: Path) -> None:
        fixture = FIXTURES_DIR / "serp-with-aio.json"
        output = tmp_path / "output.json"

        subprocess.run(
            [sys.executable, "-m", "seo_pipeline.serp.process_serp",
             str(fixture), "--top", "1", "--output", str(output)],
            check=True,
        )

        data = json.loads(output.read_text(encoding="utf-8"))
        assert len(data["competitors"]) == 1
