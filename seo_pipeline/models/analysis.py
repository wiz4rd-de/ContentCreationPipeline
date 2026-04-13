"""Data models for analysis modules in the SEO Pipeline.

Covers: content topics, page structure, entity prominence, claims extraction,
WDF*IDF scoring, and the top-level BriefingData aggregation.
"""

from __future__ import annotations

from pydantic import Field, model_serializer, model_validator

from seo_pipeline.models.common import PipelineBaseModel
from seo_pipeline.models.llm_responses import (
    QualAioStrategy,
    QualContentFormat,
    QualEntityCluster,
    QualGeoAudit,
    QualUniqueAngle,
)

# ---------------------------------------------------------------------------
# Content Topics group
# ---------------------------------------------------------------------------


class ProofKeyword(PipelineBaseModel):
    """A proof keyword with TF-IDF metrics.

    Field order matches golden output: term, document_frequency, total_pages,
    avg_tf, then optional idf_boost and idf_score (present in full analysis,
    absent in briefing summary).
    """

    term: str
    document_frequency: int
    total_pages: int
    avg_tf: float
    idf_boost: float | None = Field(default=None)
    idf_score: float | None = Field(default=None)

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        full = handler(self)
        return {k: v for k, v in full.items() if k in self.model_fields_set}


class EntityCandidate(PipelineBaseModel):
    """An entity candidate extracted from competitor content.

    In content-topics output: term, document_frequency, pages.
    In briefing content_analysis: adds prominence and prominence_source.
    """

    term: str
    document_frequency: int
    pages: list[str]
    prominence: str | None = Field(default=None)
    prominence_source: str | None = Field(default=None)

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        full = handler(self)
        return {k: v for k, v in full.items() if k in self.model_fields_set}


class SectionWeight(PipelineBaseModel):
    """Weight and occurrence data for a heading cluster."""

    heading_cluster: str
    sample_headings: list[str]
    occurrence: int
    avg_word_count: int | float
    avg_content_percentage: float
    weight: str


class ContentFormatSignals(PipelineBaseModel):
    """Content format signals aggregated across competitors."""

    pages_with_numbered_lists: int
    pages_with_faq: int
    pages_with_tables: int
    avg_h2_count: float
    dominant_pattern: str | None = Field(default=None)


class ContentTopics(PipelineBaseModel):
    """Top-level output of analyze-content-topics."""

    proof_keywords: list[ProofKeyword]
    entity_candidates: list[EntityCandidate]
    section_weights: list[SectionWeight]
    content_format_signals: ContentFormatSignals


# ---------------------------------------------------------------------------
# Page Structure group
# ---------------------------------------------------------------------------


class PageStructureSection(PipelineBaseModel):
    """A section within a competitor's page structure."""

    heading: str
    level: int
    word_count: int
    sentence_count: int
    has_numbers: bool
    has_lists: bool
    depth_score: str


class CompetitorPageStructure(PipelineBaseModel):
    """Page structure analysis for a single competitor."""

    url: str
    domain: str
    total_word_count: int
    section_count: int
    detected_modules: list[str]
    sections: list[PageStructureSection]


class CrossCompetitorAnalysis(PipelineBaseModel):
    """Cross-competitor module analysis."""

    common_modules: list[str]
    rare_modules: list[str]
    module_frequency: dict[str, int]
    avg_word_count: int | float
    avg_sections: int | float


class PageStructure(PipelineBaseModel):
    """Top-level output of analyze-page-structure."""

    competitors: list[CompetitorPageStructure]
    cross_competitor: CrossCompetitorAnalysis


# ---------------------------------------------------------------------------
# Entity Prominence group
# ---------------------------------------------------------------------------


class Entity(PipelineBaseModel):
    """An entity with prominence data."""

    entity: str
    prominence: str
    prominence_gemini: str | None = Field(default=None)
    prominence_source: str
    synonyms: list[str]

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        full = handler(self)
        return {k: v for k, v in full.items() if k in self.model_fields_set}


class EntityCluster(PipelineBaseModel):
    """A cluster of entities under a category."""

    category_name: str
    entities: list[Entity]


class ProminenceCorrection(PipelineBaseModel):
    """Debug record for a prominence correction."""

    entity: str
    category: str
    gemini: str
    code: str
    delta: int


class ProminenceDebug(PipelineBaseModel):
    """Debug data for entity prominence computation."""

    corrections: list[ProminenceCorrection]


class EntityProminence(PipelineBaseModel):
    """Top-level output of compute-entity-prominence."""

    entity_clusters: list[EntityCluster]
    debug: ProminenceDebug | None = Field(default=None, alias="_debug")

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        full = handler(self)
        result = {"entity_clusters": full["entity_clusters"]}
        if "debug" in self.model_fields_set:
            result["_debug"] = full.get("_debug", full.get("debug"))
        return result


