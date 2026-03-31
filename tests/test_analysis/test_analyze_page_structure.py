"""Tests for analyze_page_structure module."""

import json
from pathlib import Path

import pytest

from seo_pipeline.analysis.analyze_page_structure import (
    _block_reason,
    _compute_depth_score,
    _count_sentences,
    _count_words,
    _detect_modules,
    _has_lists,
    _has_numbers,
    _normalize_tree,
    _split_sections,
    analyze_page_structure,
    main,
)

FIXTURES = Path("test/fixtures/analyze-page-structure")
GOLDEN = Path("tests/golden")


# ---------------------------------------------------------------------------
# count_words
# ---------------------------------------------------------------------------


class TestCountWords:
    """Tests for _count_words helper."""

    def test_basic(self):
        assert _count_words("one two three") == 3

    def test_empty(self):
        assert _count_words("") == 0

    def test_whitespace_only(self):
        assert _count_words("   ") == 0

    def test_multiple_spaces(self):
        assert _count_words("one   two   three") == 3


# ---------------------------------------------------------------------------
# count_sentences
# ---------------------------------------------------------------------------


class TestCountSentences:
    """Tests for _count_sentences helper."""

    def test_basic(self):
        assert _count_sentences("One. Two. Three.") == 3

    def test_question_marks(self):
        assert _count_sentences("What? Why? How?") == 3

    def test_exclamation(self):
        assert _count_sentences("Wow! Great!") == 2

    def test_mixed_punctuation(self):
        assert _count_sentences("Hello. What? Wow!") == 3

    def test_empty(self):
        assert _count_sentences("") == 0

    def test_no_punctuation(self):
        # No sentence-ending punctuation: text is one sentence
        assert _count_sentences("Just some words without ending") == 1

    def test_consecutive_punctuation(self):
        # "Hello..." splits on [.?!]+ -> "Hello" + rest
        assert _count_sentences("Hello... World.") == 2


# ---------------------------------------------------------------------------
# has_numbers
# ---------------------------------------------------------------------------


class TestHasNumbers:
    """Tests for _has_numbers helper."""

    def test_with_digits(self):
        assert _has_numbers("There are 5 items") is True

    def test_without_digits(self):
        assert _has_numbers("No numbers here") is False

    def test_empty(self):
        assert _has_numbers("") is False


# ---------------------------------------------------------------------------
# has_lists
# ---------------------------------------------------------------------------


class TestHasLists:
    """Tests for _has_lists helper."""

    def test_ordered_lists(self):
        assert _has_lists({"ordered_lists": 1, "unordered_lists": 0}) is True

    def test_unordered_lists(self):
        assert _has_lists({"ordered_lists": 0, "unordered_lists": 2}) is True

    def test_both(self):
        assert _has_lists({"ordered_lists": 1, "unordered_lists": 1}) is True

    def test_none(self):
        assert _has_lists({"ordered_lists": 0, "unordered_lists": 0}) is False

    def test_missing_keys(self):
        assert _has_lists({}) is False


# ---------------------------------------------------------------------------
# compute_depth_score
# ---------------------------------------------------------------------------


class TestComputeDepthScore:
    """Tests for _compute_depth_score."""

    def test_zero_sentences(self):
        assert _compute_depth_score(0) == "shallow"

    def test_two_sentences(self):
        assert _compute_depth_score(2) == "shallow"

    def test_three_sentences(self):
        assert _compute_depth_score(3) == "basic"

    def test_six_sentences(self):
        assert _compute_depth_score(6) == "basic"

    def test_seven_sentences(self):
        assert _compute_depth_score(7) == "detailed"


# ---------------------------------------------------------------------------
# block_reason
# ---------------------------------------------------------------------------


class TestBlockReason:
    """Tests for _block_reason filter."""

    def test_empty_text(self):
        assert _block_reason("", []) == "missing main_content_text"

    def test_too_few_words(self):
        text = " ".join(["word"] * 100)
        result = _block_reason(text, [])
        assert result == "too few words (100 < 200)"

    def test_exactly_200_words_passes(self):
        text = " ".join(["word"] * 200)
        assert _block_reason(text, []) is None

    def test_block_heading(self):
        text = " ".join(["word"] * 300)
        result = _block_reason(text, ["Why have I been blocked?"])
        assert result is not None
        assert "block/error heading" in result

    def test_access_denied_heading(self):
        text = " ".join(["word"] * 300)
        result = _block_reason(text, ["Access Denied"])
        assert "block/error heading" in result

    def test_normal_page_passes(self):
        text = " ".join(["word"] * 300)
        assert _block_reason(text, ["Normal Heading"]) is None


# ---------------------------------------------------------------------------
# detect_modules
# ---------------------------------------------------------------------------


