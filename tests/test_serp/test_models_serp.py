"""Tests for SERP models and their serialization."""

import json
from pathlib import Path

import pytest

from seo_pipeline.models import (
    AiOverview,
    AiOverviewReference,
    CommercialSignals,
    CompetitorsData,
    FeaturedSnippet,
    KnowledgeGraph,
    LocalSignals,
    PaaQuestion,
    Rating,
    SerpCompetitor,
    SerpFeatures,
    SerpProcessed,
)


@pytest.fixture
def golden_dir() -> Path:
    """Return path to golden output directory."""
    return Path(__file__).parent.parent / "golden"


# Fields present in assemble-competitors but absent in process-serp output
_EXTENDED_COMPETITOR_FIELDS = {
    "word_count",
    "h1",
    "headings",
    "link_count",
    "meta_description",
    "format",
    "topics",
    "unique_angle",
    "strengths",
    "weaknesses",
}


class TestAiOverviewReference:
    """Tests for the AiOverviewReference model."""

    def test_full_reference(self):
        ref = AiOverviewReference(
            domain="example.com",
            url="https://example.com/page",
            title="Example",
        )
        assert ref.domain == "example.com"
        assert ref.url == "https://example.com/page"
        assert ref.title == "Example"

    def test_nullable_fields(self):
        ref = AiOverviewReference()
        assert ref.domain is None
        assert ref.url is None
        assert ref.title is None


class TestAiOverview:
    """Tests for the AiOverview model."""

    def test_present_with_data(self):
        aio = AiOverview(
            present=True,
            title="Test Title",
            text="Some text",
            references=[
                AiOverviewReference(
                    domain="example.com",
                    url="https://example.com",
                    title="Example",
                )
            ],
            references_count=1,
        )
        assert aio.present is True
        assert aio.title == "Test Title"
        assert len(aio.references) == 1
        assert aio.references_count == 1

    def test_not_present(self):
        aio = AiOverview(present=False)
        assert aio.present is False
        assert aio.title is None
        assert aio.text is None
        assert aio.references == []
        assert aio.references_count == 0

    def test_present_false_pattern(self):
        """Handle the { "present": false } minimal pattern."""
        data = {"present": False}
        aio = AiOverview(**data)
        assert aio.present is False
        assert aio.references == []


class TestFeaturedSnippet:
    """Tests for the FeaturedSnippet model."""

    def test_present_false(self):
        data = {"present": False}
        fs = FeaturedSnippet(**data)
        assert fs.present is False
        assert fs.format is None
        assert fs.source_domain is None

    def test_present_true(self):
        fs = FeaturedSnippet(
            present=True,
            format="paragraph",
            source_domain="example.com",
            source_url="https://example.com/page",
        )
        assert fs.present is True
        assert fs.format == "paragraph"


class TestPaaQuestion:
    """Tests for the PaaQuestion model."""

    def test_with_answer(self):
        paa = PaaQuestion(
            question="What is SEO?",
            answer="Search engine optimization.",
            url="https://example.com",
            domain="example.com",
        )
        assert paa.question == "What is SEO?"
        assert paa.answer == "Search engine optimization."

    def test_without_answer(self):
        paa = PaaQuestion(question="How does SEO work?")
        assert paa.answer is None
        assert paa.url is None
        assert paa.domain is None


class TestKnowledgeGraph:
    """Tests for the KnowledgeGraph model."""

    def test_present_false(self):
        kg = KnowledgeGraph(**{"present": False})
        assert kg.present is False
        assert kg.title is None
        assert kg.description is None


class TestCommercialSignals:
    """Tests for the CommercialSignals model."""

    def test_all_false(self):
        cs = CommercialSignals(
            paid_ads_present=False,
            shopping_present=False,
            commercial_units_present=False,
            popular_products_present=False,
        )
        assert cs.paid_ads_present is False


class TestLocalSignals:
    """Tests for the LocalSignals model."""

    def test_all_false(self):
        ls = LocalSignals(
            local_pack_present=False,
            map_present=False,
            hotels_pack_present=False,
        )
        assert ls.local_pack_present is False


class TestSerpFeatures:
    """Tests for the SerpFeatures model."""

    def test_empty(self):
        """SerpFeatures can be constructed from empty dict."""
        sf = SerpFeatures()
        assert sf.ai_overview is None
        assert sf.people_also_ask == []
        assert sf.related_searches == []
        assert sf.other_features_present == []

    def test_from_empty_dict(self):
        sf = SerpFeatures(**{})
        assert sf.ai_overview is None


