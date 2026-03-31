"""Tests for analyze_content_topics module."""

import json
from pathlib import Path

import pytest

from seo_pipeline.analysis.analyze_content_topics import (
    _count_words,
    _count_words_raw,
    _extract_ngrams,
    _extract_page_terms,
    _idf_boost,
    _is_all_stopwords,
    _is_blocked_page,
    _jaccard_similarity,
    _normalize_heading,
    _normalize_tree,
    _split_sections,
    analyze_content_topics,
    main,
)

FIXTURES = Path("test/fixtures/analyze-content-topics")
GOLDEN = Path("tests/golden")


# ---------------------------------------------------------------------------
# IDF boost
# ---------------------------------------------------------------------------


class TestIdfBoost:
    """Tests for _idf_boost helper."""

    def test_none_table_returns_neutral(self):
        assert _idf_boost("anything", None) == 1.0

    def test_missing_term_returns_neutral(self):
        assert _idf_boost("nonexistent", {"other": 12.0}) == 1.0

    def test_exact_midpoint(self):
        # val=10.0, IDF_MIDPOINT=10.0 -> 10/10*1000 = 1000 -> 1.0
        assert _idf_boost("exact", {"exact": 10.0}) == 1.0

    def test_high_idf_gives_boost(self):
        # val=16.124, 16.124/10.0 = 1.6124, round(1.6124*1000)/1000 = 1.612
        assert _idf_boost("playa", {"playa": 16.124}) == 1.612

    def test_low_idf_gives_penalty(self):
        # val=7.28, 7.28/10.0 = 0.728, round(0.728*1000)/1000 = 0.728
        assert _idf_boost("de", {"de": 7.28}) == 0.728


# ---------------------------------------------------------------------------
# Page quality filter
# ---------------------------------------------------------------------------


class TestIsBlockedPage:
    """Tests for _is_blocked_page filter."""

    def test_empty_text_blocked(self):
        assert _is_blocked_page("", []) == "missing main_content_text"

    def test_too_few_words(self):
        text = " ".join(["word"] * 100)
        result = _is_blocked_page(text, [])
        assert result == "too few words (100 < 200)"

    def test_exactly_200_words_passes(self):
        text = " ".join(["word"] * 200)
        assert _is_blocked_page(text, []) is None

    def test_block_heading_detected(self):
        text = " ".join(["word"] * 300)
        headings = [{"text": "Why have I been blocked?", "level": 2}]
        result = _is_blocked_page(text, headings)
        assert result is not None
        assert "block/error heading" in result

    def test_access_denied_heading(self):
        text = " ".join(["word"] * 300)
        headings = [{"text": "Access Denied", "level": 1}]
        result = _is_blocked_page(text, headings)
        assert "block/error heading" in result

    def test_normal_page_passes(self):
        text = " ".join(["word"] * 300)
        headings = [{"text": "Normal Heading", "level": 2}]
        assert _is_blocked_page(text, headings) is None


# ---------------------------------------------------------------------------
# N-gram extraction
# ---------------------------------------------------------------------------


class TestExtractNgrams:
    """Tests for _extract_ngrams."""

    def test_unigrams(self):
        assert _extract_ngrams(["a", "b", "c"], 1) == ["a", "b", "c"]

    def test_bigrams(self):
        assert _extract_ngrams(["a", "b", "c"], 2) == ["a b", "b c"]

    def test_trigrams(self):
        assert _extract_ngrams(["a", "b", "c", "d"], 3) == ["a b c", "b c d"]

    def test_empty_tokens(self):
        assert _extract_ngrams([], 1) == []

    def test_too_few_tokens_for_n(self):
        assert _extract_ngrams(["a"], 2) == []


