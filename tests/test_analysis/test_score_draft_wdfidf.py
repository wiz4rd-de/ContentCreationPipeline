"""Tests for score_draft_wdfidf module."""

import json
import math
from collections import Counter
from pathlib import Path

import pytest

from seo_pipeline.analysis.score_draft_wdfidf import (
    _compute_wdf,
    _extract_terms,
    _normalize_tree,
    _round6,
    main,
    score_draft_wdfidf,
)

FIXTURES = Path("test/fixtures/score-draft-wdfidf")
GOLDEN = Path("tests/golden")


# ---------------------------------------------------------------------------
# WDF formula
# ---------------------------------------------------------------------------


class TestComputeWdf:
    """Tests for _compute_wdf helper."""

    def test_zero_word_count(self):
        assert _compute_wdf(5, 0) == 0.0

    def test_one_word_count(self):
        assert _compute_wdf(5, 1) == 0.0

    def test_basic_wdf(self):
        # wdf(3, 100) = log2(4) / log2(100) = 2.0 / 6.643856...
        result = _compute_wdf(3, 100)
        expected = math.log2(4) / math.log2(100)
        assert result == pytest.approx(expected)

    def test_tf_zero(self):
        # wdf(0, 100) = log2(1) / log2(100) = 0
        assert _compute_wdf(0, 100) == 0.0

    def test_tf_one(self):
        # wdf(1, 10) = log2(2) / log2(10) = 1.0 / 3.321928...
        result = _compute_wdf(1, 10)
        expected = math.log2(2) / math.log2(10)
        assert result == pytest.approx(expected)


# ---------------------------------------------------------------------------
# round6
# ---------------------------------------------------------------------------


class TestRound6:
    """Tests for _round6 helper."""

    def test_basic_rounding(self):
        assert _round6(1.23456789) == 1.234568

    def test_zero(self):
        assert _round6(0.0) == 0.0

    def test_negative(self):
        assert _round6(-1.23456789) == -1.234568

    def test_already_precise(self):
        assert _round6(1.5) == 1.5

    def test_js_round_half_up(self):
        # JS Math.round rounds 0.5 up: round6(0.0000005) should round to 0.000001
        assert _round6(0.0000005) == 0.000001


# ---------------------------------------------------------------------------
# Term extraction
# ---------------------------------------------------------------------------


class TestExtractTerms:
    """Tests for _extract_terms helper."""

    def test_returns_counts_and_word_count(self):
        from seo_pipeline.utils.tokenizer import load_stopword_set

        stopwords = load_stopword_set("de")
        counts, word_count = _extract_terms("Wandern in den Bergen", stopwords)
        assert isinstance(counts, Counter)
        assert isinstance(word_count, int)
        # word_count is total tokens before stopword removal
        assert word_count == 4  # "wandern", "in", "den", "bergen"

    def test_empty_text(self):
        counts, word_count = _extract_terms("", set())
        assert len(counts) == 0
        assert word_count == 0


# ---------------------------------------------------------------------------
# normalize_tree
# ---------------------------------------------------------------------------


class TestNormalizeTree:
    """Tests for _normalize_tree helper."""

    def test_float_to_int(self):
        assert _normalize_tree(4.0) == 4
        assert isinstance(_normalize_tree(4.0), int)

    def test_float_stays_float(self):
        assert _normalize_tree(4.5) == 4.5
        assert isinstance(_normalize_tree(4.5), float)

    def test_nested_dict(self):
        result = _normalize_tree({"a": 1.0, "b": {"c": 2.5}})
        assert result == {"a": 1, "b": {"c": 2.5}}

    def test_list(self):
        result = _normalize_tree([1.0, 2.5, 3.0])
        assert result == [1, 2.5, 3]


# ---------------------------------------------------------------------------
# Golden file test
# ---------------------------------------------------------------------------


class TestGoldenOutput:
    """Test byte-identical output against golden file."""

    def test_default_fixture(self):
        golden_path = GOLDEN / "score-draft-wdfidf--default.json"
        if not golden_path.exists():
            pytest.skip("Golden file not found")

        result = score_draft_wdfidf(
            draft_path=FIXTURES / "draft.txt",
            pages_dir=FIXTURES / "pages",
            language="de",
            threshold=0.1,
        )
        output_dict = _normalize_tree(result.model_dump())
        output_json = json.dumps(output_dict, indent=2, ensure_ascii=False)

        golden = golden_path.read_text(encoding="utf-8").rstrip("\n")
        assert output_json == golden


