"""Data models for keyword processing in the SEO Pipeline."""

from pydantic import BaseModel, ConfigDict, Field


class Keyword(BaseModel):
    """A keyword with optional metrics and filtering information.

    Attributes:
        keyword: The keyword text.
        search_volume: Monthly search volume (optional).
        cpc: Cost per click for ads (optional).
        monthly_searches: List of monthly search volume data (optional).
        difficulty: Keyword difficulty score 0-100 (optional).
        intent: Search intent type (optional).
        opportunity_score: Calculated opportunity score (optional).
        filter_status: Status after filtering - "keep" or "removed" (optional).
        filter_reason: Reason for removal if filtered out (optional).
        source: Source of the keyword (optional).
    """

    keyword: str
    search_volume: int | None = Field(default=None)
    cpc: float | None = Field(default=None)
    monthly_searches: list | None = Field(default=None)
    difficulty: int | None = Field(default=None)
    intent: str | None = Field(default=None)
    opportunity_score: float | None = Field(default=None)
    filter_status: str | None = Field(default=None)
    filter_reason: str | None = Field(default=None)
    source: str | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True)


class KeywordCluster(BaseModel):
    """A cluster of related keywords.

    Attributes:
        cluster_keyword: The main keyword for this cluster.
        cluster_label: User-defined label for the cluster (optional).
        strategic_notes: Notes about the cluster strategy (optional).
        keyword_count: Number of keywords in the cluster.
        keywords: List of keywords in the cluster.
        cluster_opportunity: Aggregate opportunity score (optional).
    """

    cluster_keyword: str
    cluster_label: str | None = Field(default=None)
    strategic_notes: str | None = Field(default=None)
    keyword_count: int
    keywords: list[Keyword]
    cluster_opportunity: float | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True)


class ProcessedKeywords(BaseModel):
    """Processed keywords with clustering information.

    Attributes:
        seed_keyword: The original keyword that was expanded.
        total_keywords: Total number of keywords found.
        total_clusters: Total number of clusters created.
        clusters: List of keyword clusters.
    """

    seed_keyword: str
    total_keywords: int
    total_clusters: int | None = Field(default=None)
    clusters: list[KeywordCluster] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class FaqItem(BaseModel):
    """A frequently asked question item.

    Attributes:
        question: The FAQ question text.
        priority: Priority level (e.g., "pflicht", "empfohlen", "optional").
        relevance_score: Relevance score for the keyword.
    """

    question: str
    priority: str
    relevance_score: int

    model_config = ConfigDict(populate_by_name=True)


class RemovalSummary(BaseModel):
    """Summary of keyword removal counts by reason.

    Attributes:
        ethics: Count of keywords removed for ethical reasons.
        brand: Count of keywords removed for brand protection.
        off_topic: Count of keywords removed as off-topic.
        foreign_language: Count of keywords removed for being foreign language.
    """

    ethics: int
    brand: int
    off_topic: int
    foreign_language: int

    model_config = ConfigDict(populate_by_name=True)


class FilteredKeywords(BaseModel):
    """Processed keywords after filtering.

    Contains filtering results and FAQ selection. Field order is important for
    serialization compatibility with golden output.

    Attributes:
        seed_keyword: The original keyword that was expanded.
        total_keywords: Total number of keywords found.
        filtered_keywords: Count of keywords that passed filtering.
        removed_count: Count of keywords removed during filtering.
        removal_summary: Breakdown of removal reasons.
        clusters: List of keyword clusters with filter information.
        faq_selection: Selected FAQ items based on keywords.
    """

    seed_keyword: str
    total_keywords: int
    filtered_keywords: int
    removed_count: int
    removal_summary: RemovalSummary
    clusters: list[KeywordCluster] = Field(default_factory=list)
    faq_selection: list[FaqItem] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class StrategistData(BaseModel):
    """Comprehensive data for content strategist analysis.

    Attributes:
        seed_keyword: The original keyword.
        top_keywords: Top keywords by opportunity score.
        all_keywords: All processed keywords.
        autocomplete: Autocomplete suggestions.
        content_ideas: Suggested content topics.
        paa_questions: People Also Ask questions from SERP.
        serp_snippets: Top SERP results snippets.
        competitor_keywords: Keywords used by competitors.
        stats: Aggregate statistics about the keyword set.
    """

    seed_keyword: str
    top_keywords: list = Field(default_factory=list)
    all_keywords: list = Field(default_factory=list)
    autocomplete: list[str] = Field(default_factory=list)
    content_ideas: list[str] = Field(default_factory=list)
    paa_questions: list = Field(default_factory=list)
    serp_snippets: list = Field(default_factory=list)
    competitor_keywords: list = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)
