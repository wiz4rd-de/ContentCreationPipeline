"""Data models for SERP processing in the SEO Pipeline."""

from typing import Any

from pydantic import Field, model_serializer

from seo_pipeline.models.common import PipelineBaseModel

# --- SERP Feature sub-models ---


class AiOverviewReference(PipelineBaseModel):
    """A reference cited in the AI Overview.

    Attributes:
        domain: The domain of the referenced page.
        url: The full URL of the referenced page.
        title: The title of the referenced page.
    """

    domain: str | None = Field(default=None)
    url: str | None = Field(default=None)
    title: str | None = Field(default=None)


class AiOverview(PipelineBaseModel):
    """AI Overview (AIO) feature from the SERP.

    Handles both present and absent states. When present is False,
    other fields default to None or empty lists.

    Attributes:
        present: Whether an AI Overview is shown.
        references: List of references cited in the overview.
        title: Title of the AI Overview section.
        text: Body text of the AI Overview.
        references_count: Number of references cited.
    """

    present: bool
    references: list[AiOverviewReference] = Field(default_factory=list)
    title: str | None = Field(default=None)
    text: str | None = Field(default=None)
    references_count: int = Field(default=0)


class FeaturedSnippet(PipelineBaseModel):
    """Featured snippet feature from the SERP.

    Serializes with exclude_unset so that ``{"present": false}`` roundtrips
    without emitting nullable fields that were never provided.

    Attributes:
        present: Whether a featured snippet is shown.
        format: The snippet format (paragraph, list, table, etc.).
        source_domain: Domain of the snippet source.
        source_url: URL of the snippet source.
    """

    present: bool
    format: str | None = Field(default=None)
    source_domain: str | None = Field(default=None)
    source_url: str | None = Field(default=None)

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """Only include fields that were explicitly set."""
        full = handler(self)
        return {k: v for k, v in full.items() if k in self.model_fields_set}


class PaaQuestion(PipelineBaseModel):
    """A People Also Ask question from the SERP.

    Attributes:
        question: The question text.
        answer: The answer text (None if not expanded).
        url: URL of the answer source.
        domain: Domain of the answer source.
    """

    question: str
    answer: str | None = Field(default=None)
    url: str | None = Field(default=None)
    domain: str | None = Field(default=None)


class KnowledgeGraph(PipelineBaseModel):
    """Knowledge Graph panel from the SERP.

    Serializes with exclude_unset so that ``{"present": false}`` roundtrips
    without emitting nullable fields that were never provided.

    Attributes:
        present: Whether a Knowledge Graph panel is shown.
        title: Title of the Knowledge Graph entry.
        description: Description text in the Knowledge Graph.
    """

    present: bool
    title: str | None = Field(default=None)
    description: str | None = Field(default=None)

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """Only include fields that were explicitly set."""
        full = handler(self)
        return {k: v for k, v in full.items() if k in self.model_fields_set}


class CommercialSignals(PipelineBaseModel):
    """Commercial intent signals detected in the SERP.

    Attributes:
        paid_ads_present: Whether paid ads appear.
        shopping_present: Whether shopping results appear.
        commercial_units_present: Whether commercial units appear.
        popular_products_present: Whether popular products appear.
    """

    paid_ads_present: bool
    shopping_present: bool
    commercial_units_present: bool
    popular_products_present: bool


class LocalSignals(PipelineBaseModel):
    """Local search signals detected in the SERP.

    Attributes:
        local_pack_present: Whether a local pack appears.
        map_present: Whether a map appears.
        hotels_pack_present: Whether a hotels pack appears.
    """

    local_pack_present: bool
    map_present: bool
    hotels_pack_present: bool


class RelatedSearch(PipelineBaseModel):
    """A related search suggestion.

    Attributes:
        query: The related search query text.
    """

    query: str


class Discussion(PipelineBaseModel):
    """A discussion/forum result from the SERP.

    Attributes:
        url: URL of the discussion.
        domain: Domain hosting the discussion.
        title: Title of the discussion.
        description: Description or snippet of the discussion.
    """

    url: str | None = Field(default=None)
    domain: str | None = Field(default=None)
    title: str | None = Field(default=None)
    description: str | None = Field(default=None)


class VideoResult(PipelineBaseModel):
    """A video result from the SERP.

    Attributes:
        url: URL of the video.
        domain: Domain hosting the video.
        title: Title of the video.
        description: Description of the video.
    """

    url: str | None = Field(default=None)
    domain: str | None = Field(default=None)
    title: str | None = Field(default=None)
    description: str | None = Field(default=None)


class TopStory(PipelineBaseModel):
    """A top story result from the SERP.

    Attributes:
        url: URL of the story.
        domain: Domain of the story.
        title: Title of the story.
        description: Description of the story.
    """

    url: str | None = Field(default=None)
    domain: str | None = Field(default=None)
    title: str | None = Field(default=None)
    description: str | None = Field(default=None)


