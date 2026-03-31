"""Tests for process_keywords module."""

import json
from pathlib import Path

from seo_pipeline.keywords.process_keywords import (
    build_volume_map,
    classify_intent,
    compute_opportunity_score,
    jaccard_similarity,
    process_keywords,
    tokenize_keyword,
)
from seo_pipeline.utils.math import normalize_number

FIXTURES = Path("test/fixtures/process-keywords")
GOLDEN = Path("test/golden")


# --- normalize_number ---


class TestNormalizeNumber:
    """Tests for the normalize_number helper."""

    def test_whole_float_becomes_int(self):
        assert normalize_number(4.0) == 4
        assert isinstance(normalize_number(4.0), int)

    def test_fractional_float_stays_float(self):
        assert normalize_number(4.5) == 4.5
        assert isinstance(normalize_number(4.5), float)

    def test_int_stays_int(self):
        assert normalize_number(4) == 4
        assert isinstance(normalize_number(4), int)

    def test_none_stays_none(self):
        assert normalize_number(None) is None

    def test_zero_float_becomes_int(self):
        assert normalize_number(0.0) == 0
        assert isinstance(normalize_number(0.0), int)


# --- tokenize_keyword ---


class TestTokenizeKeyword:
    """Tests for simple whitespace tokenizer used in Jaccard clustering."""

    def test_basic_split(self):
        assert tokenize_keyword("keyword recherche") == ["keyword", "recherche"]

    def test_lowercases(self):
        assert tokenize_keyword("Keyword Recherche") == ["keyword", "recherche"]

    def test_multiple_spaces(self):
        assert tokenize_keyword("keyword  recherche") == ["keyword", "recherche"]

    def test_empty_string(self):
        assert tokenize_keyword("") == []

    def test_single_word(self):
        assert tokenize_keyword("keyword") == ["keyword"]


# --- jaccard_similarity ---


class TestJaccardSimilarity:
    """Tests for Jaccard similarity computation."""

    def test_identical_sets(self):
        s = {"keyword", "recherche"}
        assert jaccard_similarity(s, s) == 1.0

    def test_disjoint_sets(self):
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        # {keyword, recherche} vs {keyword, tool} -> intersection=1, union=3
        assert jaccard_similarity(
            {"keyword", "recherche"}, {"keyword", "tool"}
        ) == 1 / 3

    def test_empty_sets(self):
        assert jaccard_similarity(set(), set()) == 0.0

    def test_one_empty(self):
        assert jaccard_similarity({"a"}, set()) == 0.0

    def test_threshold_example(self):
        # {keyword, recherche} vs {keyword, recherche, tool} -> 2/3 >= 0.5
        sim = jaccard_similarity(
            {"keyword", "recherche"}, {"keyword", "recherche", "tool"}
        )
        assert sim >= 0.5


# --- classify_intent ---


class TestClassifyIntent:
    """Tests for intent classification."""

    def test_transactional_kaufen(self):
        assert classify_intent("seo keywords kaufen", []) == "transactional"

    def test_transactional_buy(self):
        assert classify_intent("buy keyword tool", []) == "transactional"

    def test_commercial_best(self):
        assert classify_intent("best keyword research tool", []) == "commercial"

    def test_commercial_beste(self):
        assert classify_intent("beste keyword recherche tool", []) == "commercial"

    def test_commercial_test(self):
        assert classify_intent("empty test", []) == "commercial"

    def test_informational_how(self):
        assert classify_intent("how to find keywords", []) == "informational"

    def test_informational_anleitung(self):
        assert classify_intent("keyword recherche anleitung", []) == "informational"

    def test_informational_tipps(self):
        assert classify_intent("keyword recherche tipps", []) == "informational"

    def test_informational_guide(self):
        assert classify_intent("keyword recherche guide", []) == "informational"

    def test_no_match(self):
        assert classify_intent("keyword recherche", []) is None

    def test_navigational_brand(self):
        assert classify_intent("semrush tool", ["semrush"]) == "navigational"

    def test_navigational_takes_priority(self):
        # Brand match should win over pattern match
        assert classify_intent("buy semrush", ["semrush"]) == "navigational"

    def test_transactional_over_commercial(self):
        # "kaufen" (transactional) should beat "best" (commercial)
        assert classify_intent("best tool kaufen", []) == "transactional"

    def test_case_insensitive(self):
        assert classify_intent("HOW to find", []) == "informational"


# --- compute_opportunity_score ---