# ---------------------------------------------------------------------------
# Claims group
# ---------------------------------------------------------------------------


class Claim(PipelineBaseModel):
    """A single extracted factual claim."""

    id: str
    category: str
    value: str
    sentence: str
    line: int
    section: str | None = Field(default=None)


class ClaimsMeta(PipelineBaseModel):
    """Metadata for claims extraction."""

    draft: str
    extracted_at: str
    total_claims: int


class ClaimsOutput(PipelineBaseModel):
    """Top-level output of extract-claims."""

    meta: ClaimsMeta
    claims: list[Claim]


# ---------------------------------------------------------------------------
# Fact-check group
# ---------------------------------------------------------------------------


class VerifiedClaim(PipelineBaseModel):
    """A claim that has been fact-checked against web sources."""

    id: str
    category: str
    value: str
    sentence: str
    line: int
    section: str | None = Field(default=None)
    verdict: str  # "correct" | "incorrect" | "uncertain" | "unverifiable"
    corrected_value: str | None = Field(default=None)
    sources: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None)


class FactCheckMeta(PipelineBaseModel):
    """Metadata for the fact-check pipeline run."""

    draft: str
    checked_at: str
    total_claims_extracted: int
    total_claims_supplemented: int
    total_claims_checked: int
    corrections_applied: int


class FactCheckOutput(PipelineBaseModel):
    """Top-level output of the fact-check pipeline."""

    meta: FactCheckMeta
    verified_claims: list[VerifiedClaim]


# ---------------------------------------------------------------------------
# WDF*IDF group
# ---------------------------------------------------------------------------


class WdfIdfTerm(PipelineBaseModel):
    """A single term's WDF*IDF scores."""

    term: str
    draft_wdfidf: float
    competitor_avg_wdfidf: float
    delta: float
    signal: str


class WdfIdfMeta(PipelineBaseModel):
    """Metadata for WDF*IDF scoring."""

    draft: str
    pages_dir: str
    language: str
    threshold: float
    competitor_count: int
    idf_source: str


class WdfIdfScore(PipelineBaseModel):
    """Top-level output of score-draft-wdfidf."""

    meta: WdfIdfMeta
    terms: list[WdfIdfTerm]


# ---------------------------------------------------------------------------
# Briefing Data group
# ---------------------------------------------------------------------------


class BriefingDataSources(PipelineBaseModel):
    """Data sources metadata within briefing meta."""

    competitor_urls: list[str]
    location_code: int


class BriefingMeta(PipelineBaseModel):
    """Metadata for the briefing data assembly."""

    seed_keyword: str
    date: str
    current_year: int
    pipeline_version: str
    market: str | None = Field(default=None)
    language: str | None = Field(default=None)
    user_domain: str | None = Field(default=None)
    business_context: str | None = Field(default=None)
    phase1_completed_at: str
    data_sources: BriefingDataSources


class BriefingStats(PipelineBaseModel):
    """Summary statistics for the briefing."""

    total_keywords: int
    filtered_keywords: int
    total_clusters: int
    competitor_count: int


class BriefingKeywordClusterSummary(PipelineBaseModel):
    """Flattened cluster summary in briefing keyword_data (no individual keywords)."""

    cluster_keyword: str
    cluster_label: str | None = Field(default=None)
    cluster_opportunity: float | int
    keyword_count: int
    rank: int
    total_search_volume: int | float


class BriefingKeywordData(PipelineBaseModel):
    """Keyword data section in BriefingData (flattened summaries)."""

    clusters: list[BriefingKeywordClusterSummary]
    total_keywords: int
    filtered_count: int
    removal_summary: dict[str, int]


class BriefingSerpFeatures(PipelineBaseModel):
    """Boolean-flag SERP features for briefing data.

    Unlike the full SerpFeatures model which has nested objects, briefing
    uses flat boolean flags.
    """

    ai_overview: bool
    featured_snippet: bool
    people_also_ask: bool
    people_also_search: bool
    related_searches: bool
    discussions_and_forums: bool
    video: bool
    top_stories: bool
    knowledge_graph: bool
    commercial_signals: bool
    local_signals: bool
    other_features_present: bool


class BriefingAioReference(PipelineBaseModel):
    """AI Overview reference in briefing serp_data."""

    domain: str
    title: str
    url: str


class BriefingAio(PipelineBaseModel):
    """AI Overview section in briefing serp_data."""

    present: bool
    references: list[BriefingAioReference]
    references_count: int
    text: str | None = Field(default=None)
    title: str | None = Field(default=None)