# ---------------------------------------------------------------------------
# Integration / scoring behavior
# ---------------------------------------------------------------------------


class TestScoreDraftWdfidf:
    """Integration tests for score_draft_wdfidf."""

    def test_returns_wdfidf_score_model(self):
        from seo_pipeline.models.analysis import WdfIdfScore

        result = score_draft_wdfidf(
            draft_path=FIXTURES / "draft.txt",
            pages_dir=FIXTURES / "pages",
            language="de",
        )
        assert isinstance(result, WdfIdfScore)

    def test_meta_fields(self):
        result = score_draft_wdfidf(
            draft_path=FIXTURES / "draft.txt",
            pages_dir=FIXTURES / "pages",
            language="de",
            threshold=0.1,
        )
        assert result.meta.language == "de"
        assert result.meta.threshold == 0.1
        assert result.meta.competitor_count == 2
        assert result.meta.idf_source == "reference"

    def test_terms_sorted_by_abs_delta_descending(self):
        result = score_draft_wdfidf(
            draft_path=FIXTURES / "draft.txt",
            pages_dir=FIXTURES / "pages",
            language="de",
        )
        deltas = [abs(t.delta) for t in result.terms]
        # Check monotonically non-increasing
        for i in range(len(deltas) - 1):
            assert deltas[i] >= deltas[i + 1] or (
                deltas[i] == deltas[i + 1]
                and result.terms[i].term <= result.terms[i + 1].term
            )

    def test_signals_correct(self):
        result = score_draft_wdfidf(
            draft_path=FIXTURES / "draft.txt",
            pages_dir=FIXTURES / "pages",
            language="de",
            threshold=0.1,
        )
        for term in result.terms:
            abs_delta = abs(term.delta)
            if abs_delta < 0.1:
                assert term.signal == "ok", f"{term.term}: expected ok"
            elif term.delta < 0:
                assert term.signal == "increase", f"{term.term}: expected increase"
            else:
                assert term.signal == "decrease", f"{term.term}: expected decrease"

    def test_no_competitors(self, tmp_path):
        """Empty pages dir should produce zero terms."""
        draft = tmp_path / "draft.txt"
        draft.write_text("Some text here for testing.", encoding="utf-8")
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()

        result = score_draft_wdfidf(
            draft_path=draft,
            pages_dir=pages_dir,
            language="de",
        )
        assert result.meta.competitor_count == 0
        # All competitor_avg_wdfidf should be 0, all deltas positive or zero
        for term in result.terms:
            assert term.competitor_avg_wdfidf == 0

    def test_corpus_local_idf_fallback(self, tmp_path):
        """Non-German language falls back to corpus-local IDF."""
        draft = tmp_path / "draft.txt"
        draft.write_text("Some text here for testing.", encoding="utf-8")
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        page = {"main_content_text": "Some text with different words and content."}
        (pages_dir / "page.json").write_text(
            json.dumps(page), encoding="utf-8"
        )

        result = score_draft_wdfidf(
            draft_path=draft,
            pages_dir=pages_dir,
            language="en",
        )
        assert result.meta.idf_source == "corpus-local"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    """Tests for the CLI entry point."""

    def test_output_to_file(self, tmp_path):
        out = tmp_path / "result.json"
        main(
            [
                "--draft",
                str(FIXTURES / "draft.txt"),
                "--pages-dir",
                str(FIXTURES / "pages"),
                "--language",
                "de",
                "--threshold",
                "0.1",
                "--output",
                str(out),
            ]
        )
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "meta" in data
        assert "terms" in data
        assert len(data["terms"]) > 0

    def test_output_to_stdout(self, capsys):
        main(
            [
                "--draft",
                str(FIXTURES / "draft.txt"),
                "--pages-dir",
                str(FIXTURES / "pages"),
            ]
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "meta" in data
        assert "terms" in data
