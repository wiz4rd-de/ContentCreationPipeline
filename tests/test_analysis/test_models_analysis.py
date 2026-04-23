"""Tests for analysis models and their serialization."""

import json
from pathlib import Path

import pytest

from seo_pipeline.models import (
    BriefingCompetitor,
    BriefingData,
    ClaimsOutput,
    ContentTopics,
    EntityProminence,
    PageStructure,
    WdfIdfScore,
)


@pytest.fixture
def golden_dir() -> Path:
    """Return path to golden output directory."""
    return Path(__file__).parent.parent / "golden"


@pytest.fixture
def fixture_dir() -> Path:
    """Return path to briefing-data fixture directory."""
    return (
        Path(__file__).parent.parent.parent
        / "tests"
        / "fixtures"
        / "assemble-briefing-data"
        / "2026-03-09_test-keyword"
    )


# -----------------------------------------------------------------------
# ContentTopics
# -----------------------------------------------------------------------


class TestContentTopics:
    """Tests for ContentTopics model."""

    def test_roundtrip(self, golden_dir):
        golden_file = golden_dir / "analyze-content-topics--default.json"
        with open(golden_file) as f:
            original = json.load(f)

        model = ContentTopics(**original)
        serialized = model.model_dump(mode="json")

        assert serialized == original, (
            f"Roundtrip mismatch for ContentTopics:\n"
            f"Expected keys: {json.dumps(list(original.keys()))}\n"
            f"Got keys: {json.dumps(list(serialized.keys()))}"
        )

    def test_proof_keyword_fields(self, golden_dir):
        golden_file = golden_dir / "analyze-content-topics--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        model = ContentTopics(**data)
        pk = model.proof_keywords[0]
        assert pk.term == "playa"
        assert pk.document_frequency == 3
        assert pk.total_pages == 3
        assert pk.avg_tf == 1
        assert pk.idf_boost == 1.612
        assert pk.idf_score == 4.836

    def test_entity_candidate_fields(self, golden_dir):
        golden_file = golden_dir / "analyze-content-topics--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        model = ContentTopics(**data)
        ec = model.entity_candidates[0]
        assert ec.term == "beliebt"
        assert ec.document_frequency == 3
        assert len(ec.pages) == 3

    def test_section_weights(self, golden_dir):
        golden_file = golden_dir / "analyze-content-topics--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        model = ContentTopics(**data)
        assert len(model.section_weights) == 8
        sw = model.section_weights[0]
        assert sw.heading_cluster == "aktivitaeten und sport"
        assert sw.weight == "high"

    def test_content_format_signals(self, golden_dir):
        golden_file = golden_dir / "analyze-content-topics--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        model = ContentTopics(**data)
        cfs = model.content_format_signals
        assert cfs.pages_with_numbered_lists == 1
        assert cfs.pages_with_faq == 1
        assert cfs.pages_with_tables == 2
        assert cfs.avg_h2_count == 2.7
        assert cfs.dominant_pattern is None

    def test_key_order(self, golden_dir):
        """Verify JSON key order matches golden output."""
        golden_file = golden_dir / "analyze-content-topics--default.json"
        with open(golden_file) as f:
            original = json.load(f)

        model = ContentTopics(**original)
        serialized = json.loads(model.model_dump_json())

        assert list(serialized.keys()) == list(original.keys())
        assert list(serialized["proof_keywords"][0].keys()) == list(
            original["proof_keywords"][0].keys()
        )


# -----------------------------------------------------------------------
# PageStructure
# -----------------------------------------------------------------------


class TestPageStructure:
    """Tests for PageStructure model."""

    def test_roundtrip(self, golden_dir):
        golden_file = golden_dir / "analyze-page-structure--default.json"
        with open(golden_file) as f:
            original = json.load(f)

        model = PageStructure(**original)
        serialized = model.model_dump(mode="json")

        assert serialized == original

    def test_competitor_fields(self, golden_dir):
        golden_file = golden_dir / "analyze-page-structure--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        model = PageStructure(**data)
        assert len(model.competitors) == 3
        c = model.competitors[0]
        assert c.url == "https://alpha.example.com/guide"
        assert c.domain == "alpha.example.com"
        assert c.total_word_count == 201
        assert c.section_count == 6
        assert "faq" in c.detected_modules

    def test_section_fields(self, golden_dir):
        golden_file = golden_dir / "analyze-page-structure--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        model = PageStructure(**data)
        sec = model.competitors[0].sections[0]
        assert sec.heading == ""
        assert sec.level == 0
        assert sec.word_count == 38
        assert sec.has_numbers is True
        assert sec.depth_score == "basic"

    def test_cross_competitor(self, golden_dir):
        golden_file = golden_dir / "analyze-page-structure--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        model = PageStructure(**data)
        cc = model.cross_competitor
        assert cc.common_modules == ["list"]
        assert cc.rare_modules == []
        assert cc.module_frequency["faq"] == 2
        assert cc.avg_word_count == 201
        assert cc.avg_sections == 5

    def test_key_order(self, golden_dir):
        golden_file = golden_dir / "analyze-page-structure--default.json"
        with open(golden_file) as f:
            original = json.load(f)

        model = PageStructure(**original)
        serialized = json.loads(model.model_dump_json())
        assert list(serialized.keys()) == list(original.keys())