class BriefingHeading(PipelineBaseModel):
    """Heading in briefing competitor data."""

    level: int
    text: str


class BriefingRating(PipelineBaseModel):
    """Rating in briefing competitor data."""

    rating_max: float | int
    value: float
    votes_count: int


class BriefingCompetitor(PipelineBaseModel):
    """Competitor in briefing serp_data.

    Fields are declared in alphabetical order to match golden output.
    The model_serializer ensures keys are emitted in alphabetical order.
    """

    cited_in_ai_overview: bool
    description: str | None = Field(default=None)
    domain: str
    format: str | None = Field(default=None)
    h1: str | None = Field(default=None)
    has_rating: bool
    headings: list[BriefingHeading] = Field(default_factory=list)
    is_featured_snippet: bool
    is_video: bool
    link_count: int | None = Field(default=None)
    meta_description: str | None = Field(default=None)
    rank: int
    rank_absolute: int
    rating: BriefingRating | None = Field(default=None)
    strengths: str | None = Field(default=None)
    timestamp: str | None = Field(default=None)
    title: str
    topics: str | None = Field(default=None)
    unique_angle: str | None = Field(default=None)
    url: str
    weaknesses: str | None = Field(default=None)
    word_count: int | None = Field(default=None)

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """Emit keys in alphabetical order."""
        full = handler(self)
        return dict(sorted(full.items()))


class BriefingSerpData(PipelineBaseModel):
    """SERP data section in BriefingData."""

    competitors: list[BriefingCompetitor]
    serp_features: BriefingSerpFeatures
    aio: BriefingAio


class BriefingContentAnalysis(PipelineBaseModel):
    """Content analysis section in BriefingData.

    Uses ProofKeyword (without idf_boost/idf_score) and EntityCandidate
    (with prominence fields).
    """

    proof_keywords: list[ProofKeyword]
    entity_candidates: list[EntityCandidate]
    section_weights: list[SectionWeight]
    content_format_signals: ContentFormatSignals


class BriefingCompetitorAnalysis(PipelineBaseModel):
    """Competitor analysis section in BriefingData."""

    page_structures: list[CompetitorPageStructure]
    common_modules: list[str]
    rare_modules: list[str]
    avg_word_count: int | float


class BriefingFaqQuestion(PipelineBaseModel):
    """FAQ question in briefing faq_data."""

    priority: str
    question: str
    relevance_score: int


class BriefingFaqData(PipelineBaseModel):
    """FAQ data section in BriefingData."""

    questions: list[BriefingFaqQuestion]
    paa_source: str


class BriefingQualitative(PipelineBaseModel):
    """Qualitative analysis section (all nullable, populated by LLM).

    Field types match ``QualitativeResponse`` so that merge_qualitative can
    write structured LLM output into briefing-data.json and it round-trips
    through ``BriefingData.model_validate()`` without loss.
    """

    entity_clusters: list[QualEntityCluster] | None = Field(default=None)
    unique_angles: list[QualUniqueAngle] | None = Field(default=None)
    content_format_recommendation: QualContentFormat | None = Field(default=None)
    geo_audit: QualGeoAudit | None = Field(default=None)
    aio_strategy: QualAioStrategy | None = Field(default=None)
    briefing: str | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def _coerce_empty_dicts(cls, data: dict) -> dict:  # type: ignore[override]
        """Coerce empty dicts from legacy data to None.

        Before the typed sub-models were introduced, the LLM returned ``{}``
        for qualitative fields.  Existing briefing-data.json files still have
        these empty placeholders.  Convert ``{}`` to ``None`` for object
        fields and filter ``{}`` entries from list fields (turning the list
        to ``None`` if nothing remains).
        """
        if not isinstance(data, dict):
            return data
        object_fields = {
            "content_format_recommendation",
            "geo_audit",
            "aio_strategy",
        }
        list_fields = {"entity_clusters", "unique_angles"}
        for key in object_fields:
            if isinstance(data.get(key), dict) and not data[key]:
                data[key] = None
        for key in list_fields:
            val = data.get(key)
            if isinstance(val, list):
                filtered = [item for item in val if item != {}]
                data[key] = filtered or None
        return data


class BriefingData(PipelineBaseModel):
    """Top-level briefing data model.

    Aggregates all Phase 1 analysis outputs into a single structure.
    """

    meta: BriefingMeta
    stats: BriefingStats
    keyword_data: BriefingKeywordData
    serp_data: BriefingSerpData
    content_analysis: BriefingContentAnalysis
    competitor_analysis: BriefingCompetitorAnalysis
    faq_data: BriefingFaqData
    qualitative: BriefingQualitative
