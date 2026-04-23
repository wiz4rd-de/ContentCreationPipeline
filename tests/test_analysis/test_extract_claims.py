"""Tests for extract_claims module."""

import json
from pathlib import Path

import pytest

from seo_pipeline.analysis.extract_claims import (
    _extract_section,
    _find_sentence,
    _find_skip_ranges,
    _is_editorial_marker,
    _is_in_skip_range,
    _split_sentences,
    extract_claims,
    main,
)

FIXTURE = Path("tests/fixtures/extract-claims/draft.md")


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------


class TestSplitSentences:
    """Tests for _split_sentences helper."""

    def test_simple_sentences(self):
        result = _split_sentences("Hello world. Goodbye world.")
        assert result == ["Hello world.", "Goodbye world."]

    def test_question_and_exclamation(self):
        result = _split_sentences("Is it done? Yes! Great.")
        assert result == ["Is it done?", "Yes!", "Great."]

    def test_german_number_not_split(self):
        """Dots in German numbers like 1.700 should not split."""
        result = _split_sentences("Es sind 1.700 Kilometer lang.")
        assert result == ["Es sind 1.700 Kilometer lang."]

    def test_multiple_german_numbers(self):
        result = _split_sentences(
            "Von 6.500 bis 8.000 Quadratkilometern. Zweiter Satz."
        )
        assert result == [
            "Von 6.500 bis 8.000 Quadratkilometern.",
            "Zweiter Satz.",
        ]

    def test_trailing_text_without_delimiter(self):
        result = _split_sentences("No ending period")
        assert result == ["No ending period"]

    def test_empty_string(self):
        assert _split_sentences("") == []


# ---------------------------------------------------------------------------
# Skip ranges (meta tables)
# ---------------------------------------------------------------------------


class TestFindSkipRanges:
    """Tests for _find_skip_ranges helper."""

    def test_finds_meta_table(self):
        lines = [
            "| Feld | Wert |",
            "|------|------|",
            "| Keyword | test |",
            "",
            "---",
            "",
            "Regular content",
        ]
        ranges = _find_skip_ranges(lines)
        assert ranges == [(0, 4)]

    def test_no_meta_table(self):
        lines = ["# Heading", "Regular content"]
        assert _find_skip_ranges(lines) == []

    def test_unclosed_meta_table(self):
        lines = ["| Feld | Wert |", "|------|------|", "| Key | Value |"]
        ranges = _find_skip_ranges(lines)
        assert ranges == [(0, 2)]

    def test_is_in_skip_range(self):
        ranges = [(0, 4)]
        assert _is_in_skip_range(0, ranges) is True
        assert _is_in_skip_range(4, ranges) is True
        assert _is_in_skip_range(5, ranges) is False


# ---------------------------------------------------------------------------
# Editorial markers
# ---------------------------------------------------------------------------


class TestIsEditorialMarker:
    """Tests for _is_editorial_marker helper."""

    def test_html_comment(self):
        assert _is_editorial_marker("<!-- TODO: fix -->") is True

    def test_blockquote_marker(self):
        assert _is_editorial_marker('> **[TODO]** Fix this') is True
        assert _is_editorial_marker('> **[VERIFY]** Check prices') is True

    def test_regular_line(self):
        assert _is_editorial_marker("Regular text here.") is False

    def test_regular_blockquote(self):
        assert _is_editorial_marker("> Regular quote") is False


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------


class TestExtractSection:
    """Tests for _extract_section helper."""

    def test_h2(self):
        assert _extract_section("## My Section") == "My Section"

    def test_h3(self):
        assert _extract_section("### Sub Section") == "Sub Section"

    def test_h1_not_matched(self):
        assert _extract_section("# Title") is None

    def test_no_heading(self):
        assert _extract_section("Regular text") is None


# ---------------------------------------------------------------------------
# Find sentence
# ---------------------------------------------------------------------------


class TestFindSentence:
    """Tests for _find_sentence helper."""

    def test_finds_correct_sentence(self):
        text = "First sentence. Second with 1.700 Meter. Third sentence."
        result = _find_sentence(text, "1.700 Meter", text.index("1.700 Meter"))
        assert result == "Second with 1.700 Meter."

    def test_fallback_to_full_line(self):
        # If no sentence boundary found, return trimmed text
        text = "No sentence boundary here"
        result = _find_sentence(text, "boundary", text.index("boundary"))
        assert result == "No sentence boundary here"


# ---------------------------------------------------------------------------
# Full extraction against fixture
# ---------------------------------------------------------------------------