# -----------------------------------------------------------------------
# EntityProminence
# -----------------------------------------------------------------------


class TestEntityProminence:
    """Tests for EntityProminence model."""

    def test_roundtrip(self, golden_dir):
        golden_file = golden_dir / "compute-entity-prominence--default.json"
        with open(golden_file) as f:
            original = json.load(f)

        model = EntityProminence(**original)
        serialized = model.model_dump(mode="json", by_alias=True)

        assert serialized == original

    def test_entity_fields(self, golden_dir):
        golden_file = golden_dir / "compute-entity-prominence--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        model = EntityProminence(**data)
        cluster = model.entity_clusters[0]
        assert cluster.category_name == "Aktivitaeten"
        e = cluster.entities[0]
        assert e.entity == "Schnorcheln"
        assert e.prominence == "2/3"
        assert e.prominence_gemini == "8/10"
        assert e.prominence_source == "code"
        assert "schnorcheln" in e.synonyms

    def test_debug_corrections(self, golden_dir):
        golden_file = golden_dir / "compute-entity-prominence--default.json"
        with open(golden_file) as f:
            data = json.load(f)

        model = EntityProminence(**data)
        serialized = model.model_dump(mode="json", by_alias=True)
        assert "_debug" in serialized
        assert len(serialized["_debug"]["corrections"]) == 4

    def test_without_debug(self):
        """EntityProminence without _debug field omits it."""
        data = {
            "entity_clusters": [
                {
                    "category_name": "Test",
                    "entities": [
                        {
                            "entity": "Foo",
                            "prominence": "1/1",
                            "prominence_source": "code",
                            "synonyms": ["foo"],
                        }
                    ],
                }
            ]
        }
        model = EntityProminence(**data)
        serialized = model.model_dump(mode="json", by_alias=True)
        assert "_debug" not in serialized

    def test_fixture_without_prominence_gemini(self, fixture_dir):
        """Entity prominence fixture has no prominence_gemini field."""
        with open(fixture_dir / "entity-prominence.json") as f:
            data = json.load(f)

        model = EntityProminence(**data)
        e = model.entity_clusters[0].entities[0]
        assert e.prominence_gemini is None
        serialized = model.model_dump(mode="json", by_alias=True)
        # Should not include prominence_gemini when not set
        first_entity = serialized["entity_clusters"][0]["entities"][0]
        assert "prominence_gemini" not in first_entity


# -----------------------------------------------------------------------
# ClaimsOutput
# -----------------------------------------------------------------------


class TestClaimsOutput:
    """Tests for ClaimsOutput model."""

    def test_construction(self):
        data = {
            "meta": {
                "draft": "test.md",
                "extracted_at": "2026-01-01T00:00:00.000Z",
                "total_claims": 2,
            },
            "claims": [
                {
                    "id": "c001",
                    "category": "heights_distances",
                    "value": "2.469 Metern",
                    "sentence": "Der Berg ist 2.469 Metern hoch.",
                    "line": 5,
                    "section": "Geographie",
                },
                {
                    "id": "c002",
                    "category": "dates_years",
                    "value": "seit 1962",
                    "sentence": "Das Hotel besteht seit 1962.",
                    "line": 10,
                    "section": "Geschichte",
                },
            ],
        }

        model = ClaimsOutput(**data)
        assert model.meta.total_claims == 2
        assert len(model.claims) == 2
        assert model.claims[0].id == "c001"
        assert model.claims[0].category == "heights_distances"
        assert model.claims[1].section == "Geschichte"

    def test_roundtrip(self):
        data = {
            "meta": {
                "draft": "path/to/draft.md",
                "extracted_at": "2026-01-01T00:00:00.000Z",
                "total_claims": 1,
            },
            "claims": [
                {
                    "id": "c001",
                    "category": "counts",
                    "value": "550 Huetten",
                    "sentence": "Es gibt ueber 550 Huetten.",
                    "line": 3,
                    "section": None,
                },
            ],
        }
        model = ClaimsOutput(**data)
        serialized = model.model_dump(mode="json")
        assert serialized == data

    def test_null_section(self):
        claim_data = {
            "id": "c001",
            "category": "geographic",
            "value": "noerdlich Berlin",
            "sentence": "Der Ort liegt noerdlich Berlin.",
            "line": 1,
        }
        from seo_pipeline.models import Claim

        claim = Claim(**claim_data)
        assert claim.section is None


