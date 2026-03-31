"""Tests for filter_keywords module."""

import json
from pathlib import Path

from seo_pipeline.keywords.filter_keywords import (
    _assign_priority,
    _build_blocklist_entries,
    _category_to_reason,
    _filter_keyword,
    _load_blocklist,
    _tokenize_question,
    filter_keywords,
)
from seo_pipeline.utils.text import is_foreign_language

FIXTURES = Path("test/fixtures/filter-keywords")
GOLDEN = Path("tests/golden")


# --- _category_to_reason ---


class TestCategoryToReason:
    """Tests for blocklist category to filter_reason mapping."""

    def test_ethics_maps_to_ethics(self):
        assert _category_to_reason("ethics") == "ethics"

    def test_booking_portals_maps_to_off_topic(self):
        assert _category_to_reason("booking_portals") == "off_topic"

    def test_spam_patterns_maps_to_off_topic(self):
        assert _category_to_reason("spam_patterns") == "off_topic"

    def test_custom_category_maps_to_off_topic(self):
        assert _category_to_reason("custom_category") == "off_topic"


# --- _is_foreign_language ---


class TestIsForeignLanguage:
    """Tests for foreign-language detection."""

    def test_latin_keyword_not_foreign(self):
        assert not is_foreign_language("thailand")
        assert not is_foreign_language("urlaub")
        assert not is_foreign_language("hotel")

    def test_extended_latin_not_foreign(self):
        assert not is_foreign_language("café")
        assert not is_foreign_language("résumé")
        assert not is_foreign_language("naïve")

    def test_latin_with_punctuation_not_foreign(self):
        assert not is_foreign_language("it's")
        assert not is_foreign_language("well-known")
        assert not is_foreign_language("test-case")
        assert not is_foreign_language("word,another")

    def test_digits_not_foreign(self):
        assert not is_foreign_language("2024")
        assert not is_foreign_language("test123")

    def test_thai_is_foreign(self):
        # Thai script (ท่องเที่ยวไทย)
        assert is_foreign_language("ท่องเที่ยวไทย")

    def test_cyrillic_is_foreign(self):
        # Cyrillic (привет)
        assert is_foreign_language("привет")

    def test_arabic_is_foreign(self):
        # Arabic (مرحبا)
        assert is_foreign_language("مرحبا")

    def test_chinese_is_foreign(self):
        # Chinese (你好)
        assert is_foreign_language("你好")


# --- _tokenize_question ---


class TestTokenizeQuestion:
    """Tests for FAQ question tokenization."""

    def test_basic_tokenization(self):
        result = _tokenize_question("How are you today?")
        assert result == ["how", "are", "you", "today"]

    def test_punctuation_removed(self):
        result = _tokenize_question("Thailand? Yes!")
        assert result == ["thailand", "yes"]

    def test_multiple_punctuation(self):
        result = _tokenize_question("What's the cost of holidays?")
        assert result == ["whats", "the", "cost", "of", "holidays"]

    def test_lowercase(self):
        result = _tokenize_question("THAILAND Urlaub")
        assert result == ["thailand", "urlaub"]

    def test_empty_question(self):
        result = _tokenize_question("")
        assert result == []

    def test_accented_characters_preserved(self):
        result = _tokenize_question("Café au lait")
        assert result == ["café", "au", "lait"]


# --- _assign_priority ---


class TestAssignPriority:
    """Tests for FAQ priority tier assignment."""

    def test_empty_list_all_optional(self):
        assert _assign_priority(0, 0) == "optional"

    def test_single_item_is_pflicht(self):
        assert _assign_priority(0, 1) == "pflicht"

    def test_top_30_percent_is_pflicht(self):
        # 5 items: indices 0-1 should be pflicht (0-0.4)
        assert _assign_priority(0, 5) == "pflicht"
        assert _assign_priority(1, 5) == "pflicht"

    def test_30_70_percent_is_empfohlen(self):
        # 5 items: indices 2-3 should be empfohlen (0.4-0.8)
        assert _assign_priority(2, 5) == "empfohlen"
        assert _assign_priority(3, 5) == "empfohlen"

    def test_bottom_30_percent_is_optional(self):
        # 5 items: index 4 should be optional (0.8-1.0)
        assert _assign_priority(4, 5) == "optional"

    def test_boundary_at_30_percent(self):
        # 10 items: index 2 is at 0.2 (pflicht), index 3 is at 0.3 (empfohlen, boundary)
        assert _assign_priority(2, 10) == "pflicht"
        assert _assign_priority(3, 10) == "empfohlen"

    def test_boundary_at_70_percent(self):
        # 10 items: 6 at 0.6 (empfohlen), 7 at 0.7 (optional, boundary)
        assert _assign_priority(6, 10) == "empfohlen"
        assert _assign_priority(7, 10) == "optional"


