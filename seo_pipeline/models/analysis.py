"""Data models for analysis modules in the SEO Pipeline.

Covers: content topics, page structure, entity prominence, claims extraction,
WDF*IDF scoring, and the top-level BriefingData aggregation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_serializer

# ---------------------------------------------------------------------------
# Content Topics group
# ---------------------------------------------------------------------------


class ProofKeyword(BaseModel):
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

    model_config = ConfigDict(populate_by_name=True)

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        full = handler(self)
        return {k: v for k, v in full.items() if k in self.model_fields_set}


class EntityCandidate(BaseModel):
    """An entity candidate extracted from competitor content.

    In content-topics output: term, document_frequency, pages.
    In briefing content_analysis: adds prominence and prominence_source.
    """

    term: str
    document_frequency: int
    pages: list[str]
    prominence: str | None = Field(default=None)
    prominence_source: str | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True)

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        full = handler(self)
        return {k: v for k, v in full.items() if k in self.model_fields_set}


class SectionWeight(BaseModel):
    """Weight and occurrence data for a heading cluster."""

    heading_cluster: str
    sample_headings: list[str]
    occurrence: int
    avg_word_count: int | float
    avg_content_percentage: float
    weight: str

    model_config = ConfigDict(populate_by_name=True)


class ContentFormatSignals(BaseModel):
    """Content format signals aggregated across competitors."""

    pages_with_numbered_lists: int
    pages_with_faq: int
    pages_with_tables: int
    avg_h2_count: float
    dominant_pattern: str | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True)


class ContentTopics(BaseModel):
    """Top-level output of analyze-content-topics."""

    proof_keywords: list[ProofKeyword]
    entity_candidates: list[EntityCandidate]
    section_weights: list[SectionWeight]
    content_format_signals: ContentFormatSignals

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Page Structure group
# ---------------------------------------------------------------------------


class PageStructureSection(BaseModel):
    """A section within a competitor's page structure."""

    heading: str
    level: int
    word_count: int
    sentence_count: int
    has_numbers: bool
    has_lists: bool
    depth_score: str

    model_config = ConfigDict(populate_by_name=True)


class CompetitorPageStructure(BaseModel):
    """Page structure analysis for a single competitor."""

    url: str
    domain: str
    total_word_count: int
    section_count: int
    detected_modules: list[str]
    sections: list[PageStructureSection]

    model_config = ConfigDict(populate_by_name=True)


class CrossCompetitorAnalysis(BaseModel):
    """Cross-competitor module analysis."""

    common_modules: list[str]
    rare_modules: list[str]
    module_frequency: dict[str, int]
    avg_word_count: int | float
    avg_sections: int | float

    model_config = ConfigDict(populate_by_name=True)


class PageStructure(BaseModel):
    """Top-level output of analyze-page-structure."""

    competitors: list[CompetitorPageStructure]
    cross_competitor: CrossCompetitorAnalysis

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Entity Prominence group
# ---------------------------------------------------------------------------


class Entity(BaseModel):
    """An entity with prominence data."""

    entity: str
    prominence: str
    prominence_gemini: str | None = Field(default=None)
    prominence_source: str
    synonyms: list[str]

    model_config = ConfigDict(populate_by_name=True)

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        full = handler(self)
        return {k: v for k, v in full.items() if k in self.model_fields_set}


class EntityCluster(BaseModel):
    """A cluster of entities under a category."""

    category_name: str
    entities: list[Entity]

    model_config = ConfigDict(populate_by_name=True)


class ProminenceCorrection(BaseModel):
    """Debug record for a prominence correction."""

    entity: str
    category: str
    gemini: str
    code: str
    delta: int

    model_config = ConfigDict(populate_by_name=True)


class ProminenceDebug(BaseModel):
    """Debug data for entity prominence computation."""

    corrections: list[ProminenceCorrection]

    model_config = ConfigDict(populate_by_name=True)


class EntityProminence(BaseModel):
    """Top-level output of compute-entity-prominence."""

    entity_clusters: list[EntityCluster]
    debug: ProminenceDebug | None = Field(default=None, alias="_debug")

    model_config = ConfigDict(populate_by_name=True)

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


class Claim(BaseModel):
    """A single extracted factual claim."""

    id: str
    category: str
    value: str
    sentence: str
    line: int
    section: str | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True)


class ClaimsMeta(BaseModel):
    """Metadata for claims extraction."""

    draft: str
    extracted_at: str
    total_claims: int

    model_config = ConfigDict(populate_by_name=True)


class ClaimsOutput(BaseModel):
    """Top-level output of extract-claims."""

    meta: ClaimsMeta
    claims: list[Claim]

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# WDF*IDF group
# ---------------------------------------------------------------------------