class SerpFeatures(PipelineBaseModel):
    """Composite model of all SERP features.

    Can be empty ({}) when no features are detected. All fields
    have defaults so the model can be instantiated with no arguments.

    Attributes:
        ai_overview: AI Overview feature data.
        featured_snippet: Featured snippet feature data.
        people_also_ask: List of People Also Ask questions.
        people_also_search: List of People Also Search suggestions.
        related_searches: List of related search suggestions.
        discussions_and_forums: List of discussion results.
        video: List of video results.
        top_stories: List of top story results.
        knowledge_graph: Knowledge Graph panel data.
        commercial_signals: Commercial intent signals.
        local_signals: Local search signals.
        other_features_present: List of other feature type strings.
    """

    ai_overview: AiOverview | None = Field(default=None)
    featured_snippet: FeaturedSnippet | None = Field(default=None)
    people_also_ask: list[PaaQuestion] = Field(default_factory=list)
    people_also_search: list[str] = Field(default_factory=list)
    related_searches: list[RelatedSearch] = Field(default_factory=list)
    discussions_and_forums: list[Discussion] = Field(default_factory=list)
    video: list[VideoResult] = Field(default_factory=list)
    top_stories: list[TopStory] = Field(default_factory=list)
    knowledge_graph: KnowledgeGraph | None = Field(default=None)
    commercial_signals: CommercialSignals | None = Field(default=None)
    local_signals: LocalSignals | None = Field(default=None)
    other_features_present: list[str] = Field(default_factory=list)


# --- Competitor and Rating models ---


class Rating(PipelineBaseModel):
    """A rating attached to a SERP result.

    Attributes:
        value: The rating value (e.g., 4.5).
        votes_count: Number of votes/reviews.
        rating_max: Maximum possible rating value.
    """

    value: float | None = Field(default=None)
    votes_count: int | None = Field(default=None)
    rating_max: float | None = Field(default=None)


class SerpCompetitor(PipelineBaseModel):
    """A competitor result from the SERP.

    Uses a single model with optional qualitative fields that are absent
    in process-serp output and populated after assemble-competitors.

    Attributes:
        rank: Organic rank position.
        rank_absolute: Absolute position including all result types.
        url: Full URL of the result.
        domain: Domain of the result.
        title: Title of the result.
        description: Meta description or snippet.
        is_featured_snippet: Whether this result is the featured snippet.
        is_video: Whether this is a video result.
        has_rating: Whether this result has a rating.
        rating: Rating data (None if no rating).
        timestamp: Publication or update timestamp string.
        cited_in_ai_overview: Whether this result is cited in the AI Overview.
        word_count: Word count of the page content (extended field).
        h1: The H1 heading of the page (extended field).
        headings: Headings extracted from the page (extended field).
        link_count: Link counts for the page (extended field).
        meta_description: Full meta description (extended field).
        format: Content format analysis (extended field).
        topics: Topics covered (extended field).
        unique_angle: Unique angle of the content (extended field).
        strengths: Content strengths (extended field).
        weaknesses: Content weaknesses (extended field).
    """

    rank: int
    rank_absolute: int
    url: str
    domain: str
    title: str
    description: str | None = Field(default=None)
    is_featured_snippet: bool
    is_video: bool
    has_rating: bool
    rating: Rating | None = Field(default=None)
    timestamp: str | None = Field(default=None)
    cited_in_ai_overview: bool
    word_count: int | None = Field(default=None)
    h1: str | None = Field(default=None)
    headings: list[dict[str, Any]] | None = Field(default=None)
    link_count: dict[str, int] | None = Field(default=None)
    meta_description: str | None = Field(default=None)
    format: str | None = Field(default=None)
    topics: list[str] | None = Field(default=None)
    unique_angle: str | None = Field(default=None)
    strengths: list[str] | None = Field(default=None)
    weaknesses: list[str] | None = Field(default=None)


# --- Top-level output models ---


class SerpProcessed(PipelineBaseModel):
    """Top-level output model for process-serp.

    Attributes:
        target_keyword: The keyword that was searched.
        se_results_count: Total number of search engine results.
        location_code: DataForSEO location code.
        language_code: Language code for the search.
        item_types_present: List of SERP item types found.
        serp_features: Composite SERP features data.
        competitors: List of organic competitors.
    """

    target_keyword: str
    se_results_count: int
    location_code: int
    language_code: str
    item_types_present: list[str] = Field(default_factory=list)
    serp_features: SerpFeatures
    competitors: list[SerpCompetitor] = Field(default_factory=list)


class CompetitorsData(PipelineBaseModel):
    """Output model for assemble-competitors.

    Extends process-serp output with a date field and qualitative
    analysis fields on competitors.

    Attributes:
        target_keyword: The keyword that was searched.
        date: Date of the SERP data collection.
        se_results_count: Total number of search engine results.
        location_code: DataForSEO location code.
        language_code: Language code for the search.
        item_types_present: List of SERP item types found.
        serp_features: Composite SERP features data.
        competitors: List of competitors with extended fields.
        common_themes: Common themes across competitors.
        content_gaps: Content gaps identified.
        opportunities: Opportunities identified.
    """

    target_keyword: str
    date: str
    se_results_count: int
    location_code: int
    language_code: str
    item_types_present: list[str] = Field(default_factory=list)
    serp_features: SerpFeatures
    competitors: list[SerpCompetitor] = Field(default_factory=list)
    common_themes: list[str] | None = Field(default=None)
    content_gaps: list[str] | None = Field(default=None)
    opportunities: list[str] | None = Field(default=None)
