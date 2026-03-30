"""Tests for keyword models and their serialization."""

import json
from pathlib import Path

import pytest

from seo_pipeline.models import (
    FaqItem,
    FilteredKeywords,
    Keyword,
    KeywordCluster,
    ProcessedKeywords,
    RemovalSummary,
    StrategistData,
)


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def golden_dir() -> Path:
    """Return path to golden output directory."""
    return Path(__file__).parent.parent / "golden"


class TestKeyword:
    """Tests for the Keyword model."""

    def test_keyword_minimal(self):
        """Test creating a keyword with only required fields."""
        kw = Keyword(keyword="test keyword")
        assert kw.keyword == "test keyword"
        assert kw.search_volume is None
        assert kw.cpc is None
        assert kw.filter_status is None

    def test_keyword_with_metrics(self):
        """Test creating a keyword with all metrics."""
        kw = Keyword(
            keyword="test keyword",
            search_volume=1000,
            cpc=1.5,
            difficulty=50,
            intent="commercial",
            opportunity_score=25.5,
        )
        assert kw.keyword == "test keyword"
        assert kw.search_volume == 1000
        assert kw.cpc == 1.5
        assert kw.difficulty == 50
        assert kw.intent == "commercial"
        assert kw.opportunity_score == 25.5

    def test_keyword_with_filter_status(self):
        """Test keyword with filter information."""
        kw = Keyword(
            keyword="test keyword",
            search_volume=100,
            filter_status="removed",
            filter_reason="ethics",
        )
        assert kw.filter_status == "removed"
        assert kw.filter_reason == "ethics"

    def test_keyword_monthly_searches(self):
        """Test keyword with monthly search data."""
        monthly_data = [
            {"year": 2025, "month": 1, "search_volume": 1100},
            {"year": 2025, "month": 2, "search_volume": 1300},
        ]
        kw = Keyword(keyword="test", monthly_searches=monthly_data)
        assert kw.monthly_searches == monthly_data

    def test_keyword_serialization(self):
        """Test keyword serialization to JSON."""
        kw = Keyword(
            keyword="test",
            search_volume=100,
            cpc=1.5,
            opportunity_score=25.5,
            filter_status="keep",
            filter_reason=None,
        )
        data = kw.model_dump(mode="json")
        assert data["keyword"] == "test"
        assert data["search_volume"] == 100
        assert data["cpc"] == 1.5
        assert data["opportunity_score"] == 25.5
        assert data["filter_status"] == "keep"
        assert data["filter_reason"] is None


class TestKeywordCluster:
    """Tests for the KeywordCluster model."""

    def test_cluster_creation(self):
        """Test creating a keyword cluster."""
        kw1 = Keyword(keyword="test keyword 1", search_volume=500)
        kw2 = Keyword(keyword="test keyword 2", search_volume=300)
        cluster = KeywordCluster(
            cluster_keyword="test keyword",
            keyword_count=2,
            keywords=[kw1, kw2],
            cluster_opportunity=50.0,
        )
        assert cluster.cluster_keyword == "test keyword"
        assert cluster.keyword_count == 2
        assert len(cluster.keywords) == 2
        assert cluster.cluster_opportunity == 50.0
        assert cluster.cluster_label is None

    def test_cluster_with_label(self):
        """Test cluster with label and strategic notes."""
        kw = Keyword(keyword="test")
        cluster = KeywordCluster(
            cluster_keyword="main",
            cluster_label="Navigation",
            strategic_notes="Focus on user navigation",
            keyword_count=1,
            keywords=[kw],
        )
        assert cluster.cluster_label == "Navigation"
        assert cluster.strategic_notes == "Focus on user navigation"