class TestIsAllStopwords:
    """Tests for _is_all_stopwords."""

    def test_all_stopwords(self):
        stopwords = {"the", "a", "is"}
        assert _is_all_stopwords("the a is", stopwords) is True

    def test_mixed(self):
        stopwords = {"the", "a"}
        assert _is_all_stopwords("the house", stopwords) is False

    def test_no_stopwords(self):
        stopwords = {"the", "a"}
        assert _is_all_stopwords("house car", stopwords) is False


class TestExtractPageTerms:
    """Tests for _extract_page_terms."""

    def test_basic_extraction(self):
        stopwords = {"the", "is", "a"}
        counts = _extract_page_terms("The house is big and a car is red", stopwords)
        # Unigrams: "house", "big", "car", "red"
        # (stopwords removed, single-char filtered by tokenize)
        assert counts["house"] >= 1
        assert counts["car"] >= 1
        # "is" should not be in unigrams (stopword)
        # But bigrams from all_tokens may include it
        assert "the" not in counts  # single-char 'a' filtered by tokenize

    def test_empty_text(self):
        counts = _extract_page_terms("", set())
        assert len(counts) == 0


# ---------------------------------------------------------------------------
# Heading normalization and Jaccard similarity
# ---------------------------------------------------------------------------


class TestNormalizeHeading:
    """Tests for _normalize_heading."""

    def test_basic(self):
        assert _normalize_heading("Straende und Buchten") == "straende und buchten"

    def test_strips_numbers(self):
        assert _normalize_heading("Top 10 Straende") == "top straende"

    def test_strips_punctuation(self):
        assert _normalize_heading("Fragen & Antworten!") == "fragen antworten"

    def test_preserves_umlauts(self):
        result = _normalize_heading("Häufig gestellte Fragen")
        assert result == "häufig gestellte fragen"

    def test_collapses_whitespace(self):
        assert _normalize_heading("Foo   Bar") == "foo bar"


class TestJaccardSimilarity:
    """Tests for _jaccard_similarity."""

    def test_identical(self):
        assert _jaccard_similarity("foo bar", "foo bar") == 1.0

    def test_no_overlap(self):
        assert _jaccard_similarity("foo bar", "baz qux") == 0.0

    def test_partial_overlap(self):
        # {foo, bar} & {bar, baz} = {bar}, union = {foo, bar, baz}
        assert _jaccard_similarity("foo bar", "bar baz") == pytest.approx(1 / 3)

    def test_both_empty(self):
        assert _jaccard_similarity("", "") == 1.0

    def test_one_empty(self):
        assert _jaccard_similarity("foo", "") == 0.0


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------


class TestSplitSections:
    """Tests for _split_sections."""

    def test_no_headings(self):
        result = _split_sections("some text here", [])
        assert len(result) == 1
        assert result[0]["heading"] == ""
        assert result[0]["text"] == "some text here"

    def test_with_intro_and_sections(self):
        text = (
            "Intro text. Section One Body of section one."
            " Section Two Body of section two."
        )
        headings = [
            {"text": "Section One", "level": 2},
            {"text": "Section Two", "level": 2},
        ]
        result = _split_sections(text, headings)
        assert result[0]["heading"] == ""
        assert "Intro" in result[0]["text"]
        assert result[1]["heading"] == "Section One"
        assert result[2]["heading"] == "Section Two"

    def test_heading_not_found_in_text(self):
        text = "Some text here"
        headings = [{"text": "Not Found", "level": 2}]
        result = _split_sections(text, headings)
        # Heading not found, so no sections created from it
        assert len(result) == 0 or (len(result) == 1 and result[0]["heading"] == "")


# ---------------------------------------------------------------------------
# Count words
# ---------------------------------------------------------------------------


class TestCountWords:
    """Tests for _count_words and _count_words_raw."""

    def test_basic(self):
        assert _count_words("one two three") == 3

    def test_empty(self):
        assert _count_words("") == 0

    def test_whitespace_only(self):
        assert _count_words("   ") == 0

    def test_count_words_raw_matches(self):
        assert _count_words_raw("one two three") == 3