class TestRating:
    """Tests for the Rating model."""

    def test_with_values(self):
        r = Rating(value=4.5, votes_count=100, rating_max=5)
        assert r.value == 4.5
        assert r.votes_count == 100
        assert r.rating_max == 5

    def test_nullable(self):
        r = Rating()
        assert r.value is None
        assert r.votes_count is None
        assert r.rating_max is None

    def test_null_rating_serialization(self):
        """Rating with null value serializes correctly."""
        r = Rating(value=None, votes_count=None, rating_max=None)
        data = r.model_dump(mode="json")
        assert data["value"] is None
        assert data["votes_count"] is None

    def test_non_null_rating_roundtrip(self):
        """Rating with real values roundtrips correctly."""
        original = {"value": 4.5, "votes_count": 100, "rating_max": 5}
        r = Rating(**original)
        assert r.model_dump(mode="json") == original


class TestSerpCompetitor:
    """Tests for the SerpCompetitor model."""

    def test_minimal(self):
        comp = SerpCompetitor(
            rank=1,
            rank_absolute=1,
            url="https://example.com",
            domain="example.com",
            title="Example",
            is_featured_snippet=False,
            is_video=False,
            has_rating=False,
            cited_in_ai_overview=False,
        )
        assert comp.rank == 1
        assert comp.rating is None
        assert comp.timestamp is None
        assert comp.word_count is None
        assert comp.format is None

    def test_with_rating(self):
        comp = SerpCompetitor(
            rank=1,
            rank_absolute=1,
            url="https://example.com",
            domain="example.com",
            title="Example",
            is_featured_snippet=False,
            is_video=False,
            has_rating=True,
            rating=Rating(value=4.5, votes_count=100, rating_max=5),
            cited_in_ai_overview=True,
        )
        assert comp.has_rating is True
        assert comp.rating.value == 4.5

    def test_null_rating_field(self):
        """Competitor with rating=null (process-serp pattern)."""
        data = {
            "rank": 1,
            "rank_absolute": 1,
            "url": "https://example.com",
            "domain": "example.com",
            "title": "Example",
            "description": "Desc",
            "is_featured_snippet": False,
            "is_video": False,
            "has_rating": False,
            "rating": None,
            "timestamp": None,
            "cited_in_ai_overview": False,
        }
        comp = SerpCompetitor(**data)
        assert comp.rating is None
        assert comp.has_rating is False


class TestSerpProcessedRoundtrip:
    """Roundtrip serialization tests for SerpProcessed against golden outputs."""

    @pytest.mark.parametrize(
        "golden_name",
        [
            "process-serp--serp-with-aio",
            "process-serp--serp-no-aio-no-paa",
            "process-serp--serp-aio-encoding-artifacts",
            "process-serp--serp-aio-no-text",
            "process-serp--serp-paa-no-expanded",
        ],
    )
    def test_roundtrip(self, golden_dir, golden_name):
        """Test that SerpProcessed roundtrips to match golden output exactly."""
        golden_file = golden_dir / f"{golden_name}.json"
        with open(golden_file) as f:
            original_data = json.load(f)

        processed = SerpProcessed(**original_data)
        serialized = processed.model_dump(
            mode="json",
            exclude={
                "competitors": {
                    "__all__": _EXTENDED_COMPETITOR_FIELDS
                }
            },
        )

        assert serialized == original_data, (
            f"Roundtrip mismatch for {golden_name}:\n"
            f"Expected: {json.dumps(original_data, indent=2)}\n"
            f"Got: {json.dumps(serialized, indent=2)}"
        )

    def test_serp_with_aio_fields(self, golden_dir):
        """Verify specific fields in the serp-with-aio golden output."""
        golden_file = golden_dir / "process-serp--serp-with-aio.json"
        with open(golden_file) as f:
            data = json.load(f)

        processed = SerpProcessed(**data)
        assert processed.target_keyword == "best seo tools"
        assert processed.se_results_count == 500000
        assert processed.location_code == 2840
        assert processed.language_code == "en"
        assert "ai_overview" in processed.item_types_present

        aio = processed.serp_features.ai_overview
        assert aio.present is True
        assert aio.title == "Best SEO Tools for 2026"
        assert aio.references_count == 3
        assert len(aio.references) == 3

        assert len(processed.competitors) == 2
        assert processed.competitors[0].rank == 1
        assert processed.competitors[0].cited_in_ai_overview is True

    def test_serp_no_aio(self, golden_dir):
        """Verify absent AI overview pattern."""
        golden_file = golden_dir / "process-serp--serp-no-aio-no-paa.json"
        with open(golden_file) as f:
            data = json.load(f)

        processed = SerpProcessed(**data)
        assert processed.serp_features.ai_overview.present is False
        assert processed.serp_features.ai_overview.references == []
        assert processed.serp_features.ai_overview.references_count == 0
        assert processed.serp_features.people_also_ask == []

    def test_paa_unexpanded(self, golden_dir):
        """Verify PAA with null answers (unexpanded)."""
        golden_file = golden_dir / "process-serp--serp-paa-no-expanded.json"
        with open(golden_file) as f:
            data = json.load(f)

        processed = SerpProcessed(**data)
        paa = processed.serp_features.people_also_ask
        assert len(paa) == 2
        assert paa[0].question == "What is SEO?"
        assert paa[0].answer is None
        assert paa[0].url is None

    def test_null_rating_roundtrip(self, golden_dir):
        """Verify competitors with null rating roundtrip correctly."""
        golden_file = golden_dir / "process-serp--serp-with-aio.json"
        with open(golden_file) as f:
            data = json.load(f)

        processed = SerpProcessed(**data)
        for comp in processed.competitors:
            assert comp.has_rating is False
            assert comp.rating is None

        serialized = processed.model_dump(
            mode="json",
            exclude={
                "competitors": {
                    "__all__": _EXTENDED_COMPETITOR_FIELDS
                }
            },
        )
        for i, comp_data in enumerate(serialized["competitors"]):
            assert comp_data["rating"] is None
            assert comp_data["has_rating"] is False
            assert comp_data == data["competitors"][i]


