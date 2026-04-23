"""Pydantic models for structured LLM responses."""

from seo_pipeline.models.common import PipelineBaseModel


class EntitySynonym(PipelineBaseModel):
    """A single entity-to-synonyms mapping."""

    entity: str
    synonyms: list[str]


class QualEntityCluster(PipelineBaseModel):
    """A cluster of entities under a category."""

    category: str
    entities: list[str]
    synonyms: list[EntitySynonym]


class QualGeoAudit(PipelineBaseModel):
    """GEO audit findings."""

    must_haves: list[str]
    hidden_gems: list[str]
    hallucination_risks: list[str]
    information_gaps: list[str]


class QualContentFormat(PipelineBaseModel):
    """Content format recommendation."""

    format: str
    rationale: str


class QualUniqueAngle(PipelineBaseModel):
    """A unique content angle."""

    angle: str
    rationale: str


class QualAioSnippet(PipelineBaseModel):
    """A single AIO optimization snippet."""

    topic: str
    pattern: str
    target_section: str


class QualAioStrategy(PipelineBaseModel):
    """AIO optimization strategy."""

    snippets: list[QualAioSnippet]


class QualitativeResponse(PipelineBaseModel):
    """Structured response from the qualitative analysis LLM call.

    Maps to the 5 qualitative fields in BriefingQualitative
    (entity_clusters, geo_audit, content_format_recommendation,
    unique_angles, aio_strategy).
    """

    entity_clusters: list[QualEntityCluster]
    geo_audit: QualGeoAudit
    content_format_recommendation: QualContentFormat
    unique_angles: list[QualUniqueAngle]
    aio_strategy: QualAioStrategy