class TestDetectModules:
    """Tests for _detect_modules."""

    def test_faq_by_heading(self):
        signals = {"faq_sections": 0}
        modules = _detect_modules(signals, ["FAQ Section"])
        assert "faq" in modules

    def test_faq_by_signal(self):
        signals = {"faq_sections": 2}
        modules = _detect_modules(signals, [])
        assert "faq" in modules

    def test_faq_haeufig_heading(self):
        signals = {"faq_sections": 0}
        modules = _detect_modules(signals, ["Haeufig gestellte Fragen"])
        assert "faq" in modules

    def test_table(self):
        signals = {"tables": 1}
        modules = _detect_modules(signals, [])
        assert "table" in modules

    def test_list_ordered(self):
        signals = {"ordered_lists": 1}
        modules = _detect_modules(signals, [])
        assert "list" in modules

    def test_list_unordered(self):
        signals = {"unordered_lists": 1}
        modules = _detect_modules(signals, [])
        assert "list" in modules

    def test_video(self):
        signals = {"video_embeds": 1}
        modules = _detect_modules(signals, [])
        assert "video" in modules

    def test_image_gallery_above_threshold(self):
        signals = {"images_in_content": 4}
        modules = _detect_modules(signals, [])
        assert "image_gallery" in modules

    def test_image_gallery_at_threshold(self):
        # images_in_content > 3 means 4+ triggers it, 3 does not
        signals = {"images_in_content": 3}
        modules = _detect_modules(signals, [])
        assert "image_gallery" not in modules

    def test_form(self):
        signals = {"forms": 1}
        modules = _detect_modules(signals, [])
        assert "form" in modules

    def test_sorted_alphabetically(self):
        signals = {
            "faq_sections": 1,
            "tables": 1,
            "ordered_lists": 1,
            "video_embeds": 1,
            "images_in_content": 5,
            "forms": 1,
        }
        modules = _detect_modules(signals, [])
        assert modules == sorted(modules)

    def test_empty_signals(self):
        assert _detect_modules({}, []) == []

    def test_alpha_fixture(self):
        signals = {
            "faq_sections": 2,
            "tables": 1,
            "ordered_lists": 0,
            "unordered_lists": 2,
            "video_embeds": 0,
            "forms": 0,
            "images_in_content": 5,
        }
        headings = [
            "Strände und Buchten",
            "Haeufig gestellte Fragen",
            "Wie komme ich nach Mallorca?",
            "Wann ist die beste Reisezeit?",
            "Aktivitaeten und Sport",
        ]
        modules = _detect_modules(signals, headings)
        assert modules == ["faq", "image_gallery", "list", "table"]


# ---------------------------------------------------------------------------
# split_sections
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

    def test_heading_not_found(self):
        result = _split_sections("Some text here", [{"text": "Not Found", "level": 2}])
        # Heading not found -> no positions -> empty sections list
        assert len(result) == 0

    def test_no_intro_if_heading_at_start(self):
        text = "Heading Body text here"
        headings = [{"text": "Heading", "level": 2}]
        result = _split_sections(text, headings)
        assert len(result) == 1
        assert result[0]["heading"] == "Heading"


# ---------------------------------------------------------------------------
# normalize_tree
# ---------------------------------------------------------------------------


class TestNormalizeTree:
    """Tests for _normalize_tree helper."""

    def test_float_to_int(self):
        assert _normalize_tree(1.0) == 1
        assert isinstance(_normalize_tree(1.0), int)

    def test_fractional_float_preserved(self):
        assert _normalize_tree(1.5) == 1.5

    def test_nested_dict(self):
        result = _normalize_tree({"a": 1.0, "b": {"c": 2.0}})
        assert result == {"a": 1, "b": {"c": 2}}
        assert isinstance(result["a"], int)

    def test_list(self):
        result = _normalize_tree([1.0, 2.5])
        assert result == [1, 2.5]

    def test_string_passthrough(self):
        assert _normalize_tree("hello") == "hello"


# ---------------------------------------------------------------------------
# Golden file test
# ---------------------------------------------------------------------------


class TestGoldenOutput:
    """Test byte-identical output against golden file."""

    def test_golden_default(self):
        golden_path = GOLDEN / "analyze-page-structure--default.json"
        if not golden_path.exists():
            pytest.skip("Golden file not found")

        result = analyze_page_structure(FIXTURES / "pages")
        output_dict = _normalize_tree(result.model_dump())
        output_json = json.dumps(output_dict, indent=2, ensure_ascii=False)

        expected = golden_path.read_text(encoding="utf-8")
        assert output_json == expected


# ---------------------------------------------------------------------------
# Integration: fixture competitors
# ---------------------------------------------------------------------------


