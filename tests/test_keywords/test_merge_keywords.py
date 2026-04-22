"""Tests for the merge_keywords module."""

import json
from pathlib import Path

import pytest

from seo_pipeline.keywords.merge_keywords import merge_keywords

# Load fixtures from the Node.js test fixtures directory
FIXTURES_DIR = (
    Path(__file__).parent.parent.parent
    / "test"
    / "fixtures"
    / "keyword-expansion"
)


@pytest.fixture
def related_raw():
    """Load the related-raw.json fixture."""
    with open(FIXTURES_DIR / "related-raw.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def suggestions_raw():
    """Load the suggestions-raw.json fixture."""
    with open(FIXTURES_DIR / "suggestions-raw.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def kfk_raw():
    """Load the kfk-raw.json fixture."""
    with open(FIXTURES_DIR / "kfk-raw.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def related_empty():
    """Load the related-empty.json fixture."""
    with open(FIXTURES_DIR / "related-empty.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def suggestions_empty():
    """Load the suggestions-empty.json fixture."""
    with open(FIXTURES_DIR / "suggestions-empty.json", "r", encoding="utf-8") as f:
        return json.load(f)


class TestDeduplication:
    """Test keyword deduplication behavior."""

    def test_deduplicates_case_insensitive(self, related_raw, suggestions_raw):
        """Test that keywords are deduplicated case-insensitively."""
        result = merge_keywords(related_raw, suggestions_raw, "keyword recherche")

        # "Keyword Analyse" appears in both (related has "keyword analyse",
        # suggestions has "Keyword Analyse")
        analyse_entries = [
            k for k in result["keywords"]
            if k["keyword"].lower() == "keyword analyse"
        ]
        assert len(analyse_entries) == 1, "duplicate keyword must appear only once"

    def test_prefers_related_on_collision(self, related_raw, suggestions_raw):
        """Test that related_keywords entry is preferred on collision."""
        result = merge_keywords(related_raw, suggestions_raw, "keyword recherche")

        analyse = next(
            (k for k in result["keywords"]
             if k["keyword"].lower() == "keyword analyse"),
            None
        )
        assert analyse is not None
        assert analyse["source"] == "related", "duplicate should keep related source"
        # Related has search_volume 800, suggestions has 900
        assert analyse["search_volume"] == 800


class TestSeedKeywordInclusion:
    """Test seed keyword inclusion behavior."""

    def test_includes_seed_when_in_results(self, related_raw, suggestions_raw):
        """Test that seed keyword is included when present in API results."""
        result = merge_keywords(related_raw, suggestions_raw, "keyword recherche")

        assert result["seed_keyword"] == "keyword recherche"
        seed = next(
            (k for k in result["keywords"] if k["keyword"] == "keyword recherche"),
            None
        )
        assert seed is not None, "seed keyword must be in the list"

    def test_adds_seed_when_absent(self, related_empty, suggestions_empty):
        """Test that seed keyword is added even when absent from API results."""
        result = merge_keywords(related_empty, suggestions_empty, "my unique seed")

        assert result["total_keywords"] == 1
        assert result["keywords"][0]["keyword"] == "my unique seed"
        assert result["keywords"][0]["source"] == "seed"
        assert result["keywords"][0]["search_volume"] is None
        assert result["keywords"][0]["cpc"] is None
    def test_does_not_duplicate_seed(self, related_raw, suggestions_raw):
        """Test that seed keyword is not duplicated when already present."""
        result = merge_keywords(related_raw, suggestions_raw, "keyword recherche")

        seed_entries = [
            k for k in result["keywords"]
            if k["keyword"].lower() == "keyword recherche"
        ]
        assert len(seed_entries) == 1, "seed must not be duplicated"

    def test_seed_matching_case_insensitive(self, related_raw, suggestions_raw):
        """Test that seed keyword matching is case-insensitive."""
        result = merge_keywords(related_raw, suggestions_raw, "Keyword Recherche")

        # Seed "Keyword Recherche" should match "keyword recherche" in results
        seed_entries = [
            k for k in result["keywords"]
            if k["keyword"].lower() == "keyword recherche"
        ]
        assert (
            len(seed_entries) == 1
        ), "case-insensitive seed should not create duplicate"


class TestCaseInsensitiveMerging:
    """Test case-insensitive merging behavior."""

    def test_treats_differently_cased_as_same(self, related_raw, suggestions_raw):
        """Test that differently-cased keywords are treated as the same."""
        result = merge_keywords(related_raw, suggestions_raw, "keyword recherche")

        keyword_set = {k["keyword"].lower() for k in result["keywords"]}
        assert "keyword planner" in keyword_set
        assert "keyword recherche tool" in keyword_set

    def test_preserves_original_casing(self, related_raw, suggestions_raw):
        """Test that the original keyword casing from the source is preserved."""
        result = merge_keywords(related_raw, suggestions_raw, "keyword recherche")

        # Find the "Keyword Planner" entry
        planner = next(
            (k for k in result["keywords"]
             if k["keyword"].lower() == "keyword planner"),
            None
        )
        assert planner is not None
        # The original casing from related_keywords should be preserved
        assert planner["keyword"] == "Keyword Planner"


class TestSorting:
    """Test sorting behavior."""

    def test_sorts_by_volume_descending(self, related_raw, suggestions_raw):
        """Test that results are sorted by search_volume descending."""
        result = merge_keywords(related_raw, suggestions_raw, "keyword recherche")

        volumes = [
            k["search_volume"] if k["search_volume"] is not None else -1
            for k in result["keywords"]
        ]
        for i in range(1, len(volumes)):
            assert (
                volumes[i] <= volumes[i - 1]
            ), f"volume at index {i} should be <= volume at index {i - 1}"

    def test_uses_alphabetical_tiebreak(self, related_raw, suggestions_raw):
        """Test that alphabetical order is used for equal volumes."""
        result = merge_keywords(related_raw, suggestions_raw, "keyword recherche")

        for i in range(1, len(result["keywords"])):
            prev = result["keywords"][i - 1]
            curr = result["keywords"][i]
            prev_vol = (
                prev["search_volume"]
                if prev["search_volume"] is not None
                else -1
            )
            curr_vol = (
                curr["search_volume"]
                if curr["search_volume"] is not None
                else -1
            )

            if prev_vol == curr_vol:
                # For equal volumes, alphabetical order should be maintained
                prev_lower = prev["keyword"].lower()
                curr_lower = curr["keyword"].lower()
                assert (
                    prev_lower <= curr_lower
                ), f'"{prev["keyword"]}" should come before "{curr["keyword"]}"'


class TestEmptyAndMalformed:
    """Test handling of empty and malformed responses."""

    def test_handles_empty_responses(self, related_empty, suggestions_empty):
        """Test handling when both endpoints return empty results."""
        result = merge_keywords(related_empty, suggestions_empty, "empty test")

        assert result["total_keywords"] == 1, "only seed keyword should be present"
        assert result["keywords"][0]["keyword"] == "empty test"
        assert result["keywords"][0]["source"] == "seed"

    def test_handles_malformed_items(self, suggestions_empty):
        """Test that malformed items are gracefully skipped."""
        # Load malformed response
        with open(
            FIXTURES_DIR / "malformed-response.json", "r", encoding="utf-8"
        ) as f:
            malformed = json.load(f)

        result = merge_keywords(malformed, suggestions_empty, "test seed")

        keywords = {k["keyword"] for k in result["keywords"]}
        assert "valid keyword" in keywords, "valid keyword should be extracted"
        assert "test seed" in keywords, "seed should be present"
        assert result["total_keywords"] == 2


class TestKfkIntegration:
    """Test keywords_for_keywords third source integration."""

    def test_kfk_keywords_included(
        self, related_empty, suggestions_empty, kfk_raw
    ):
        """KFK keywords are included when both other sources are empty."""
        result = merge_keywords(
            related_empty, suggestions_empty, "sintra", kfk_raw=kfk_raw
        )
        kfk_kws = [k for k in result["keywords"] if k["source"] == "kfk"]
        assert len(kfk_kws) >= 1

    def test_kfk_dedup_priority(self, related_raw, suggestions_raw, kfk_raw):
        """Related > suggestions > kfk dedup priority is respected."""
        result = merge_keywords(
            related_raw, suggestions_raw, "keyword recherche", kfk_raw=kfk_raw
        )
        # All KFK keywords that share a name with related/suggestions
        # should NOT appear as kfk source
        for kw in result["keywords"]:
            if kw["source"] == "kfk":
                key = kw["keyword"].lower()
                related_keys = {
                    k["keyword"].lower()
                    for k in merge_keywords(
                        related_raw, suggestions_raw, "keyword recherche"
                    )["keywords"]
                }
                assert key not in related_keys

    def test_kfk_none_backward_compatible(self, related_raw, suggestions_raw):
        """When kfk_raw is None, output matches two-source merge."""
        result_two = merge_keywords(related_raw, suggestions_raw, "keyword recherche")
        result_three = merge_keywords(
            related_raw, suggestions_raw, "keyword recherche", kfk_raw=None
        )
        assert result_two == result_three

    def test_kfk_source_label(
        self, related_empty, suggestions_empty, kfk_raw
    ):
        """KFK-sourced keywords have source='kfk'."""
        result = merge_keywords(
            related_empty, suggestions_empty, "sintra", kfk_raw=kfk_raw
        )
        kfk_kws = [k for k in result["keywords"] if k["source"] == "kfk"]
        assert len(kfk_kws) > 0
        # All KFK keywords should have the correct source
        for kw in kfk_kws:
            assert kw["source"] == "kfk"

    def test_kfk_related_wins_collision(self, suggestions_empty, kfk_raw):
        """When related and KFK have same keyword, related wins."""
        # Build a related response that contains one of the KFK keywords
        related_with_overlap = {
            "tasks": [{"result": [{"items": [
                {
                    "keyword_data": {
                        "keyword": "sintra pena palace",
                        "keyword_info": {"search_volume": 999, "cpc": 9.99},
                        "keyword_properties": {},
                    }
                }
            ]}]}]
        }
        result = merge_keywords(
            related_with_overlap, suggestions_empty, "sintra", kfk_raw=kfk_raw
        )
        match = next(
            k for k in result["keywords"]
            if k["keyword"].lower() == "sintra pena palace"
        )
        assert match["source"] == "related"
        assert match["search_volume"] == 999


class TestOutputStructure:
    """Test output structure and fields."""

    def test_includes_required_top_level_fields(self, related_raw, suggestions_raw):
        """Test that required top-level fields are present."""
        result = merge_keywords(related_raw, suggestions_raw, "keyword recherche")

        assert "seed_keyword" in result
        assert "total_keywords" in result
        assert "keywords" in result
        assert isinstance(result["keywords"], list)
        assert result["total_keywords"] == len(result["keywords"])

    def test_includes_required_keyword_fields(self, related_raw, suggestions_raw):
        """Test that required fields are present per keyword."""
        result = merge_keywords(related_raw, suggestions_raw, "keyword recherche")

        for kw in result["keywords"]:
            assert "keyword" in kw, "keyword field required"
            assert "search_volume" in kw, "search_volume field required"
            assert "cpc" in kw, "cpc field required"
            assert "source" in kw, "source field required"

    def test_source_field_values(self, related_raw, suggestions_raw):
        """Test that source field contains valid values."""
        result = merge_keywords(related_raw, suggestions_raw, "keyword recherche")

        valid_sources = {"related", "suggestions", "kfk", "seed"}
        for kw in result["keywords"]:
            assert kw["source"] in valid_sources, (
                f"source must be one of {valid_sources}, got {kw['source']}"
            )


class TestDeterminism:
    """Test deterministic behavior."""

    def test_produces_consistent_output(self, related_raw, suggestions_raw):
        """Test that identical input produces identical output."""
        result1 = merge_keywords(related_raw, suggestions_raw, "keyword recherche")
        result2 = merge_keywords(related_raw, suggestions_raw, "keyword recherche")

        # Convert to JSON strings for byte-identical comparison
        json1 = json.dumps(result1, indent=2, sort_keys=True)
        json2 = json.dumps(result2, indent=2, sort_keys=True)
        assert json1 == json2, "identical input must produce identical output"