class TestCompetitorsDataRoundtrip:
    """Roundtrip serialization tests for CompetitorsData."""

    def test_roundtrip(self, golden_dir):
        """Test that CompetitorsData roundtrips to match golden output."""
        golden_file = (
            golden_dir / "assemble-competitors--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            original_data = json.load(f)

        competitors_data = CompetitorsData(**original_data)
        serialized = competitors_data.model_dump(mode="json")

        assert serialized == original_data, (
            f"Roundtrip mismatch for CompetitorsData:\n"
            f"Expected: {json.dumps(original_data, indent=2)}\n"
            f"Got: {json.dumps(serialized, indent=2)}"
        )

    def test_competitors_data_fields(self, golden_dir):
        """Verify specific fields in competitors golden output."""
        golden_file = (
            golden_dir / "assemble-competitors--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        cd = CompetitorsData(**data)
        assert cd.target_keyword == "test keyword"
        assert cd.date == "2026-03-09"
        assert cd.common_themes is None
        assert cd.content_gaps is None
        assert cd.opportunities is None
        assert len(cd.competitors) == 3

    def test_competitor_with_rating(self, golden_dir):
        """Verify competitor with non-null rating."""
        golden_file = (
            golden_dir / "assemble-competitors--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        cd = CompetitorsData(**data)
        # Second competitor has rating
        comp = cd.competitors[1]
        assert comp.has_rating is True
        assert comp.rating is not None
        assert comp.rating.value == 4.5
        assert comp.rating.votes_count == 100
        assert comp.rating.rating_max == 5

    def test_competitor_without_rating(self, golden_dir):
        """Verify competitor with null rating."""
        golden_file = (
            golden_dir / "assemble-competitors--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        cd = CompetitorsData(**data)
        comp = cd.competitors[0]
        assert comp.has_rating is False
        assert comp.rating is None

    def test_extended_fields_present(self, golden_dir):
        """Verify extended competitor fields are populated."""
        golden_file = (
            golden_dir / "assemble-competitors--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        cd = CompetitorsData(**data)
        comp = cd.competitors[0]
        # Extended fields should be None (null in fixture)
        assert comp.word_count is None
        assert comp.h1 is None
        assert comp.headings is None
        assert comp.format is None
        assert comp.topics is None

    def test_timestamp_is_string(self, golden_dir):
        """Verify timestamp is modeled as str, not datetime."""
        golden_file = (
            golden_dir / "assemble-competitors--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        cd = CompetitorsData(**data)
        # First competitor has timestamp "2024-01-15"
        comp = cd.competitors[0]
        assert comp.timestamp == "2024-01-15"
        assert isinstance(comp.timestamp, str)

        # Third competitor has null timestamp
        comp3 = cd.competitors[2]
        assert comp3.timestamp is None
