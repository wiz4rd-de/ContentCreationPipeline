"""Tests for prepare_strategist_data module."""

import json
from pathlib import Path

import pytest

from seo_pipeline.keywords.prepare_strategist_data import (
    _deduplicate_with_year_normalization,
    _extract_paa_questions,
    _extract_serp_snippets,
    _flatten_keywords,
    _is_foreign_language,
    _process_competitor_keywords,
    _sort_by_volume_desc,
    _year_normalized_key,
    prepare_strategist_data,
)


class TestYearNormalization:
    """Test year normalization for dedup."""

    def test_replaces_2024_with_yyyy(self):
        """Test that 2024 is replaced with YYYY."""
        result = _year_normalized_key("seo reporting 2024")
        assert result == "seo reporting yyyy"

    def test_replaces_2025_with_yyyy(self):
        """Test that 2025 is replaced with YYYY."""
        result = _year_normalized_key("seo reporting 2025")
        assert result == "seo reporting yyyy"

    def test_replaces_2029_with_yyyy(self):
        """Test that 2029 is replaced with YYYY."""
        result = _year_normalized_key("seo reporting 2029")
        assert result == "seo reporting yyyy"

    def test_does_not_replace_2023(self):
        """Test that 2023 is not replaced."""
        result = _year_normalized_key("seo reporting 2023")
        assert result == "seo reporting 2023"

    def test_does_not_replace_2030(self):
        """Test that 2030 is not replaced."""
        result = _year_normalized_key("seo reporting 2030")
        assert result == "seo reporting 2030"

    def test_lowercases_and_trims(self):
        """Test that keyword is lowercased and trimmed."""
        result = _year_normalized_key("  SEO REPORTING 2025  ")
        assert result == "seo reporting yyyy"

    def test_word_boundary_only(self):
        """Test that year replacement respects word boundaries."""
        result = _year_normalized_key("https2025 is not a year")
        assert result == "https2025 is not a year"


class TestForeignLanguageDetection:
    """Test foreign language detection."""

    def test_english_keyword_is_latin(self):
        """Test that English keywords are detected as Latin."""
        assert not _is_foreign_language("seo reporting")

    def test_german_keyword_is_latin(self):
        """Test that German keywords (with umlauts) are Latin."""
        assert not _is_foreign_language("seo bericht erstellen")

    def test_cyrillic_keyword_is_foreign(self):
        """Test that Cyrillic keywords are detected as foreign."""
        assert _is_foreign_language("сео репортинг")

    def test_chinese_keyword_is_foreign(self):
        """Test that Chinese keywords are detected as foreign."""
        assert _is_foreign_language("广告分析")

    def test_mixed_latin_and_cyrillic_is_foreign(self):
        """Test that mixed Latin and Cyrillic is detected as foreign."""
        assert _is_foreign_language("seo репортинг")

    def test_hyphens_and_apostrophes_allowed(self):
        """Test that hyphens and apostrophes are allowed."""
        assert not _is_foreign_language("seo-reporting")
        assert not _is_foreign_language("don't worry")


class TestFlattenKeywords:
    """Test keyword flattening from clusters."""

    def test_empty_clusters(self):
        """Test with no clusters."""
        result = _flatten_keywords({"clusters": []})
        assert result == []

    def test_none_clusters(self):
        """Test with None clusters."""
        result = _flatten_keywords({"clusters": None})
        assert result == []

    def test_missing_clusters(self):
        """Test with missing clusters key."""
        result = _flatten_keywords({})
        assert result == []

    def test_single_cluster_multiple_keywords(self):
        """Test flattening a single cluster with multiple keywords."""
        data = {
            "clusters": [
                {
                    "cluster_keyword": "test",
                    "keywords": [
                        {"keyword": "kw1"},
                        {"keyword": "kw2"},
                    ],
                }
            ]
        }
        result = _flatten_keywords(data)
        assert len(result) == 2
        assert result[0]["keyword"] == "kw1"
        assert result[1]["keyword"] == "kw2"

    def test_multiple_clusters(self):
        """Test flattening multiple clusters."""
        data = {
            "clusters": [
                {"keywords": [{"keyword": "kw1"}]},
                {"keywords": [{"keyword": "kw2"}, {"keyword": "kw3"}]},
            ]
        }
        result = _flatten_keywords(data)
        assert len(result) == 3

    def test_cluster_with_no_keywords(self):
        """Test cluster without keywords key."""
        data = {
            "clusters": [
                {"cluster_keyword": "test"},
            ]
        }
        result = _flatten_keywords(data)
        assert result == []


