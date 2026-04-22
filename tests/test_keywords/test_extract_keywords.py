"""Tests for extract_keywords module."""

import json
from pathlib import Path

from seo_pipeline.keywords.extract_keywords import extract_keywords, normalize_item


class TestNormalizeItem:
    """Tests for normalize_item function."""

    def test_related_keywords_shape(self):
        """Test normalization of related_keywords response shape."""
        item = {
            "keyword_data": {
                "keyword": "test keyword",
                "keyword_info": {"search_volume": 100},
                "keyword_properties": {"keyword_difficulty": 25},
            }
        }
        result = normalize_item(item)
        assert result is not None
        assert result["keyword"] == "test keyword"
        assert result["info"] == {"search_volume": 100}
        assert result["props"] == {"keyword_difficulty": 25}

    def test_keyword_suggestions_shape(self):
        """Test normalization of keyword_suggestions response shape."""
        item = {
            "keyword": "test keyword",
            "keyword_info": {"search_volume": 200},
            "keyword_properties": {"keyword_difficulty": 50},
        }
        result = normalize_item(item)
        assert result is not None
        assert result["keyword"] == "test keyword"
        assert result["info"] == {"search_volume": 200}
        assert result["props"] == {"keyword_difficulty": 50}

    def test_related_keywords_missing_keyword_data(self):
        """Test that missing keyword returns None."""
        item = {"keyword_data": {}}
        result = normalize_item(item)
        assert result is None

    def test_keyword_suggestions_missing_keyword(self):
        """Test that missing keyword in suggestions shape returns None."""
        item = {"keyword_info": {"search_volume": 100}}
        result = normalize_item(item)
        assert result is None

    def test_none_item(self):
        """Test that None item returns None."""
        result = normalize_item(None)
        assert result is None

    def test_empty_item(self):
        """Test that empty item returns None."""
        result = normalize_item({})
        assert result is None

    def test_kfk_flat_shape(self):
        """Test normalization of keywords_for_keywords flat Google Ads shape."""
        item = {
            "keyword": "sintra pena palace",
            "location_code": 2276,
            "language_code": "de",
            "search_volume": 210,
            "cpc": 1.07,
            "competition": "LOW",
            "competition_index": 7,
            "monthly_searches": [
                {"year": 2025, "month": 3, "search_volume": 170},
            ],
        }
        result = normalize_item(item)
        assert result is not None
        assert result["keyword"] == "sintra pena palace"
        # info should be the item itself (flat keys)
        assert result["info"]["search_volume"] == 210
        assert result["info"]["cpc"] == 1.07
        assert result["info"]["monthly_searches"][0]["search_volume"] == 170
        # No keyword_properties in KFK
        assert result["props"] == {}

    def test_kfk_null_cpc(self):
        """Test KFK item with null CPC (common for low-competition keywords)."""
        item = {
            "keyword": "sintra strand",
            "search_volume": 50,
            "cpc": None,
            "competition": "LOW",
            "monthly_searches": [],
        }
        result = normalize_item(item)
        assert result is not None
        assert result["keyword"] == "sintra strand"
        assert result["info"]["cpc"] is None

    def test_kfk_vs_suggestions_disambiguation(self):
        """KFK shape (search_volume at top) vs suggestions (keyword_info nested)."""
        # KFK: has search_volume at top, no keyword_info
        kfk_item = {"keyword": "kw", "search_volume": 100, "cpc": 0.5}
        kfk_result = normalize_item(kfk_item)
        assert kfk_result["info"]["search_volume"] == 100

        # Suggestions: has keyword_info nested
        sug_item = {
            "keyword": "kw",
            "keyword_info": {"search_volume": 200},
            "keyword_properties": {},
        }
        sug_result = normalize_item(sug_item)
        assert sug_result["info"]["search_volume"] == 200

    def test_missing_optional_fields(self):
        """Test that missing optional keyword_info and keyword_properties."""
        item = {"keyword": "test", "keyword_info": {}}
        result = normalize_item(item)
        assert result is not None
        assert result["keyword"] == "test"
        assert result["info"] == {}
        assert result["props"] == {}

    def test_none_optional_fields(self):
        """Test that None values for optional fields are handled as empty dicts."""
        item = {
            "keyword": "test",
            "keyword_info": None,
            "keyword_properties": None,
        }
        result = normalize_item(item)
        assert result is not None
        assert result["keyword"] == "test"
        assert result["info"] == {}
        assert result["props"] == {}