class TestComputeOpportunityScore:
    """Tests for opportunity scoring with js_round semantics."""

    def test_basic_score(self):
        # 1200 / (42 + 1) = 27.906... -> js_round(2790.6...) / 100 = 27.91
        assert compute_opportunity_score(1200, 42) == 27.91

    def test_high_volume(self):
        # 5000 / (70 + 1) = 70.4225... -> js_round(7042.25...) / 100 = 70.42
        assert compute_opportunity_score(5000, 70) == 70.42

    def test_null_difficulty(self):
        assert compute_opportunity_score(1000, None) is None

    def test_null_volume(self):
        assert compute_opportunity_score(None, 50) == 0

    def test_zero_volume(self):
        assert compute_opportunity_score(0, 50) == 0

    def test_zero_difficulty(self):
        # 500 / (0 + 1) = 500.0 -> 500.0
        assert compute_opportunity_score(500, 0) == 500.0

    def test_known_scores(self):
        """Verify specific scores from golden output."""
        assert compute_opportunity_score(800, 55) == 14.29
        assert compute_opportunity_score(200, 45) == 4.35
        assert compute_opportunity_score(150, 50) == 2.94
        assert compute_opportunity_score(300, 65) == 4.55
        assert compute_opportunity_score(100, 10) == 9.09
        assert compute_opportunity_score(400, 20) == 19.05
        assert compute_opportunity_score(250, 15) == 15.63
        assert compute_opportunity_score(600, 38) == 15.38
        assert compute_opportunity_score(350, 30) == 11.29
        assert compute_opportunity_score(180, 25) == 6.92
        assert compute_opportunity_score(3000, 80) == 37.04
        assert compute_opportunity_score(500, 35) == 13.89


# --- build_volume_map ---


class TestBuildVolumeMap:
    """Tests for volume map builder."""

    def test_valid_volume_response(self):
        raw = {
            "tasks": [
                {
                    "result": [
                        {"keyword": "Test Keyword", "search_volume": 500, "cpc": 1.5},
                        {"keyword": "another", "search_volume": 100, "cpc": 0.5},
                    ]
                }
            ]
        }
        vmap = build_volume_map(raw)
        assert "test keyword" in vmap
        assert vmap["test keyword"]["search_volume"] == 500
        assert vmap["test keyword"]["cpc"] == 1.5

    def test_empty_tasks(self):
        assert build_volume_map({"tasks": []}) == {}

    def test_none_input(self):
        assert build_volume_map(None) == {}

    def test_missing_keyword(self):
        raw = {"tasks": [{"result": [{"search_volume": 100}]}]}
        assert build_volume_map(raw) == {}

    def test_null_keyword_skipped(self):
        raw = {"tasks": [{"result": [{"keyword": None, "search_volume": 100}]}]}
        # keyword is None -> skipped (matching Node.js `item?.keyword != null`)
        vmap = build_volume_map(raw)
        assert vmap == {}


# --- process_keywords (golden file parity) ---


class TestProcessKeywordsGolden:
    """Golden file parity tests."""

    def _load_fixture(self, name: str) -> dict:
        with open(FIXTURES / name, encoding="utf-8") as f:
            return json.load(f)

    def _load_golden(self, name: str) -> dict:
        with open(GOLDEN / name, encoding="utf-8") as f:
            return json.load(f)

    def test_main_fixture_byte_identical(self):
        """Full pipeline produces byte-identical output to Node.js."""
        related = self._load_fixture("related-raw.json")
        suggestions = self._load_fixture("suggestions-raw.json")

        result = process_keywords(related, suggestions, "keyword recherche")
        result_json = json.dumps(result, indent=2)
        golden_path = GOLDEN / "process-keywords.json"
        golden_json = golden_path.read_text(encoding="utf-8").rstrip("\n")

        assert result_json == golden_json

    def test_empty_fixture_byte_identical(self):
        """Empty inputs (seed only) produce byte-identical output."""
        related = self._load_fixture("related-empty.json")
        suggestions = self._load_fixture("suggestions-empty.json")

        result = process_keywords(related, suggestions, "empty test")
        result_json = json.dumps(result, indent=2)
        golden_path = GOLDEN / "process-keywords-empty.json"
        golden_json = golden_path.read_text(encoding="utf-8").rstrip("\n")

        assert result_json == golden_json

    def test_single_keyword_byte_identical(self):
        """Single keyword produces byte-identical output."""
        related = self._load_fixture("related-single.json")
        suggestions = self._load_fixture("suggestions-empty.json")

        result = process_keywords(related, suggestions, "single keyword")
        result_json = json.dumps(result, indent=2)
        golden_path = GOLDEN / "process-keywords-single.json"
        golden_json = golden_path.read_text(encoding="utf-8").rstrip("\n")

        assert result_json == golden_json


# --- process_keywords (structural tests) ---