class TestDeduplication:
    """Test year-normalization deduplication."""

    def test_keeps_single_keyword(self):
        """Test that single keyword is kept."""
        kws = [{"keyword": "seo reporting", "search_volume": 100}]
        result, count = _deduplicate_with_year_normalization(kws)
        assert len(result) == 1
        assert result[0]["keyword"] == "seo reporting"
        assert count == 0

    def test_deduplicates_identical_keywords(self):
        """Test deduplication of identical keywords."""
        kws = [
            {"keyword": "seo reporting", "search_volume": 100},
            {"keyword": "seo reporting", "search_volume": 50},
        ]
        result, count = _deduplicate_with_year_normalization(kws)
        assert len(result) == 1
        assert result[0]["search_volume"] == 100  # Higher volume kept
        assert count == 1

    def test_keeps_higher_volume_when_year_varies(self):
        """Test that higher volume is kept when year varies."""
        kws = [
            {"keyword": "seo reporting 2025", "search_volume": 100},
            {"keyword": "seo reporting 2026", "search_volume": 150},
        ]
        result, count = _deduplicate_with_year_normalization(kws)
        assert len(result) == 1
        assert result[0]["keyword"] == "seo reporting 2026"
        assert result[0]["search_volume"] == 150
        assert count == 1

    def test_alphabetical_tiebreak_on_equal_volume(self):
        """Test alphabetical tie-break when volumes are equal."""
        kws = [
            {"keyword": "seo reporting 2026", "search_volume": 100},
            {"keyword": "Seo Reporting 2025", "search_volume": 100},
        ]
        result, count = _deduplicate_with_year_normalization(kws)
        assert len(result) == 1
        # "seo reporting 2025" lowercased is < "seo reporting 2026" lowercased,
        # so Seo Reporting 2025 should be kept (compared by lowercased)
        assert result[0]["keyword"] == "Seo Reporting 2025"
        assert count == 1

    def test_handles_none_volume(self):
        """Test handling of None volume."""
        kws = [
            {"keyword": "seo reporting 2025"},
            {"keyword": "seo reporting 2026", "search_volume": 100},
        ]
        result, count = _deduplicate_with_year_normalization(kws)
        assert len(result) == 1
        assert result[0]["search_volume"] == 100


class TestSortByVolume:
    """Test sorting by volume descending."""

    def test_sorts_by_volume_descending(self):
        """Test sorting by volume in descending order."""
        kws = [
            {"keyword": "a", "search_volume": 100},
            {"keyword": "b", "search_volume": 200},
            {"keyword": "c", "search_volume": 50},
        ]
        result = _sort_by_volume_desc(kws)
        assert result[0]["keyword"] == "b"
        assert result[1]["keyword"] == "a"
        assert result[2]["keyword"] == "c"

    def test_alphabetical_tiebreak(self):
        """Test alphabetical tiebreak when volumes are equal."""
        kws = [
            {"keyword": "Bee", "search_volume": 100},
            {"keyword": "apple", "search_volume": 100},
            {"keyword": "cherry", "search_volume": 100},
        ]
        result = _sort_by_volume_desc(kws)
        assert result[0]["keyword"] == "apple"
        assert result[1]["keyword"] == "Bee"
        assert result[2]["keyword"] == "cherry"

    def test_handles_none_volume(self):
        """Test that None volume is treated as lowest."""
        kws = [
            {"keyword": "a", "search_volume": 100},
            {"keyword": "b"},
            {"keyword": "c", "search_volume": 50},
        ]
        result = _sort_by_volume_desc(kws)
        assert result[0]["keyword"] == "a"
        assert result[1]["keyword"] == "c"
        assert result[2]["keyword"] == "b"