# --- _build_blocklist_entries ---


class TestBuildBlocklistEntries:
    """Tests for blocklist entry flattening and sorting."""

    def test_single_category_single_term(self):
        blocklist = {"ethics": ["sextourismus"]}
        entries = _build_blocklist_entries(blocklist)
        assert len(entries) == 1
        assert entries[0]["term"] == "sextourismus"
        assert entries[0]["category"] == "ethics"

    def test_multiple_terms_same_category(self):
        blocklist = {"ethics": ["term1", "term2", "term3"]}
        entries = _build_blocklist_entries(blocklist)
        assert len(entries) == 3
        assert all(e["category"] == "ethics" for e in entries)

    def test_lowercase_normalization(self):
        blocklist = {"ethics": ["SexTourismus", "RotLicht"]}
        entries = _build_blocklist_entries(blocklist)
        # Entries are sorted alphabetically, so rotlicht comes before sextourismus
        assert entries[0]["term"] == "rotlicht"
        assert entries[1]["term"] == "sextourismus"

    def test_sorted_by_category_then_term(self):
        blocklist = {
            "spam_patterns": ["zebra"],
            "ethics": ["apple"],
            "booking_portals": ["banana"],
        }
        entries = _build_blocklist_entries(blocklist)
        # Should be sorted: booking_portals:banana, ethics:apple, spam_patterns:zebra
        assert entries[0]["category"] == "booking_portals"
        assert entries[0]["term"] == "banana"
        assert entries[1]["category"] == "ethics"
        assert entries[1]["term"] == "apple"
        assert entries[2]["category"] == "spam_patterns"
        assert entries[2]["term"] == "zebra"


# --- _filter_keyword ---


class TestFilterKeyword:
    """Tests for single keyword filtering."""

    def test_blocklist_ethics_match(self):
        blocklist_entries = [
            {"term": "sextourismus", "category": "ethics"},
        ]
        kw = {"keyword": "sextourismus thailand"}
        result = _filter_keyword(kw, blocklist_entries, [])
        assert result["filter_status"] == "removed"
        assert result["filter_reason"] == "ethics"

    def test_blocklist_booking_portals_match(self):
        blocklist_entries = [
            {"term": "check24", "category": "booking_portals"},
        ]
        kw = {"keyword": "thailand check24"}
        result = _filter_keyword(kw, blocklist_entries, [])
        assert result["filter_status"] == "removed"
        assert result["filter_reason"] == "off_topic"

    def test_brand_match(self):
        blocklist_entries = []
        brand_list = ["booking.com"]
        kw = {"keyword": "thailand booking.com"}
        result = _filter_keyword(kw, blocklist_entries, brand_list)
        assert result["filter_status"] == "removed"
        assert result["filter_reason"] == "brand"

    def test_foreign_language_match(self):
        blocklist_entries = []
        brand_list = []
        kw = {"keyword": "ท่องเที่ยวไทย"}
        result = _filter_keyword(kw, blocklist_entries, brand_list)
        assert result["filter_status"] == "removed"
        assert result["filter_reason"] == "foreign_language"

    def test_keep_keyword(self):
        blocklist_entries = []
        brand_list = []
        kw = {"keyword": "thailand urlaub"}
        result = _filter_keyword(kw, blocklist_entries, brand_list)
        assert result["filter_status"] == "keep"
        assert result["filter_reason"] is None

    def test_first_match_wins(self):
        # If keyword matches both blocklist and brand, blocklist should win
        blocklist_entries = [
            {"term": "thailand", "category": "ethics"},
        ]
        brand_list = ["thailand"]
        kw = {"keyword": "thailand hotel"}
        result = _filter_keyword(kw, blocklist_entries, brand_list)
        # Blocklist is checked first
        assert result["filter_reason"] == "ethics"

    def test_case_insensitive_matching(self):
        blocklist_entries = [
            {"term": "sextourismus", "category": "ethics"},
        ]
        kw = {"keyword": "SeXTourismus Thailand"}
        result = _filter_keyword(kw, blocklist_entries, [])
        assert result["filter_status"] == "removed"
        assert result["filter_reason"] == "ethics"