class WdfIdfTerm(BaseModel):
    """A single term's WDF*IDF scores."""

    term: str
    draft_wdfidf: float
    competitor_avg_wdfidf: float
    delta: float
    signal: str

    model_config = ConfigDict(populate_by_name=True)


class WdfIdfMeta(BaseModel):
    """Metadata for WDF*IDF scoring."""

    draft: str
    pages_dir: str
    language: str
    threshold: float
    competitor_count: int
    idf_source: str

    model_config = ConfigDict(populate_by_name=True)


class WdfIdfScore(BaseModel):
    """Top-level output of score-draft-wdfidf."""

    meta: WdfIdfMeta
    terms: list[WdfIdfTerm]

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Briefing Data group
# ---------------------------------------------------------------------------


class BriefingDataSources(BaseModel):
    """Data sources metadata within briefing meta."""

    competitor_urls: list[str]
    location_code: int

    model_config = ConfigDict(populate_by_name=True)


class BriefingMeta(BaseModel):
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

    model_config = ConfigDict(populate_by_name=True)


class BriefingStats(BaseModel):
    """Summary statistics for the briefing."""

    total_keywords: int
    filtered_keywords: int
    total_clusters: int
    competitor_count: int

    model_config = ConfigDict(populate_by_name=True)


class BriefingKeywordClusterSummary(BaseModel):
    """Flattened cluster summary in briefing keyword_data (no individual keywords)."""

    cluster_keyword: str
    cluster_label: str | None = Field(default=None)
    cluster_opportunity: float | int
    keyword_count: int
    rank: int
    total_search_volume: int | float

    model_config = ConfigDict(populate_by_name=True)


class BriefingKeywordData(BaseModel):
    """Keyword data section in BriefingData (flattened summaries)."""

    clusters: list[BriefingKeywordClusterSummary]
    total_keywords: int
    filtered_count: int
    removal_summary: dict[str, int]

    model_config = ConfigDict(populate_by_name=True)


class BriefingSerpFeatures(BaseModel):
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

    model_config = ConfigDict(populate_by_name=True)


class BriefingAioReference(BaseModel):
    """AI Overview reference in briefing serp_data."""

    domain: str
    title: str
    url: str

    model_config = ConfigDict(populate_by_name=True)


class BriefingAio(BaseModel):
    """AI Overview section in briefing serp_data."""

    present: bool
    references: list[BriefingAioReference]
    references_count: int
    text: str | None = Field(default=None)
    title: str | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True)


class BriefingHeading(BaseModel):
    """Heading in briefing competitor data."""

    level: int
    text: str

    model_config = ConfigDict(populate_by_name=True)


class BriefingRating(BaseModel):
    """Rating in briefing competitor data."""

    rating_max: float | int
    value: float
    votes_count: int

    model_config = ConfigDict(populate_by_name=True)


class BriefingCompetitor(BaseModel):
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
    word_count: int

    model_config = ConfigDict(populate_by_name=True)

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """Emit keys in alphabetical order."""
        full = handler(self)
        return dict(sorted(full.items()))


class BriefingSerpData(BaseModel):
    """SERP data section in BriefingData."""

    competitors: list[BriefingCompetitor]
    serp_features: BriefingSerpFeatures
    aio: BriefingAio

    model_config = ConfigDict(populate_by_name=True)


class BriefingContentAnalysis(BaseModel):
    """Content analysis section in BriefingData.

    Uses ProofKeyword (without idf_boost/idf_score) and EntityCandidate
    (with prominence fields).
    """

    proof_keywords: list[ProofKeyword]
    entity_candidates: list[EntityCandidate]
    section_weights: list[SectionWeight]
    content_format_signals: ContentFormatSignals

    model_config = ConfigDict(populate_by_name=True)


class BriefingCompetitorAnalysis(BaseModel):
    """Competitor analysis section in BriefingData."""

    page_structures: list[CompetitorPageStructure]
    common_modules: list[str]
    rare_modules: list[str]
    avg_word_count: int | float

    model_config = ConfigDict(populate_by_name=True)


class BriefingFaqQuestion(BaseModel):
    """FAQ question in briefing faq_data."""

    priority: str
    question: str
    relevance_score: int

    model_config = ConfigDict(populate_by_name=True)


class BriefingFaqData(BaseModel):
    """FAQ data section in BriefingData."""

    questions: list[BriefingFaqQuestion]
    paa_source: str

    model_config = ConfigDict(populate_by_name=True)


class BriefingQualitative(BaseModel):
    """Qualitative analysis section (all nullable, populated by LLM)."""

    entity_clusters: list | None = Field(default=None)
    unique_angles: list | None = Field(default=None)
    content_format_recommendation: str | None = Field(default=None)
    geo_audit: dict | None = Field(default=None)
    aio_strategy: str | None = Field(default=None)
    briefing: str | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True)


class BriefingData(BaseModel):
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

    model_config = ConfigDict(populate_by_name=True)