class TestExtractPAAQuestions:
    """Test PAA extraction."""

    def test_empty_serp_data(self):
        """Test with no SERP data."""
        result = _extract_paa_questions({})
        assert result == []

    def test_no_paa(self):
        """Test with no PAA in SERP data."""
        result = _extract_paa_questions({"serp_features": {}})
        assert result == []

    def test_string_format_paa(self):
        """Test PAA in legacy string format."""
        data = {
            "serp_features": {
                "people_also_ask": [
                    "What is SEO?",
                    "How to do SEO?",
                ]
            }
        }
        result = _extract_paa_questions(data)
        assert len(result) == 2
        assert result[0]["question"] == "What is SEO?"
        assert result[0]["answer"] is None
        assert result[1]["question"] == "How to do SEO?"

    def test_object_format_paa(self):
        """Test PAA in object format with answers."""
        data = {
            "serp_features": {
                "people_also_ask": [
                    {
                        "question": "What is SEO?",
                        "answer": "SEO is search engine optimization.",
                    },
                    {"question": "How to do SEO?", "answer": None},
                ]
            }
        }
        result = _extract_paa_questions(data)
        assert len(result) == 2
        assert result[0]["question"] == "What is SEO?"
        assert result[0]["answer"] == "SEO is search engine optimization."
        assert result[1]["answer"] is None

    def test_mixed_format_paa(self):
        """Test mixed string and object format."""
        data = {
            "serp_features": {
                "people_also_ask": [
                    "What is SEO?",
                    {"question": "How to do SEO?", "answer": "Step by step..."},
                ]
            }
        }
        result = _extract_paa_questions(data)
        assert len(result) == 2

    def test_skips_empty_string_questions(self):
        """Test that empty string questions are skipped."""
        data = {
            "serp_features": {
                "people_also_ask": [
                    "",
                    "What is SEO?",
                ]
            }
        }
        result = _extract_paa_questions(data)
        assert len(result) == 1
        assert result[0]["question"] == "What is SEO?"


class TestExtractSERPSnippets:
    """Test SERP snippet extraction."""

    def test_empty_competitors(self):
        """Test with no competitors."""
        result = _extract_serp_snippets({})
        assert result == []

    def test_skips_if_no_title_and_description(self):
        """Test that entries with neither title nor description are skipped."""
        data = {
            "competitors": [
                {"rank": 1, "url": "https://example.com"},
                {"rank": 2, "title": "Title", "url": "https://example.org"},
            ]
        }
        result = _extract_serp_snippets(data)
        assert len(result) == 1

    def test_extracts_all_fields(self):
        """Test extraction of all snippet fields."""
        data = {
            "competitors": [
                {
                    "rank": 1,
                    "title": "Title",
                    "description": "Description",
                    "url": "https://example.com",
                    "domain": "example.com",
                }
            ]
        }
        result = _extract_serp_snippets(data)
        assert len(result) == 1
        snippet = result[0]
        assert snippet["rank"] == 1
        assert snippet["title"] == "Title"
        assert snippet["description"] == "Description"
        assert snippet["url"] == "https://example.com"
        assert snippet["domain"] == "example.com"

    def test_handles_missing_optional_fields(self):
        """Test handling of missing optional fields."""
        data = {
            "competitors": [
                {
                    "title": "Title",
                }
            ]
        }
        result = _extract_serp_snippets(data)
        assert len(result) == 1
        snippet = result[0]
        assert snippet["rank"] is None
        assert snippet["domain"] is None