# ---------------------------------------------------------------------------
# Normalize tree
# ---------------------------------------------------------------------------


class TestNormalizeTree:
    """Tests for _normalize_tree helper."""

    def test_float_to_int(self):
        assert _normalize_tree(1.0) == 1
        assert isinstance(_normalize_tree(1.0), int)

    def test_fractional_float_preserved(self):
        assert _normalize_tree(1.5) == 1.5

    def test_nested_dict(self):
        result = _normalize_tree({"a": 1.0, "b": {"c": 2.0, "d": 2.5}})
        assert result == {"a": 1, "b": {"c": 2, "d": 2.5}}
        assert isinstance(result["a"], int)

    def test_list(self):
        result = _normalize_tree([1.0, 2.5, 3.0])
        assert result == [1, 2.5, 3]

    def test_string_passthrough(self):
        assert _normalize_tree("hello") == "hello"

    def test_none_passthrough(self):
        assert _normalize_tree(None) is None


# ---------------------------------------------------------------------------
# Golden file test
# ---------------------------------------------------------------------------


class TestGoldenOutput:
    """Test byte-identical output against golden file."""

    def test_golden_default(self):
        golden_path = GOLDEN / "analyze-content-topics--default.json"
        if not golden_path.exists():
            pytest.skip("Golden file not found")

        result = analyze_content_topics(
            pages_dir=FIXTURES / "pages",
            seed="mallorca",
            language="de",
        )
        output_dict = _normalize_tree(result.model_dump())
        output_json = json.dumps(output_dict, indent=2, ensure_ascii=False)

        expected = golden_path.read_text(encoding="utf-8")
        assert output_json == expected


# ---------------------------------------------------------------------------
# Integration: empty directory
# ---------------------------------------------------------------------------


class TestEmptyDirectory:
    """Test behavior with no page files."""

    def test_empty_dir(self, tmp_path):
        result = analyze_content_topics(tmp_path, "test", "de")
        assert result.proof_keywords == []
        assert result.entity_candidates == []
        assert result.section_weights == []
        assert result.content_format_signals.pages_with_numbered_lists == 0
        assert result.content_format_signals.avg_h2_count == 0
        assert result.content_format_signals.dominant_pattern is None


# ---------------------------------------------------------------------------
# Integration: blocked pages
# ---------------------------------------------------------------------------


class TestBlockedPages:
    """Test that blocked/thin pages are excluded."""

    def test_thin_page_excluded(self, tmp_path):
        page = {
            "url": "https://example.com/thin",
            "main_content_text": "Only a few words here",
            "headings": [],
            "html_signals": {},
        }
        (tmp_path / "thin.json").write_text(json.dumps(page), encoding="utf-8")
        result = analyze_content_topics(tmp_path, "test", "de")
        assert result.proof_keywords == []

    def test_blocked_heading_excluded(self, tmp_path):
        text = " ".join(["word"] * 300)
        page = {
            "url": "https://example.com/blocked",
            "main_content_text": text,
            "headings": [{"text": "Access Denied", "level": 1}],
            "html_signals": {},
        }
        (tmp_path / "blocked.json").write_text(json.dumps(page), encoding="utf-8")
        result = analyze_content_topics(tmp_path, "test", "de")
        assert result.proof_keywords == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    """Tests for CLI entry point."""

    def test_cli_output_file(self, tmp_path):
        output = tmp_path / "output.json"
        main([
            "--pages-dir", str(FIXTURES / "pages"),
            "--seed", "mallorca",
            "--output", str(output),
        ])
        assert output.exists()
        data = json.loads(output.read_text(encoding="utf-8"))
        assert "proof_keywords" in data
        assert "entity_candidates" in data
        assert "section_weights" in data
        assert "content_format_signals" in data

    def test_cli_golden_match(self, tmp_path):
        golden_path = GOLDEN / "analyze-content-topics--default.json"
        if not golden_path.exists():
            pytest.skip("Golden file not found")

        output = tmp_path / "output.json"
        main([
            "--pages-dir", str(FIXTURES / "pages"),
            "--seed", "mallorca",
            "--output", str(output),
        ])

        expected = golden_path.read_text(encoding="utf-8")
        actual = output.read_text(encoding="utf-8")
        assert actual == expected