# -----------------------------------------------------------------------
# WdfIdfScore
# -----------------------------------------------------------------------


class TestWdfIdfScore:
    """Tests for WdfIdfScore model."""

    def test_construction(self):
        data = {
            "meta": {
                "draft": "draft.txt",
                "pages_dir": "pages/",
                "language": "de",
                "threshold": 0.1,
                "competitor_count": 2,
                "idf_source": "reference",
            },
            "terms": [
                {
                    "term": "mallorca",
                    "draft_wdfidf": 0.5,
                    "competitor_avg_wdfidf": 0.3,
                    "delta": 0.2,
                    "signal": "decrease",
                },
                {
                    "term": "strand",
                    "draft_wdfidf": 0.1,
                    "competitor_avg_wdfidf": 0.4,
                    "delta": -0.3,
                    "signal": "increase",
                },
            ],
        }

        model = WdfIdfScore(**data)
        assert model.meta.language == "de"
        assert model.meta.threshold == 0.1
        assert model.meta.idf_source == "reference"
        assert len(model.terms) == 2
        assert model.terms[0].signal == "decrease"
        assert model.terms[1].delta == -0.3

    def test_roundtrip(self):
        data = {
            "meta": {
                "draft": "d.txt",
                "pages_dir": "p/",
                "language": "de",
                "threshold": 0.1,
                "competitor_count": 3,
                "idf_source": "corpus-local",
            },
            "terms": [
                {
                    "term": "test",
                    "draft_wdfidf": 0.0,
                    "competitor_avg_wdfidf": 0.0,
                    "delta": 0.0,
                    "signal": "ok",
                },
            ],
        }
        model = WdfIdfScore(**data)
        serialized = model.model_dump(mode="json")
        assert serialized == data


# -----------------------------------------------------------------------
# BriefingData
# -----------------------------------------------------------------------