class TestExtractKeywords:
    """Tests for extract_keywords function."""

    def test_extract_from_related_keywords_fixture(self):
        """Test extraction from related_keywords response shape."""
        fixture_path = (
            Path(__file__).parent.parent.parent
            / "test"
            / "fixtures"
            / "keyword-expansion"
            / "related-raw.json"
        )
        with open(fixture_path) as f:
            raw = json.load(f)

        results = extract_keywords(raw)
        assert len(results) > 0
        assert all("keyword" in r for r in results)
        assert all("search_volume" in r for r in results)
        assert all("cpc" in r for r in results)
        assert all("monthly_searches" in r for r in results)
        # Should not have difficulty when include_difficulty=False
        assert all("difficulty" not in r for r in results)

    def test_extract_from_keyword_suggestions_fixture(self):
        """Test extraction from keyword_suggestions response shape."""
        fixture_path = (
            Path(__file__).parent.parent.parent
            / "test"
            / "fixtures"
            / "keyword-expansion"
            / "suggestions-raw.json"
        )
        with open(fixture_path) as f:
            raw = json.load(f)

        results = extract_keywords(raw)
        assert len(results) > 0
        assert all("keyword" in r for r in results)
        assert all("search_volume" in r for r in results)
        assert all("cpc" in r for r in results)
        assert all("monthly_searches" in r for r in results)
        assert all("difficulty" not in r for r in results)

    def test_extract_from_kfk_fixture(self):
        """Test extraction from keywords_for_keywords response shape."""
        fixture_path = (
            Path(__file__).parent.parent.parent
            / "test"
            / "fixtures"
            / "keyword-expansion"
            / "kfk-raw.json"
        )
        with open(fixture_path) as f:
            raw = json.load(f)

        results = extract_keywords(raw)
        assert len(results) == 4
        assert all("keyword" in r for r in results)
        assert all("search_volume" in r for r in results)
        assert all("cpc" in r for r in results)
        assert all("monthly_searches" in r for r in results)
        # Check specific values
        assert results[0]["keyword"] == "sintra pena palace"
        assert results[0]["search_volume"] == 210
        assert results[0]["cpc"] == 1.07
        # Null CPC should be preserved
        assert results[3]["keyword"] == "sintra strand"
        assert results[3]["cpc"] is None

    def test_extract_kfk_same_shape_as_labs(self):
        """KFK extraction produces same record shape as Labs endpoints."""
        kfk_raw = {
            "tasks": [{"result": [{"items": [
                {"keyword": "test kfk", "search_volume": 100, "cpc": 0.5,
                 "monthly_searches": [], "competition": "LOW"},
            ]}]}]
        }
        labs_raw = {
            "tasks": [{"result": [{"items": [
                {"keyword": "test labs",
                 "keyword_info": {"search_volume": 200, "cpc": 1.0,
                                  "monthly_searches": []},
                 "keyword_properties": {}},
            ]}]}]
        }

        kfk_results = extract_keywords(kfk_raw)
        labs_results = extract_keywords(labs_raw)

        # Same keys in output
        assert set(kfk_results[0].keys()) == set(labs_results[0].keys())

    def test_extract_with_difficulty(self):
        """Test extraction with include_difficulty=True."""
        fixture_path = (
            Path(__file__).parent.parent.parent
            / "test"
            / "fixtures"
            / "keyword-expansion"
            / "suggestions-raw-flat.json"
        )
        with open(fixture_path) as f:
            raw = json.load(f)

        results = extract_keywords(raw, include_difficulty=True)
        assert len(results) > 0
        assert all("difficulty" in r for r in results)
        # All difficulty values should be integers in [0, 100]
        for r in results:
            assert isinstance(r["difficulty"], int)
            assert 0 <= r["difficulty"] <= 100

    def test_difficulty_clamping(self):
        """Test that difficulty is clamped to [0, 100]."""
        raw = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "keyword": "test1",
                                    "keyword_info": {},
                                    "keyword_properties": {"keyword_difficulty": -10},
                                },
                                {
                                    "keyword": "test2",
                                    "keyword_info": {},
                                    "keyword_properties": {"keyword_difficulty": 150},
                                },
                                {
                                    "keyword": "test3",
                                    "keyword_info": {},
                                    "keyword_properties": {"keyword_difficulty": 50},
                                },
                            ]
                        }
                    ]
                }
            ]
        }
        results = extract_keywords(raw, include_difficulty=True)
        assert results[0]["difficulty"] == 0  # -10 clamped to 0
        assert results[1]["difficulty"] == 100  # 150 clamped to 100
        assert results[2]["difficulty"] == 50  # 50 unchanged

    def test_difficulty_rounding(self):
        """Test that difficulty is rounded with JavaScript semantics."""
        raw = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "keyword": "test1",
                                    "keyword_info": {},
                                    "keyword_properties": {"keyword_difficulty": 25.4},
                                },
                                {
                                    "keyword": "test2",
                                    "keyword_info": {},
                                    "keyword_properties": {"keyword_difficulty": 25.5},
                                },
                                {
                                    "keyword": "test3",
                                    "keyword_info": {},
                                    "keyword_properties": {"keyword_difficulty": 25.6},
                                },
                            ]
                        }
                    ]
                }
            ]
        }
        results = extract_keywords(raw, include_difficulty=True)
        assert results[0]["difficulty"] == 25  # 25.4 -> 25
        assert results[1]["difficulty"] == 26  # 25.5 -> 26 (JS round)
        assert results[2]["difficulty"] == 26  # 25.6 -> 26

    def test_difficulty_null_when_missing(self):
        """Test that difficulty is None when keyword_difficulty is missing."""
        raw = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "keyword": "test",
                                    "keyword_info": {},
                                    "keyword_properties": {},
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        results = extract_keywords(raw, include_difficulty=True)
        assert len(results) == 1
        assert results[0]["difficulty"] is None

    def test_keyword_trimming(self):
        """Test that keywords are trimmed of whitespace."""
        raw = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "keyword": "  test keyword  ",
                                    "keyword_info": {},
                                    "keyword_properties": {},
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        results = extract_keywords(raw)
        assert results[0]["keyword"] == "test keyword"

    def test_empty_items_array(self):
        """Test that empty items array returns empty list."""
        raw = {"tasks": [{"result": [{"items": []}]}]}
        results = extract_keywords(raw)
        assert results == []

    def test_empty_fixture(self):
        """Test extraction from empty fixture."""
        fixture_path = (
            Path(__file__).parent.parent.parent
            / "test"
            / "fixtures"
            / "keyword-expansion"
            / "related-empty.json"
        )
        with open(fixture_path) as f:
            raw = json.load(f)

        results = extract_keywords(raw)
        assert results == []

    def test_suggestions_empty_fixture(self):
        """Test extraction from suggestions empty fixture."""
        fixture_path = (
            Path(__file__).parent.parent.parent
            / "test"
            / "fixtures"
            / "keyword-expansion"
            / "suggestions-empty.json"
        )
        with open(fixture_path) as f:
            raw = json.load(f)

        results = extract_keywords(raw)
        assert results == []

    def test_malformed_response(self):
        """Test handling of malformed responses."""
        fixture_path = (
            Path(__file__).parent.parent.parent
            / "test"
            / "fixtures"
            / "keyword-expansion"
            / "malformed-response.json"
        )
        with open(fixture_path) as f:
            raw = json.load(f)

        results = extract_keywords(raw)
        # Should return empty list for malformed data
        assert isinstance(results, list)

    def test_missing_tasks_key(self):
        """Test handling when tasks key is missing."""
        raw = {}
        results = extract_keywords(raw)
        assert results == []

    def test_missing_result_key(self):
        """Test handling when result key is missing."""
        raw = {"tasks": [{}]}
        results = extract_keywords(raw)
        assert results == []

    def test_missing_items_key(self):
        """Test handling when items key is missing."""
        raw = {"tasks": [{"result": [{}]}]}
        results = extract_keywords(raw)
        assert results == []

    def test_empty_tasks_list(self):
        """Test handling when tasks list is empty."""
        raw = {"tasks": []}
        results = extract_keywords(raw)
        assert results == []

    def test_empty_result_list(self):
        """Test handling when result list is empty."""
        raw = {"tasks": [{"result": []}]}
        results = extract_keywords(raw)
        assert results == []

    def test_items_not_array(self):
        """Test handling when items is not an array."""
        raw = {"tasks": [{"result": [{"items": "not an array"}]}]}
        results = extract_keywords(raw)
        assert results == []

    def test_skips_items_without_keyword(self):
        """Test that items without a keyword are skipped."""
        raw = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {"keyword_info": {"search_volume": 100}},
                                {"keyword": "valid", "keyword_info": {}},
                                {"keyword_data": {}},
                            ]
                        }
                    ]
                }
            ]
        }
        results = extract_keywords(raw)
        assert len(results) == 1
        assert results[0]["keyword"] == "valid"

    def test_null_values_in_keyword_info(self):
        """Test that null values in keyword_info are preserved."""
        raw = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "keyword": "test",
                                    "keyword_info": {
                                        "search_volume": None,
                                        "cpc": None,
                                    },
                                    "keyword_properties": {},
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        results = extract_keywords(raw)
        assert results[0]["search_volume"] is None
        assert results[0]["cpc"] is None

    def test_multiple_items(self):
        """Test extraction of multiple items."""
        raw = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "keyword": "keyword1",
                                    "keyword_info": {"search_volume": 100},
                                    "keyword_properties": {},
                                },
                                {
                                    "keyword": "keyword2",
                                    "keyword_info": {"search_volume": 200},
                                    "keyword_properties": {},
                                },
                                {
                                    "keyword": "keyword3",
                                    "keyword_info": {"search_volume": 300},
                                    "keyword_properties": {},
                                },
                            ]
                        }
                    ]
                }
            ]
        }
        results = extract_keywords(raw)
        assert len(results) == 3
        assert results[0]["keyword"] == "keyword1"
        assert results[1]["keyword"] == "keyword2"
        assert results[2]["keyword"] == "keyword3"

    def test_deterministic_ordering(self):
        """Test that extraction preserves item order."""
        raw = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "keyword": "z",
                                    "keyword_info": {},
                                    "keyword_properties": {},
                                },
                                {
                                    "keyword": "a",
                                    "keyword_info": {},
                                    "keyword_properties": {},
                                },
                                {
                                    "keyword": "m",
                                    "keyword_info": {},
                                    "keyword_properties": {},
                                },
                            ]
                        }
                    ]
                }
            ]
        }
        results = extract_keywords(raw)
        assert [r["keyword"] for r in results] == ["z", "a", "m"]