# ---------------------------------------------------------------------------
# Proof keywords specific tests
# ---------------------------------------------------------------------------


class TestProofKeywords:
    """Tests for proof keyword extraction details."""

    def test_seed_excluded(self):
        result = analyze_content_topics(
            pages_dir=FIXTURES / "pages",
            seed="mallorca",
            language="de",
        )
        terms = [pk.term for pk in result.proof_keywords]
        assert "mallorca" not in terms

    def test_df_at_least_2(self):
        result = analyze_content_topics(
            pages_dir=FIXTURES / "pages",
            seed="mallorca",
            language="de",
        )
        for pk in result.proof_keywords:
            assert pk.document_frequency >= 2

    def test_max_50(self):
        result = analyze_content_topics(
            pages_dir=FIXTURES / "pages",
            seed="mallorca",
            language="de",
        )
        assert len(result.proof_keywords) <= 50

    def test_sorted_by_idf_score_desc(self):
        result = analyze_content_topics(
            pages_dir=FIXTURES / "pages",
            seed="mallorca",
            language="de",
        )
        scores = [pk.idf_score for pk in result.proof_keywords]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]


# ---------------------------------------------------------------------------
# Entity candidates specific tests
# ---------------------------------------------------------------------------


class TestEntityCandidates:
    """Tests for entity candidate extraction."""

    def test_single_word_only(self):
        result = analyze_content_topics(
            pages_dir=FIXTURES / "pages",
            seed="mallorca",
            language="de",
        )
        for ec in result.entity_candidates:
            assert " " not in ec.term

    def test_min_length_3(self):
        result = analyze_content_topics(
            pages_dir=FIXTURES / "pages",
            seed="mallorca",
            language="de",
        )
        for ec in result.entity_candidates:
            assert len(ec.term) >= 3

    def test_max_30(self):
        result = analyze_content_topics(
            pages_dir=FIXTURES / "pages",
            seed="mallorca",
            language="de",
        )
        assert len(result.entity_candidates) <= 30

    def test_pages_sorted(self):
        result = analyze_content_topics(
            pages_dir=FIXTURES / "pages",
            seed="mallorca",
            language="de",
        )
        for ec in result.entity_candidates:
            assert ec.pages == sorted(ec.pages)


# ---------------------------------------------------------------------------
# Section weights specific tests
# ---------------------------------------------------------------------------


class TestSectionWeights:
    """Tests for section weight analysis."""

    def test_weight_values(self):
        result = analyze_content_topics(
            pages_dir=FIXTURES / "pages",
            seed="mallorca",
            language="de",
        )
        for sw in result.section_weights:
            assert sw.weight in ("high", "medium", "low")

    def test_high_weight_threshold(self):
        result = analyze_content_topics(
            pages_dir=FIXTURES / "pages",
            seed="mallorca",
            language="de",
        )
        for sw in result.section_weights:
            if sw.avg_content_percentage > 25:
                assert sw.weight == "high"
            elif sw.avg_content_percentage >= 10:
                assert sw.weight == "medium"
            else:
                assert sw.weight == "low"


# ---------------------------------------------------------------------------
# Content format signals
# ---------------------------------------------------------------------------


class TestContentFormatSignals:
    """Tests for content format signals."""

    def test_fixture_values(self):
        result = analyze_content_topics(
            pages_dir=FIXTURES / "pages",
            seed="mallorca",
            language="de",
        )
        signals = result.content_format_signals
        assert signals.pages_with_numbered_lists == 1
        assert signals.pages_with_faq == 1
        assert signals.pages_with_tables == 2
        assert signals.dominant_pattern is None