# --- _load_blocklist ---


class TestLoadBlocklist:
    """Tests for blocklist loading."""

    def test_load_custom_blocklist(self):
        custom_path = FIXTURES / "custom-blocklist.json"
        blocklist = _load_blocklist(str(custom_path))
        assert "ethics" in blocklist
        assert "gambling" in blocklist["ethics"]
        assert "casino" in blocklist["ethics"]

    def test_load_default_blocklist(self):
        # Test by not passing a path (uses default)
        blocklist = _load_blocklist()
        assert "ethics" in blocklist
        assert "booking_portals" in blocklist
        assert "spam_patterns" in blocklist
        assert "sextourismus" in blocklist["ethics"]
        assert "check24" in blocklist["booking_portals"]
        assert "torrent" in blocklist["spam_patterns"]


# --- filter_keywords (integration) ---


class TestFilterKeywords:
    """Integration tests for the full filter_keywords pipeline."""

    def test_golden_default_fixture(self):
        """Test against the default golden file."""
        keywords_path = FIXTURES / "keywords-processed.json"
        serp_path = FIXTURES / "serp-processed.json"
        golden_path = GOLDEN / "filter-keywords--default.json"

        with open(keywords_path) as f:
            keywords_data = json.load(f)
        with open(serp_path) as f:
            serp_data = json.load(f)
        with open(golden_path) as f:
            expected = json.load(f)

        result = filter_keywords(
            keywords_data,
            serp_data,
            seed_keyword="thailand urlaub",
            blocklist_path=None,
            brands=None,
        )

        assert result == expected

    def test_golden_empty_fixture(self):
        """Test against the empty golden file."""
        keywords_path = FIXTURES / "keywords-processed-empty.json"
        serp_path = FIXTURES / "serp-processed-empty.json"
        golden_path = GOLDEN / "filter-keywords--empty.json"

        with open(keywords_path) as f:
            keywords_data = json.load(f)
        with open(serp_path) as f:
            serp_data = json.load(f)
        with open(golden_path) as f:
            expected = json.load(f)

        result = filter_keywords(
            keywords_data,
            serp_data,
            seed_keyword="empty test",
            blocklist_path=None,
            brands=None,
        )

        assert result == expected

    def test_custom_blocklist(self):
        """Test with a custom blocklist."""
        keywords_path = FIXTURES / "keywords-processed.json"
        serp_path = FIXTURES / "serp-processed.json"
        custom_blocklist = FIXTURES / "custom-blocklist.json"

        with open(keywords_path) as f:
            keywords_data = json.load(f)
        with open(serp_path) as f:
            serp_data = json.load(f)

        result = filter_keywords(
            keywords_data,
            serp_data,
            seed_keyword="thailand urlaub",
            blocklist_path=str(custom_blocklist),
            brands=None,
        )

        # Custom blocklist has "gambling" and "casino" which aren't in default
        # Check that the result structure is correct
        assert "seed_keyword" in result
        assert "total_keywords" in result
        assert "removal_summary" in result
        assert result["seed_keyword"] == "thailand urlaub"

    def test_with_brands_filter(self):
        """Test brand filtering."""
        keywords_data = {
            "clusters": [
                {
                    "cluster_keyword": "test",
                    "cluster_label": None,
                    "strategic_notes": None,
                    "keyword_count": 3,
                    "keywords": [
                        {"keyword": "test product"},
                        {"keyword": "test nike shoe"},
                        {"keyword": "test shoe"},
                    ],
                    "cluster_opportunity": 0,
                }
            ]
        }
        serp_data = {"serp_features": {"people_also_ask": []}}

        result = filter_keywords(
            keywords_data,
            serp_data,
            seed_keyword="test",
            blocklist_path=None,
            brands="nike,adidas",
        )

        # Find the keywords that passed/failed
        keywords = result["clusters"][0]["keywords"]
        assert keywords[0]["filter_status"] == "keep"  # "test product"
        # "test nike shoe" (nike is a brand)
        assert keywords[1]["filter_status"] == "removed"
        assert keywords[1]["filter_reason"] == "brand"
        assert keywords[2]["filter_status"] == "keep"  # "test shoe"

    def test_removal_summary_counts(self):
        """Test that removal_summary counts are accurate."""
        keywords_data = {
            "clusters": [
                {
                    "cluster_keyword": "test",
                    "cluster_label": None,
                    "strategic_notes": None,
                    "keyword_count": 4,
                    "keywords": [
                        {"keyword": "test"},
                        {"keyword": "test sextourismus"},  # ethics
                        {"keyword": "test check24"},  # off_topic
                        {"keyword": "ท่องเที่ยวไทย"},  # foreign_language
                    ],
                    "cluster_opportunity": 0,
                }
            ]
        }
        serp_data = {"serp_features": {"people_also_ask": []}}

        result = filter_keywords(
            keywords_data,
            serp_data,
            seed_keyword="test",
            blocklist_path=None,
            brands=None,
        )

        summary = result["removal_summary"]
        assert summary["ethics"] == 1
        assert summary["brand"] == 0
        assert summary["off_topic"] == 1
        assert summary["foreign_language"] == 1

    def test_faq_scoring_and_sorting(self):
        """Test FAQ scoring and prioritization."""
        keywords_data = {
            "clusters": [
                {
                    "cluster_keyword": "thailand",
                    "cluster_label": None,
                    "strategic_notes": None,
                    "keyword_count": 2,
                    "keywords": [
                        {"keyword": "thailand weather"},
                        {"keyword": "thailand cost"},
                    ],
                    "cluster_opportunity": 0,
                }
            ]
        }
        serp_data = {
            "serp_features": {
                "people_also_ask": [
                    "What is the weather in Thailand?",
                    "How much does Thailand cost?",
                    "Where is Thailand?",
                ]
            }
        }

        result = filter_keywords(
            keywords_data,
            serp_data,
            seed_keyword="thailand",
            blocklist_path=None,
            brands=None,
        )

        faq = result["faq_selection"]
        assert len(faq) == 3
        # Top questions should have higher relevance scores
        assert faq[0]["relevance_score"] >= faq[1]["relevance_score"]

    def test_empty_paa_questions(self):
        """Test handling of empty PAA list."""
        keywords_data = {
            "clusters": [
                {
                    "cluster_keyword": "test",
                    "cluster_label": None,
                    "strategic_notes": None,
                    "keyword_count": 1,
                    "keywords": [{"keyword": "test"}],
                    "cluster_opportunity": 0,
                }
            ]
        }
        serp_data = {"serp_features": {"people_also_ask": []}}

        result = filter_keywords(
            keywords_data,
            serp_data,
            seed_keyword="test",
            blocklist_path=None,
            brands=None,
        )

        assert result["faq_selection"] == []

    def test_seed_keyword_stripped(self):
        """Test that seed keyword is trimmed."""
        keywords_data = {"clusters": []}
        serp_data = {"serp_features": {"people_also_ask": []}}

        result = filter_keywords(
            keywords_data,
            serp_data,
            seed_keyword="  test  ",
            blocklist_path=None,
            brands=None,
        )

        assert result["seed_keyword"] == "test"

    def test_no_clusters_returns_valid_output(self):
        """Test handling of missing clusters key."""
        keywords_data = {}  # No clusters key
        serp_data = {"serp_features": {"people_also_ask": []}}

        result = filter_keywords(
            keywords_data,
            serp_data,
            seed_keyword="test",
            blocklist_path=None,
            brands=None,
        )

        assert result["total_keywords"] == 0
        assert result["filtered_keywords"] == 0
        assert result["removed_count"] == 0
        assert result["clusters"] == []