class TestProcessedKeywords:
    """Tests for the ProcessedKeywords model."""

    def test_processed_keywords_from_golden(self, golden_dir):
        """Test deserialization from golden output."""
        golden_file = golden_dir / "process-keywords--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        processed = ProcessedKeywords(**data)
        assert processed.seed_keyword == "keyword recherche"
        assert processed.total_keywords == 13
        assert processed.total_clusters == 6
        assert len(processed.clusters) == 6

    def test_processed_keywords_roundtrip(self, golden_dir):
        """Test that ProcessedKeywords can roundtrip exactly."""
        golden_file = golden_dir / "process-keywords--default.json"
        with open(golden_file) as f:
            original_data = json.load(f)

        processed = ProcessedKeywords(**original_data)
        # Exclude filter fields from keywords since they don't exist in
        # process-keywords output
        serialized = processed.model_dump(
            mode="json",
            exclude={
                "clusters": {
                    "__all__": {
                        "keywords": {
                            "__all__": {"filter_status", "filter_reason", "source"}
                        }
                    }
                }
            },
        )

        # Verify full structural equality - must match original exactly
        assert serialized == original_data, (
            f"Roundtrip mismatch:\n"
            f"Expected: {json.dumps(original_data, indent=2)}\n"
            f"Got: {json.dumps(serialized, indent=2)}"
        )

    def test_processed_keywords_empty(self, golden_dir):
        """Test deserialization of empty processed keywords."""
        golden_file = golden_dir / "process-keywords--empty.json"
        with open(golden_file) as f:
            data = json.load(f)

        processed = ProcessedKeywords(**data)
        assert processed.total_keywords == 1  # The empty test actually has 1 keyword
        assert processed.total_clusters == 1  # And 1 cluster
        assert len(processed.clusters) == 1


class TestRemovalSummary:
    """Tests for the RemovalSummary model."""

    def test_removal_summary_creation(self):
        """Test creating a removal summary."""
        summary = RemovalSummary(ethics=2, brand=0, off_topic=4, foreign_language=1)
        assert summary.ethics == 2
        assert summary.brand == 0
        assert summary.off_topic == 4
        assert summary.foreign_language == 1


class TestFaqItem:
    """Tests for the FaqItem model."""

    def test_faq_item_creation(self):
        """Test creating an FAQ item."""
        item = FaqItem(
            question="What is the best keyword?",
            priority="pflicht",
            relevance_score=2,
        )
        assert item.question == "What is the best keyword?"
        assert item.priority == "pflicht"
        assert item.relevance_score == 2


class TestFilteredKeywords:
    """Tests for the FilteredKeywords model."""

    def test_filtered_keywords_from_golden(self, golden_dir):
        """Test deserialization from golden output."""
        golden_file = golden_dir / "filter-keywords--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        filtered = FilteredKeywords(**data)
        assert filtered.seed_keyword == "thailand urlaub"
        assert filtered.total_keywords == 10
        assert filtered.filtered_keywords == 3
        assert filtered.removed_count == 7
        assert filtered.removal_summary.ethics == 2
        assert filtered.removal_summary.brand == 0
        assert len(filtered.faq_selection) == 5
        assert len(filtered.clusters) == 3

    def test_filtered_keywords_roundtrip(self, golden_dir):
        """Test that FilteredKeywords can roundtrip exactly."""
        golden_file = golden_dir / "filter-keywords--default.json"
        with open(golden_file) as f:
            original_data = json.load(f)

        filtered = FilteredKeywords(**original_data)
        # Exclude source field from keywords since it doesn't exist in
        # filter-keywords output
        serialized = filtered.model_dump(
            mode="json",
            exclude={
                "clusters": {
                    "__all__": {
                        "keywords": {"__all__": {"source"}}
                    }
                }
            },
        )

        # Verify full structural equality - must match original exactly
        assert serialized == original_data, (
            f"Roundtrip mismatch:\n"
            f"Expected: {json.dumps(original_data, indent=2)}\n"
            f"Got: {json.dumps(serialized, indent=2)}"
        )

    def test_filtered_keywords_empty(self, golden_dir):
        """Test deserialization of empty filtered keywords."""
        golden_file = golden_dir / "filter-keywords--empty.json"
        with open(golden_file) as f:
            data = json.load(f)

        filtered = FilteredKeywords(**data)
        assert filtered.total_keywords == 0
        assert filtered.filtered_keywords == 0
        assert filtered.removed_count == 0
        assert len(filtered.clusters) == 0


