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
                {"name": "Primary Topic", "entities": ["entity1", "entity2"]},
                {"name": "Secondary", "entities": ["entity3"]},
            ],
            "geo_audit": {
                "market": "de",
                "local_signals": ["Munich", "Berlin"],
                "recommendation": "Add local schema markup",
            },
            "content_format_recommendation": {
                "primary_format": "comprehensive_guide",
                "reason": "Topic requires depth",
                "suggested_sections": ["intro", "comparison", "faq"],
            },
            "unique_angles": [
                {"angle": "Expert interviews", "source": "competitor gap"},
                {"angle": "Data visualization", "source": "user intent"},
            ],
            "aio_strategy": {
                "approach": "concise_answer_box",
                "target_position": "featured_snippet",
                "key_question": "What is X?",
            },
        }

    def test_creation(self, sample_data):
        resp = QualitativeResponse(**sample_data)
        assert len(resp.entity_clusters) == 2
        assert resp.geo_audit["market"] == "de"
        fmt = resp.content_format_recommendation
        assert fmt["primary_format"] == "comprehensive_guide"
        assert len(resp.unique_angles) == 2
        assert resp.aio_strategy["approach"] == "concise_answer_box"

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
            geo_audit={},
            content_format_recommendation={},
            unique_angles=[],
            aio_strategy={},
        )
        assert resp.entity_clusters == []
        assert resp.unique_angles == []