class TestProcessKeywordsStructural:
    """Structural and behavioral tests."""

    def _load_fixture(self, name: str) -> dict:
        with open(FIXTURES / name, encoding="utf-8") as f:
            return json.load(f)

    def test_seed_always_present(self):
        """Seed keyword appears even when not in raw data."""
        related = self._load_fixture("related-empty.json")
        suggestions = self._load_fixture("suggestions-empty.json")

        result = process_keywords(related, suggestions, "unique seed")
        all_kws = [
            kw["keyword"]
            for c in result["clusters"]
            for kw in c["keywords"]
        ]
        assert "unique seed" in all_kws

    def test_dedup_case_insensitive(self):
        """Duplicate keywords (different case) are deduplicated."""
        related = self._load_fixture("related-raw.json")
        suggestions = self._load_fixture("suggestions-raw.json")

        result = process_keywords(related, suggestions, "keyword recherche")
        all_kws = [
            kw["keyword"].lower()
            for c in result["clusters"]
            for kw in c["keywords"]
        ]
        # "Keyword Analyse Tool" appears in both related (lowercase) and
        # suggestions (mixed case) -- should appear only once
        assert all_kws.count("keyword analyse tool") == 1

    def test_total_keywords_count(self):
        related = self._load_fixture("related-raw.json")
        suggestions = self._load_fixture("suggestions-raw.json")

        result = process_keywords(related, suggestions, "keyword recherche")
        assert result["total_keywords"] == 13

    def test_total_clusters_count(self):
        related = self._load_fixture("related-raw.json")
        suggestions = self._load_fixture("suggestions-raw.json")

        result = process_keywords(related, suggestions, "keyword recherche")
        assert result["total_clusters"] == 6

    def test_cluster_keyword_count_matches(self):
        """keyword_count field matches actual number of keywords in cluster."""
        related = self._load_fixture("related-raw.json")
        suggestions = self._load_fixture("suggestions-raw.json")

        result = process_keywords(related, suggestions, "keyword recherche")
        for cluster in result["clusters"]:
            assert cluster["keyword_count"] == len(cluster["keywords"])

    def test_null_llm_fields(self):
        """LLM placeholder fields are null."""
        related = self._load_fixture("related-raw.json")
        suggestions = self._load_fixture("suggestions-raw.json")

        result = process_keywords(related, suggestions, "keyword recherche")
        for cluster in result["clusters"]:
            assert cluster["cluster_label"] is None
            assert cluster["strategic_notes"] is None

    def test_keywords_sorted_by_score_within_cluster(self):
        """Keywords within each cluster are sorted by score desc."""
        related = self._load_fixture("related-raw.json")
        suggestions = self._load_fixture("suggestions-raw.json")

        result = process_keywords(related, suggestions, "keyword recherche")
        for cluster in result["clusters"]:
            scores = [
                kw["opportunity_score"] if kw["opportunity_score"] is not None else -1
                for kw in cluster["keywords"]
            ]
            assert scores == sorted(scores, reverse=True)

    def test_volume_override(self):
        """Volume from separate endpoint overrides extracted volume."""
        related = self._load_fixture("related-single.json")
        suggestions = self._load_fixture("suggestions-empty.json")
        volume_raw = {
            "tasks": [
                {
                    "result": [
                        {"keyword": "single keyword", "search_volume": 999, "cpc": 2.0}
                    ]
                }
            ]
        }

        result = process_keywords(
            related, suggestions, "single keyword", volume_raw=volume_raw
        )
        kw = result["clusters"][0]["keywords"][0]
        assert kw["search_volume"] == 999
        assert kw["cpc"] == 2

    def test_brands_navigational(self):
        """Brand keywords are classified as navigational."""
        related = self._load_fixture("related-raw.json")
        suggestions = self._load_fixture("suggestions-raw.json")

        result = process_keywords(
            related, suggestions, "keyword recherche", brands=["keyword"]
        )
        # All keywords containing "keyword" should be navigational
        for cluster in result["clusters"]:
            for kw in cluster["keywords"]:
                if "keyword" in kw["keyword"].lower():
                    assert kw["intent"] == "navigational"

    def test_every_keyword_has_opportunity_score_field(self):
        """Every keyword record has an opportunity_score field."""
        related = self._load_fixture("related-raw.json")
        suggestions = self._load_fixture("suggestions-raw.json")

        result = process_keywords(related, suggestions, "keyword recherche")
        for cluster in result["clusters"]:
            for kw in cluster["keywords"]:
                assert "opportunity_score" in kw

    def test_every_cluster_has_cluster_opportunity(self):
        """Every cluster has a cluster_opportunity field."""
        related = self._load_fixture("related-raw.json")
        suggestions = self._load_fixture("suggestions-raw.json")

        result = process_keywords(related, suggestions, "keyword recherche")
        for cluster in result["clusters"]:
            assert "cluster_opportunity" in cluster
            assert cluster["cluster_opportunity"] is not None