class TestBriefingData:
    """Tests for BriefingData model."""

    def test_roundtrip(self, golden_dir):
        """Full roundtrip against the golden briefing data output."""
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            original = json.load(f)

        model = BriefingData(**original)
        serialized = model.model_dump(mode="json")

        assert serialized == original, (
            f"Roundtrip mismatch for BriefingData:\n"
            f"Diff at top level: "
            f"expected keys={list(original.keys())}, "
            f"got keys={list(serialized.keys())}"
        )

    def test_meta_fields(self, golden_dir):
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        model = BriefingData(**data)
        assert model.meta.seed_keyword == "test keyword"
        assert model.meta.date == "2026-03-09"
        assert model.meta.current_year == 2026
        assert model.meta.pipeline_version == "0.2.0"
        assert model.meta.market is None
        assert model.meta.phase1_completed_at == "2026-01-01T00:00:00.000Z"
        assert model.meta.data_sources.location_code == 2276
        assert len(model.meta.data_sources.competitor_urls) == 3

    def test_stats(self, golden_dir):
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        model = BriefingData(**data)
        assert model.stats.total_keywords == 10
        assert model.stats.filtered_keywords == 8
        assert model.stats.total_clusters == 3
        assert model.stats.competitor_count == 3

    def test_keyword_data_flattened(self, golden_dir):
        """keyword_data clusters are flattened summaries, not full KeywordCluster."""
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        model = BriefingData(**data)
        kd = model.keyword_data
        assert kd.total_keywords == 10
        assert kd.filtered_count == 8
        assert len(kd.clusters) == 3
        c = kd.clusters[0]
        assert c.cluster_keyword == "keyword tool"
        assert c.rank == 1
        assert c.total_search_volume == 1800
        assert c.cluster_opportunity == 30

    def test_competitor_alphabetical_keys(self, golden_dir):
        """BriefingData competitors serialize with alphabetically sorted keys."""
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            original = json.load(f)

        model = BriefingData(**original)
        serialized = model.model_dump(mode="json")

        for comp in serialized["serp_data"]["competitors"]:
            keys = list(comp.keys())
            assert keys == sorted(keys), (
                f"Competitor keys not sorted: {keys}"
            )

    def test_serp_features_boolean_flags(self, golden_dir):
        """serp_features uses boolean flags, not nested objects."""
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        model = BriefingData(**data)
        sf = model.serp_data.serp_features
        assert sf.ai_overview is True
        assert sf.featured_snippet is False
        assert sf.people_also_ask is True

    def test_content_analysis_entity_candidates_with_prominence(self, golden_dir):
        """Entity candidates in content_analysis have prominence fields."""
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        model = BriefingData(**data)
        ec = model.content_analysis.entity_candidates[0]
        assert ec.prominence == "3/3"
        assert ec.prominence_source == "code"

    def test_qualitative_all_null(self, golden_dir):
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        model = BriefingData(**data)
        q = model.qualitative
        assert q.entity_clusters is None
        assert q.unique_angles is None
        assert q.content_format_recommendation is None
        assert q.geo_audit is None
        assert q.aio_strategy is None
        assert q.briefing is None

    def test_faq_data(self, golden_dir):
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        model = BriefingData(**data)
        assert model.faq_data.paa_source == "serp"
        assert len(model.faq_data.questions) == 2
        q = model.faq_data.questions[0]
        assert q.priority == "pflicht"
        assert q.question == "Was ist test keyword?"
        assert q.relevance_score == 3

    def test_competitor_with_rating(self, golden_dir):
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        model = BriefingData(**data)
        comp = model.serp_data.competitors[1]
        assert comp.has_rating is True
        assert comp.rating is not None
        assert comp.rating.value == 4.5
        assert comp.rating.votes_count == 100

    def test_competitor_without_rating(self, golden_dir):
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            data = json.load(f)

        model = BriefingData(**data)
        comp = model.serp_data.competitors[0]
        assert comp.has_rating is False
        assert comp.rating is None

    def test_key_order_top_level(self, golden_dir):
        """Verify JSON top-level key order matches golden."""
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            original = json.load(f)

        model = BriefingData(**original)
        serialized = json.loads(model.model_dump_json())
        assert list(serialized.keys()) == list(original.keys())

    def test_key_order_meta(self, golden_dir):
        golden_file = (
            golden_dir / "assemble-briefing-data--2026-03-09_test-keyword.json"
        )
        with open(golden_file) as f:
            original = json.load(f)

        model = BriefingData(**original)
        serialized = json.loads(model.model_dump_json())
        assert list(serialized["meta"].keys()) == list(original["meta"].keys())

    def test_fixture_roundtrip(self, fixture_dir):
        """Roundtrip the briefing-data fixture (not golden) too."""
        with open(fixture_dir / "briefing-data.json") as f:
            original = json.load(f)

        model = BriefingData(**original)
        serialized = model.model_dump(mode="json")
        assert serialized == original


class TestBriefingCompetitorSortedKeys:
    """Focused tests for BriefingCompetitor alphabetical key ordering."""

    def test_sorted_keys_serialization(self):
        comp = BriefingCompetitor(
            cited_in_ai_overview=True,
            description="Test",
            domain="example.com",
            format=None,
            h1="Title",
            has_rating=False,
            headings=[],
            is_featured_snippet=False,
            is_video=False,
            link_count=10,
            meta_description="desc",
            rank=1,
            rank_absolute=1,
            rating=None,
            strengths=None,
            timestamp=None,
            title="Test",
            topics=None,
            unique_angle=None,
            url="https://example.com",
            weaknesses=None,
            word_count=1000,
        )
        serialized = comp.model_dump(mode="json")
        keys = list(serialized.keys())
        assert keys == sorted(keys)


# -----------------------------------------------------------------------
# Import verification
# -----------------------------------------------------------------------


class TestImports:
    """Verify all analysis models are importable from seo_pipeline.models."""

    def test_all_importable(self):
        from seo_pipeline.models import (  # noqa: F401
            BriefingAio,
            BriefingAioReference,
            BriefingCompetitor,
            BriefingCompetitorAnalysis,
            BriefingContentAnalysis,
            BriefingData,
            BriefingDataSources,
            BriefingFaqData,
            BriefingFaqQuestion,
            BriefingHeading,
            BriefingKeywordClusterSummary,
            BriefingKeywordData,
            BriefingMeta,
            BriefingQualitative,
            BriefingRating,
            BriefingSerpData,
            BriefingSerpFeatures,
            BriefingStats,
            Claim,
            ClaimsMeta,
            ClaimsOutput,
            CompetitorPageStructure,
            ContentFormatSignals,
            ContentTopics,
            CrossCompetitorAnalysis,
            Entity,
            EntityCandidate,
            EntityCluster,
            EntityProminence,
            PageStructure,
            PageStructureSection,
            ProminenceCorrection,
            ProminenceDebug,
            ProofKeyword,
            SectionWeight,
            WdfIdfMeta,
            WdfIdfScore,
            WdfIdfTerm,
        )
