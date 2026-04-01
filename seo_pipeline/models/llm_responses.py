"""Pydantic models for structured LLM responses."""

from typing import Any

from seo_pipeline.models.common import PipelineBaseModel


class QualitativeResponse(PipelineBaseModel):
    """Structured response from the qualitative analysis LLM call.

    Maps to the 5 qualitative fields in BriefingQualitative
    (entity_clusters, geo_audit, content_format_recommendation,
    unique_angles, aio_strategy).
    """

    entity_clusters: list[dict[str, Any]]
    geo_audit: dict[str, Any]
    content_format_recommendation: dict[str, Any]
    unique_angles: list[dict[str, str]]
    aio_strategy: dict[str, Any]