class TestProcessCompetitorKeywords:
    """Test competitor keyword processing."""

    def test_empty_list(self):
        """Test with empty competitor keywords list."""
        result = _process_competitor_keywords([])
        assert result == []

    def test_none_input(self):
        """Test with None input."""
        result = _process_competitor_keywords(None)
        assert result == []

    def test_sorts_by_volume_desc(self):
        """Test that keywords are sorted by volume descending."""
        data = [
            {"keyword": "a", "search_volume": 100},
            {"keyword": "b", "search_volume": 200},
            {"keyword": "c", "search_volume": 50},
        ]
        result = _process_competitor_keywords(data)
        assert result[0]["keyword"] == "b"
        assert result[1]["keyword"] == "a"
        assert result[2]["keyword"] == "c"

    def test_skips_if_no_keyword_and_volume(self):
        """Test that entries with neither keyword nor volume are skipped."""
        data = [
            {"keyword": "a", "search_volume": 100},
            {"difficulty": 50},
            {"keyword": "b", "search_volume": 50},
        ]
        result = _process_competitor_keywords(data)
        assert len(result) == 2

    def test_includes_all_fields(self):
        """Test that all fields are included."""
        data = [
            {"keyword": "a", "search_volume": 100, "difficulty": 50}
        ]
        result = _process_competitor_keywords(data)
        assert len(result) == 1
        assert result[0]["keyword"] == "a"
        assert result[0]["search_volume"] == 100
        assert result[0]["difficulty"] == 50


