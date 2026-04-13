"""Tests for seo_pipeline.models.llm_responses — QualitativeResponse model."""

import json

import pytest
from pydantic import ValidationError

from seo_pipeline.models.llm_responses import QualitativeResponse


class TestQualitativeResponse:
    """QualitativeResponse creation, serialization, and validation."""

    @pytest.fixture()
    def sample_data(self):
        return {
            "entity_clusters": [
                {
                    "category": "Primary Topic",
                    "entities": ["entity1", "entity2"],
                    "synonyms": [
                        {"entity": "entity1", "synonyms": ["syn1", "syn2"]},
                    ],
                },
                {
                    "category": "Secondary",
                    "entities": ["entity3"],
                    "synonyms": [],
                },
            ],
            "geo_audit": {
                "must_haves": ["local schema markup"],
                "hidden_gems": ["Munich insider tips"],
                "hallucination_risks": ["incorrect population data"],
                "information_gaps": ["seasonal events"],
            },
            "content_format_recommendation": {
                "format": "comprehensive_guide",
                "rationale": "Topic requires depth",
            },
            "unique_angles": [
                {"angle": "Expert interviews", "rationale": "competitor gap"},
                {"angle": "Data visualization", "rationale": "user intent"},
            ],
            "aio_strategy": {
                "snippets": [
                    {
                        "topic": "What is X?",
                        "pattern": "X is a concise answer...",
                        "target_section": "Introduction",
                    },
                ],
            },
        }

    def test_creation(self, sample_data):
        resp = QualitativeResponse(**sample_data)
        assert len(resp.entity_clusters) == 2
        assert resp.entity_clusters[0].category == "Primary Topic"
        fmt = resp.content_format_recommendation
        assert fmt.format == "comprehensive_guide"
        assert len(resp.unique_angles) == 2
        assert resp.aio_strategy.snippets[0].topic == "What is X?"

    def test_serialization_roundtrip(self, sample_data):
        resp = QualitativeResponse(**sample_data)
        dumped = resp.model_dump()
        restored = QualitativeResponse(**dumped)
        assert restored == resp

    def test_json_roundtrip(self, sample_data):
        resp = QualitativeResponse(**sample_data)
        json_str = resp.model_dump_json()
        parsed = json.loads(json_str)
        restored = QualitativeResponse(**parsed)
        assert restored == resp

    def test_missing_required_field_raises(self, sample_data):
        del sample_data["entity_clusters"]
        with pytest.raises(ValidationError):
            QualitativeResponse(**sample_data)

    def test_empty_lists_accepted(self):
        resp = QualitativeResponse(
            entity_clusters=[],
            geo_audit={
                "must_haves": [],
                "hidden_gems": [],
                "hallucination_risks": [],
                "information_gaps": [],
            },
            content_format_recommendation={
                "format": "guide",
                "rationale": "simple",
            },
            unique_angles=[],
            aio_strategy={"snippets": []},
        )
        assert resp.entity_clusters == []
        assert resp.unique_angles == []


class TestQualitativeResponseSchema:
    """Regression: no bare type:object without properties in the schema."""

    def test_no_bare_object_without_properties(self):
        """Every 'type': 'object' node must have explicit 'properties'."""
        schema = QualitativeResponse.model_json_schema()
        self._check_node(schema)

    def _check_node(self, node):
        """Recursively check all nodes in the JSON schema."""
        if not isinstance(node, dict):
            return
        if node.get("type") == "object":
            # $ref nodes are resolved via $defs and don't need properties inline
            if "$ref" not in node:
                assert "properties" in node, (
                    f"Found bare 'type': 'object' without 'properties': {node}"
                )
        for value in node.values():
            if isinstance(value, dict):
                self._check_node(value)
            elif isinstance(value, list):
                for item in value:
                    self._check_node(item)