class TestExtractClaims:
    """Tests for extract_claims function against the test fixture."""

    @pytest.fixture()
    def result(self):
        return extract_claims(FIXTURE)

    def test_total_claims(self, result):
        assert result.meta.total_claims == 24

    def test_claim_ids_sequential(self, result):
        expected_ids = [f"c{i:03d}" for i in range(1, 25)]
        actual_ids = [c.id for c in result.claims]
        assert actual_ids == expected_ids

    def test_meta_draft_path(self, result):
        assert result.meta.draft == str(FIXTURE)

    def test_meta_extracted_at_is_iso(self, result):
        assert result.meta.extracted_at.endswith("Z")

    def test_first_claim(self, result):
        c = result.claims[0]
        assert c.id == "c001"
        assert c.category == "counts"
        assert c.value == "ueber 1.700 Kilometer"
        assert c.line == 14
        assert c.section == "Wandern in Norwegen: Ein Ueberblick"

    def test_heights_distances_claim(self, result):
        c = result.claims[1]
        assert c.id == "c002"
        assert c.category == "heights_distances"
        assert c.value == "1.700 Kilometer"

    def test_dates_years_claim(self, result):
        c = result.claims[3]
        assert c.id == "c004"
        assert c.category == "dates_years"
        assert c.value == "Seit 2015"

    def test_prices_costs_claim(self, result):
        c = result.claims[6]
        assert c.id == "c007"
        assert c.category == "prices_costs"
        assert c.value == "790 NOK"

    def test_geographic_claim(self, result):
        c = result.claims[7]
        assert c.id == "c008"
        assert c.category == "geographic"
        assert c.value == "zwischen Lom und Gjendesheim"

    def test_measurements_claim(self, result):
        c = result.claims[13]
        assert c.id == "c014"
        assert c.category == "measurements"
        assert c.value == "6.500 bis 8.000 Quadratkilometern"

    def test_claim_sentence_contains_value(self, result):
        """Every claim's sentence should contain its value."""
        for c in result.claims:
            assert c.value in c.sentence, f"{c.id}: '{c.value}' not in '{c.sentence}'"

    def test_sections_assigned_correctly(self, result):
        sections = {c.id: c.section for c in result.claims}
        assert sections["c001"] == "Wandern in Norwegen: Ein Ueberblick"
        assert sections["c005"] == "Jotunheimen Nationalpark"
        assert sections["c009"] == "Besseggen-Grat"
        assert sections["c014"] == "Hardangervidda"

    def test_meta_table_lines_skipped(self, result):
        """No claims should come from lines 1-7 (meta table + separator)."""
        for c in result.claims:
            assert c.line > 7

    def test_editorial_markers_skipped(self, result):
        """No claims from lines 9-10 (editorial markers)."""
        for c in result.claims:
            assert c.line not in (9, 10)

    def test_categories_present(self, result):
        categories = {c.category for c in result.claims}
        assert categories == {
            "heights_distances",
            "prices_costs",
            "dates_years",
            "counts",
            "geographic",
            "measurements",
        }

    def test_all_claims_match_golden(self, result):
        """Verify every claim field matches the Node.js golden output."""
        golden = [
            ("c001", "counts", "ueber 1.700 Kilometer", 14),
            ("c002", "heights_distances", "1.700 Kilometer", 14),
            ("c003", "counts", "ueber 550 Huetten", 14),
            ("c004", "dates_years", "Seit 2015", 14),
            ("c005", "heights_distances", "2.469 Metern", 18),
            ("c006", "counts", "2.469 Metern", 18),
            ("c007", "prices_costs", "790 NOK", 18),
            ("c008", "geographic", "zwischen Lom und Gjendesheim", 18),
            ("c009", "heights_distances", "8 km", 22),
            ("c010", "heights_distances", "604 Meter", 22),
            ("c011", "counts", "604 Meter", 22),
            ("c012", "dates_years", "im Jahr 1868", 22),
            ("c013", "counts", "rund 500 Routen", 22),
            ("c014", "measurements", "6.500 bis 8.000 Quadratkilometern", 26),
            ("c015", "counts", "8.000 Quadratkilometern", 26),
            ("c016", "counts", "15 Grad", 26),
            ("c017", "measurements", "15 Grad Celsius", 26),
            ("c018", "prices_costs", "ab 49 Euro", 26),
            ("c019", "counts", "49 Euro", 26),
            ("c020", "dates_years", "Im Jahr 1884", 28),
            ("c021", "counts", "28 Nationalparks", 28),
            ("c022", "geographic", "noerdlich des Polarkreises", 28),
            ("c023", "counts", "24 Stunden", 28),
            ("c024", "prices_costs", "etwa 150 EUR", 28),
        ]
        for i, (exp_id, exp_cat, exp_val, exp_line) in enumerate(golden):
            c = result.claims[i]
            assert c.id == exp_id, f"index {i}: id"
            assert c.category == exp_cat, f"index {i}: category"
            assert c.value == exp_val, f"index {i}: value"
            assert c.line == exp_line, f"index {i}: line"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLI:
    """Tests for CLI entry point."""

    def test_cli_output_file(self, tmp_path):
        out = tmp_path / "claims.json"
        main(["--draft", str(FIXTURE), "--output", str(out)])
        data = json.loads(out.read_text())
        assert data["meta"]["total_claims"] == 24
        assert len(data["claims"]) == 24

    def test_cli_stdout(self, capsys):
        main(["--draft", str(FIXTURE)])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["meta"]["total_claims"] == 24

    def test_cli_missing_draft(self):
        with pytest.raises(SystemExit):
            main([])