class TestPrepareStrategistData:
    """Integration tests for prepare_strategist_data."""

    @pytest.fixture
    def fixture_dir(self):
        """Return path to test fixtures."""
        return (
            Path(__file__).parent.parent.parent
            / "test"
            / "fixtures"
            / "prepare-strategist-data"
        )

    def test_with_default_fixture(self, fixture_dir):
        """Test with default fixture - integration test."""
        keywords_file = fixture_dir / "keywords-processed.json"
        serp_file = fixture_dir / "serp-processed.json"
        competitor_file = fixture_dir / "competitor-kws.json"

        with open(keywords_file) as f:
            keywords_data = json.load(f)
        with open(serp_file) as f:
            serp_data = json.load(f)
        with open(competitor_file) as f:
            competitor_kws = json.load(f)

        result = prepare_strategist_data(
            keywords_data,
            serp_data,
            "seo reporting",
            competitor_kws,
        )

        # Verify structure
        assert "seed_keyword" in result
        assert "top_keywords" in result
        assert "all_keywords" in result
        assert "autocomplete" in result
        assert "content_ideas" in result
        assert "paa_questions" in result
        assert "serp_snippets" in result
        assert "competitor_keywords" in result
        assert "stats" in result

        # Verify seed keyword
        assert result["seed_keyword"] == "seo reporting"

        # Verify top keywords (max 20)
        assert len(result["top_keywords"]) <= 20

        # Verify stats structure
        stats = result["stats"]
        assert "total_keywords" in stats
        assert "keywords_with_volume" in stats
        assert "avg_difficulty" in stats
        assert "foreign_filtered_count" in stats
        assert "year_dedup_count" in stats

    def test_with_empty_fixture(self, fixture_dir):
        """Test with empty fixture."""
        keywords_file = fixture_dir / "keywords-processed-empty.json"
        serp_file = fixture_dir / "serp-processed-empty.json"

        with open(keywords_file) as f:
            keywords_data = json.load(f)
        with open(serp_file) as f:
            serp_data = json.load(f)

        result = prepare_strategist_data(
            keywords_data,
            serp_data,
            "seo reporting",
        )

        # Verify structure even with empty data
        assert result["seed_keyword"] == "seo reporting"
        assert isinstance(result["all_keywords"], list)
        assert isinstance(result["stats"], dict)

    def test_golden_default(self, fixture_dir):
        """Test against golden output."""
        golden_file = (
            Path(__file__).parent.parent
            / "golden"
            / "prepare-strategist-data--default.json"
        )
        keywords_file = fixture_dir / "keywords-processed.json"
        serp_file = fixture_dir / "serp-processed.json"
        competitor_file = fixture_dir / "competitor-kws.json"

        with open(keywords_file) as f:
            keywords_data = json.load(f)
        with open(serp_file) as f:
            serp_data = json.load(f)
        with open(competitor_file) as f:
            competitor_kws = json.load(f)

        result = prepare_strategist_data(
            keywords_data,
            serp_data,
            "seo reporting",
            competitor_kws,
        )

        with open(golden_file) as f:
            expected = json.load(f)

        # Compare JSON byte-for-byte
        assert json.dumps(result, sort_keys=True) == json.dumps(
            expected, sort_keys=True
        )

    def test_year_dedup_removes_duplicates(self):
        """Test that year dedup removes keywords with year variations."""
        keywords_data = {
            "clusters": [
                {
                    "cluster_keyword": "test",
                    "keywords": [
                        {"keyword": "seo reporting 2025", "search_volume": 100},
                        {"keyword": "seo reporting 2026", "search_volume": 150},
                    ],
                }
            ]
        }
        serp_data = {"serp_features": {}, "competitors": []}

        result = prepare_strategist_data(keywords_data, serp_data, "seo")

        # Should have only 1 keyword after dedup (the 2026 version with higher volume)
        assert len(result["all_keywords"]) == 1
        assert result["all_keywords"][0]["keyword"] == "seo reporting 2026"
        assert result["stats"]["year_dedup_count"] == 1

    def test_foreign_language_filtered(self):
        """Test that foreign language keywords are filtered."""
        keywords_data = {
            "clusters": [
                {
                    "cluster_keyword": "test",
                    "keywords": [
                        {"keyword": "seo reporting", "search_volume": 100},
                        {"keyword": "сео репортинг", "search_volume": 150},  # Cyrillic
                    ],
                }
            ]
        }
        serp_data = {"serp_features": {}, "competitors": []}

        result = prepare_strategist_data(keywords_data, serp_data, "seo")

        # Should have only 1 keyword after filtering
        assert len(result["all_keywords"]) == 1
        assert result["all_keywords"][0]["keyword"] == "seo reporting"
        assert result["stats"]["foreign_filtered_count"] == 1

    def test_autocomplete_classification(self):
        """Test that keywords containing seed are in autocomplete."""
        keywords_data = {
            "clusters": [
                {
                    "cluster_keyword": "test",
                    "keywords": [
                        {"keyword": "seo reporting", "search_volume": 100},
                        {"keyword": "seo reporting tools", "search_volume": 50},
                        {"keyword": "web analytics", "search_volume": 75},
                    ],
                }
            ]
        }
        serp_data = {"serp_features": {}, "competitors": []}

        result = prepare_strategist_data(keywords_data, serp_data, "seo reporting")

        # "seo reporting tools" contains seed, should be in autocomplete
        assert "seo reporting tools" in result["autocomplete"]
        # "web analytics" doesn't contain seed, should be in content_ideas
        assert "web analytics" in result["content_ideas"]

    def test_top_20_limit(self):
        """Test that top_keywords is limited to 20."""
        keywords_data = {
            "clusters": [
                {
                    "cluster_keyword": "test",
                    "keywords": [
                        {"keyword": f"keyword {i}", "search_volume": 1000 - i}
                        for i in range(30)
                    ],
                }
            ]
        }
        serp_data = {"serp_features": {}, "competitors": []}

        result = prepare_strategist_data(keywords_data, serp_data, "test")

        assert len(result["top_keywords"]) == 20
        assert len(result["all_keywords"]) == 30