class TestFixtureCompetitors:
    """Test output structure for fixture pages."""

    def test_competitor_count(self):
        result = analyze_page_structure(FIXTURES / "pages")
        # page-blocked should be skipped, leaving 3 competitors
        assert len(result.competitors) == 3

    def test_blocked_page_excluded(self):
        result = analyze_page_structure(FIXTURES / "pages")
        domains = [c.domain for c in result.competitors]
        assert "blocked.example.com" not in domains

    def test_alpha_modules(self):
        result = analyze_page_structure(FIXTURES / "pages")
        alpha = next(c for c in result.competitors if c.domain == "alpha.example.com")
        assert alpha.detected_modules == ["faq", "image_gallery", "list", "table"]

    def test_beta_modules(self):
        result = analyze_page_structure(FIXTURES / "pages")
        beta = next(c for c in result.competitors if c.domain == "beta.example.com")
        assert beta.detected_modules == ["faq", "list", "table", "video"]

    def test_gamma_modules(self):
        result = analyze_page_structure(FIXTURES / "pages")
        gamma = next(c for c in result.competitors if c.domain == "gamma.example.com")
        assert gamma.detected_modules == ["form", "list"]

    def test_alpha_section_count(self):
        result = analyze_page_structure(FIXTURES / "pages")
        alpha = next(c for c in result.competitors if c.domain == "alpha.example.com")
        assert alpha.section_count == 6

    def test_beta_section_count(self):
        result = analyze_page_structure(FIXTURES / "pages")
        beta = next(c for c in result.competitors if c.domain == "beta.example.com")
        assert beta.section_count == 5

    def test_gamma_section_count(self):
        result = analyze_page_structure(FIXTURES / "pages")
        gamma = next(c for c in result.competitors if c.domain == "gamma.example.com")
        assert gamma.section_count == 3

    def test_alpha_word_count(self):
        result = analyze_page_structure(FIXTURES / "pages")
        alpha = next(c for c in result.competitors if c.domain == "alpha.example.com")
        assert alpha.total_word_count == 201

    def test_section_depth_scores(self):
        result = analyze_page_structure(FIXTURES / "pages")
        alpha = next(c for c in result.competitors if c.domain == "alpha.example.com")
        scores = [s.depth_score for s in alpha.sections]
        expected = [
            "basic", "detailed", "shallow", "shallow", "shallow", "detailed",
        ]
        assert scores == expected


# ---------------------------------------------------------------------------
# Integration: cross-competitor analysis
# ---------------------------------------------------------------------------


class TestCrossCompetitor:
    """Tests for cross-competitor analysis."""

    def test_common_modules(self):
        result = analyze_page_structure(FIXTURES / "pages")
        assert result.cross_competitor.common_modules == ["list"]

    def test_rare_modules(self):
        result = analyze_page_structure(FIXTURES / "pages")
        # With 3 competitors, rare threshold = 0.6, no module has count <= 0.6
        assert result.cross_competitor.rare_modules == []

    def test_module_frequency(self):
        result = analyze_page_structure(FIXTURES / "pages")
        freq = result.cross_competitor.module_frequency
        assert freq == {
            "faq": 2,
            "form": 1,
            "image_gallery": 1,
            "list": 3,
            "table": 2,
            "video": 1,
        }

    def test_module_frequency_sorted(self):
        result = analyze_page_structure(FIXTURES / "pages")
        keys = list(result.cross_competitor.module_frequency.keys())
        assert keys == sorted(keys)

    def test_avg_word_count(self):
        result = analyze_page_structure(FIXTURES / "pages")
        assert result.cross_competitor.avg_word_count == 201

    def test_avg_sections(self):
        result = analyze_page_structure(FIXTURES / "pages")
        assert result.cross_competitor.avg_sections == 5


# ---------------------------------------------------------------------------
# Integration: empty directory
# ---------------------------------------------------------------------------


class TestEmptyDirectory:
    """Test behavior with no page files."""

    def test_empty_dir(self, tmp_path):
        result = analyze_page_structure(tmp_path)
        assert result.competitors == []
        assert result.cross_competitor.common_modules == []
        assert result.cross_competitor.rare_modules == []
        assert result.cross_competitor.module_frequency == {}
        assert result.cross_competitor.avg_word_count == 0
        assert result.cross_competitor.avg_sections == 0


# ---------------------------------------------------------------------------
# Integration: all pages blocked
# ---------------------------------------------------------------------------


class TestAllPagesBlocked:
    """Test behavior when all pages are blocked/thin."""

    def test_all_blocked(self, tmp_path):
        page = {
            "url": "https://example.com/thin",
            "main_content_text": "Only a few words here",
            "headings": [],
            "html_signals": {},
        }
        (tmp_path / "thin.json").write_text(json.dumps(page), encoding="utf-8")
        result = analyze_page_structure(tmp_path)
        assert result.competitors == []
        assert result.cross_competitor.avg_word_count == 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    """Tests for CLI entry point."""

    def test_cli_output_file(self, tmp_path):
        output = tmp_path / "output.json"
        main([
            "--pages-dir", str(FIXTURES / "pages"),
            "--output", str(output),
        ])
        assert output.exists()
        data = json.loads(output.read_text(encoding="utf-8"))
        assert "competitors" in data
        assert "cross_competitor" in data

    def test_cli_golden_match(self, tmp_path):
        golden_path = GOLDEN / "analyze-page-structure--default.json"
        if not golden_path.exists():
            pytest.skip("Golden file not found")

        output = tmp_path / "output.json"
        main([
            "--pages-dir", str(FIXTURES / "pages"),
            "--output", str(output),
        ])

        expected = golden_path.read_text(encoding="utf-8")
        actual = output.read_text(encoding="utf-8")
        assert actual == expected