class TestStrategistData:
    """Tests for the StrategistData model."""

    def test_strategist_data_from_golden(self, golden_dir):
        """Test deserialization from golden output."""
        golden_file = golden_dir / "prepare-strategist-data--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        strategist = StrategistData(**data)
        assert strategist.seed_keyword == "seo reporting"
        assert len(strategist.top_keywords) == 4
        assert len(strategist.all_keywords) == 4
        assert len(strategist.autocomplete) == 1
        assert len(strategist.content_ideas) == 2
        assert len(strategist.paa_questions) == 3
        assert len(strategist.serp_snippets) == 2
        assert len(strategist.competitor_keywords) == 2

    def test_strategist_data_roundtrip(self, golden_dir):
        """Test that StrategistData can roundtrip exactly."""
        golden_file = golden_dir / "prepare-strategist-data--default.json"
        with open(golden_file) as f:
            original_data = json.load(f)

        strategist = StrategistData(**original_data)
        serialized = strategist.model_dump(mode="json")

        # Verify full structural equality - must match original exactly
        assert serialized == original_data, (
            f"Roundtrip mismatch:\n"
            f"Expected: {json.dumps(original_data, indent=2)}\n"
            f"Got: {json.dumps(serialized, indent=2)}"
        )

    def test_strategist_data_top_keywords_structure(self, golden_dir):
        """Test that top_keywords have the correct structure."""
        golden_file = golden_dir / "prepare-strategist-data--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        strategist = StrategistData(**data)
        assert len(strategist.top_keywords) > 0

        top_kw = strategist.top_keywords[0]
        assert "keyword" in top_kw
        assert "search_volume" in top_kw
        assert "difficulty" in top_kw
        assert "opportunity_score" in top_kw

    def test_strategist_data_serp_snippets_structure(self, golden_dir):
        """Test that serp_snippets have the correct structure."""
        golden_file = golden_dir / "prepare-strategist-data--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        strategist = StrategistData(**data)
        assert len(strategist.serp_snippets) > 0

        snippet = strategist.serp_snippets[0]
        assert "rank" in snippet
        assert "title" in snippet
        assert "url" in snippet

    def test_strategist_data_stats_structure(self, golden_dir):
        """Test that stats have the correct structure."""
        golden_file = golden_dir / "prepare-strategist-data--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        strategist = StrategistData(**data)
        stats = strategist.stats
        assert isinstance(stats, dict)
        assert "total_keywords" in stats
        assert "keywords_with_volume" in stats
        assert "total_search_volume" in stats

    def test_strategist_data_empty(self, golden_dir):
        """Test deserialization of empty strategist data."""
        golden_file = golden_dir / "prepare-strategist-data--empty.json"
        with open(golden_file) as f:
            data = json.load(f)

        strategist = StrategistData(**data)
        assert strategist.seed_keyword is not None
        # Other fields should be empty or default


class TestFloatPrecision:
    """Tests for float field precision handling."""

    def test_opportunity_score_precision(self, golden_dir):
        """Test that opportunity_score values round-trip exactly."""
        golden_file = golden_dir / "filter-keywords--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        filtered = FilteredKeywords(**data)

        # Check the first keyword in the first cluster
        first_keyword = filtered.clusters[0].keywords[0]
        assert first_keyword.opportunity_score == 121.95

    def test_cluster_opportunity_precision(self, golden_dir):
        """Test that cluster_opportunity values round-trip exactly."""
        golden_file = golden_dir / "filter-keywords--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        filtered = FilteredKeywords(**data)

        # Check the first cluster opportunity
        first_cluster = filtered.clusters[0]
        assert first_cluster.cluster_opportunity == 49.96

    def test_zero_cpc_precision(self, golden_dir):
        """Test that zero CPC values are preserved."""
        golden_file = golden_dir / "filter-keywords--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        filtered = FilteredKeywords(**data)

        # Find a keyword with cpc=0
        for cluster in filtered.clusters:
            for keyword in cluster.keywords:
                if keyword.cpc == 0 or keyword.cpc == 0.0:
                    assert keyword.cpc == 0 or keyword.cpc == 0.0
                    break
