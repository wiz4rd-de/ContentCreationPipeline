"""Tests for assemble_briefing_data module."""

import json
from pathlib import Path

import pytest

from seo_pipeline.analysis.assemble_briefing_data import (
    PIPELINE_VERSION,
    _build_cluster_ranking,
    _build_entity_candidates,
    _build_serp_features,
    _extract_date_from_dir,
    _normalize_tree,
    assemble_briefing_data,
    main,
    normalize_years,
)

FIXTURES = Path("tests/fixtures/assemble-briefing-data/2026-03-09_test-keyword")
GOLDEN = Path("tests/golden")

# Sentinel timestamp used in golden file so tests are deterministic.
GOLDEN_TIMESTAMP = "2026-01-01T00:00:00.000Z"


# ---------------------------------------------------------------------------
# Year normalization
# ---------------------------------------------------------------------------


class TestNormalizeYears:
    """Tests for normalize_years()."""

    def test_none_passthrough(self):
        assert normalize_years(None, 2026) is None

    def test_string_replaces_2024(self):
        assert normalize_years("Best tools 2024", 2026) == "Best tools 2026"

    def test_string_replaces_2025(self):
        assert normalize_years("Guide 2025 edition", 2026) == "Guide 2026 edition"

    def test_string_no_match(self):
        assert normalize_years("Guide 2023 edition", 2026) == "Guide 2023 edition"

    def test_string_word_boundary(self):
        # 2024 embedded in longer number should NOT be replaced
        assert normalize_years("ID: 120245", 2026) == "ID: 120245"

    def test_list_recursive(self):
        result = normalize_years(["year 2024", "year 2025", 42], 2026)
        assert result == ["year 2026", "year 2026", 42]

    def test_dict_sorts_keys(self):
        result = normalize_years({"z": "2024", "a": "2025"}, 2026)
        assert list(result.keys()) == ["a", "z"]
        assert result == {"a": "2026", "z": "2026"}

    def test_nested_dict_in_list(self):
        data = [{"title": "Page 2024", "count": 5}]
        result = normalize_years(data, 2026)
        assert result == [{"count": 5, "title": "Page 2026"}]

    def test_int_passthrough(self):
        assert normalize_years(42, 2026) == 42

    def test_float_passthrough(self):
        assert normalize_years(3.14, 2026) == 3.14

    def test_bool_passthrough(self):
        assert normalize_years(True, 2026) is True


# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------


class TestExtractDateFromDir:
    """Tests for _extract_date_from_dir()."""

    def test_standard_dir_name(self, tmp_path):
        d = tmp_path / "2026-03-09_test-keyword"
        d.mkdir()
        assert _extract_date_from_dir(d) == "2026-03-09"

    def test_no_date_fallback_to_today(self, tmp_path):
        d = tmp_path / "some-keyword"
        d.mkdir()
        result = _extract_date_from_dir(d)
        # Should be a valid YYYY-MM-DD string
        assert len(result) == 10
        assert result[4] == "-" and result[7] == "-"


# ---------------------------------------------------------------------------
# Cluster ranking
# ---------------------------------------------------------------------------


class TestBuildClusterRanking:
    """Tests for _build_cluster_ranking()."""

    def test_sorts_by_volume_desc(self):
        data = {
            "keywords_filtered": {
                "clusters": [
                    {
                        "cluster_keyword": "low",
                        "keywords": [{"search_volume": 100}],
                        "keyword_count": 1,
                    },
                    {
                        "cluster_keyword": "high",
                        "keywords": [{"search_volume": 1000}],
                        "keyword_count": 1,
                    },
                ],
            },
            "keywords_processed": None,
        }
        result = _build_cluster_ranking(data)
        assert result[0]["cluster_keyword"] == "high"
        assert result[0]["rank"] == 1
        assert result[1]["cluster_keyword"] == "low"
        assert result[1]["rank"] == 2

    def test_alpha_tiebreak(self):
        data = {
            "keywords_filtered": {
                "clusters": [
                    {
                        "cluster_keyword": "beta",
                        "keywords": [{"search_volume": 500}],
                        "keyword_count": 1,
                    },
                    {
                        "cluster_keyword": "alpha",
                        "keywords": [{"search_volume": 500}],
                        "keyword_count": 1,
                    },
                ],
            },
            "keywords_processed": None,
        }
        result = _build_cluster_ranking(data)
        assert result[0]["cluster_keyword"] == "alpha"
        assert result[1]["cluster_keyword"] == "beta"

    def test_no_source(self):
        data = {"keywords_filtered": None, "keywords_processed": None}
        assert _build_cluster_ranking(data) == []

    def test_no_clusters_key(self):
        data = {"keywords_filtered": {"total_keywords": 5}, "keywords_processed": None}
        assert _build_cluster_ranking(data) == []

    def test_falls_back_to_keywords_processed(self):
        data = {
            "keywords_filtered": None,
            "keywords_processed": {
                "clusters": [
                    {
                        "cluster_keyword": "only",
                        "keywords": [{"search_volume": 200}],
                        "keyword_count": 1,
                    },
                ],
            },
        }
        result = _build_cluster_ranking(data)
        assert len(result) == 1
        assert result[0]["total_search_volume"] == 200

    def test_missing_search_volume_defaults_to_zero(self):
        data = {
            "keywords_filtered": {
                "clusters": [
                    {
                        "cluster_keyword": "empty",
                        "keywords": [{}],
                        "keyword_count": 1,
                    },
                ],
            },
            "keywords_processed": None,
        }
        result = _build_cluster_ranking(data)
        assert result[0]["total_search_volume"] == 0

    def test_cluster_opportunity_none(self):
        data = {
            "keywords_filtered": {
                "clusters": [
                    {
                        "cluster_keyword": "test",
                        "keywords": [{"search_volume": 100}],
                        "keyword_count": 2,
                    },
                ],
            },
            "keywords_processed": None,
        }
        result = _build_cluster_ranking(data)
        assert result[0]["cluster_opportunity"] is None


# ---------------------------------------------------------------------------
# Entity candidates with prominence merge
# ---------------------------------------------------------------------------


class TestBuildEntityCandidates:
    """Tests for _build_entity_candidates()."""

    def test_no_content_topics(self):
        data = {"content_topics": None, "entity_prominence": None}
        assert _build_entity_candidates(data) is None

    def test_no_entity_candidates_key(self):
        data = {"content_topics": {}, "entity_prominence": None}
        assert _build_entity_candidates(data) is None

    def test_without_prominence(self):
        candidates = [
            {"term": "google", "document_frequency": 3, "pages": ["a.com"]},
        ]
        data = {
            "content_topics": {"entity_candidates": candidates},
            "entity_prominence": None,
        }
        result = _build_entity_candidates(data)
        assert result == candidates

    def test_with_prominence_merge(self):
        candidates = [
            {"term": "google", "document_frequency": 3, "pages": ["a.com"]},
        ]
        prominence = {
            "entity_clusters": [
                {
                    "category_name": "Tools",
                    "entities": [{
                        "entity": "Google",
                        "prominence": "3/3",
                        "prominence_source": "code",
                    }],
                },
            ],
        }
        data = {
            "content_topics": {"entity_candidates": candidates},
            "entity_prominence": prominence,
        }
        result = _build_entity_candidates(data)
        assert result[0]["prominence"] == "3/3"
        assert result[0]["prominence_source"] == "code"

    def test_case_insensitive_match(self):
        candidates = [
            {"term": "Google", "document_frequency": 1, "pages": []},
        ]
        prominence = {
            "entity_clusters": [
                {
                    "category_name": "X",
                    "entities": [{
                        "entity": "google",
                        "prominence": "1/1",
                        "prominence_source": "code",
                    }],
                },
            ],
        }
        data = {
            "content_topics": {"entity_candidates": candidates},
            "entity_prominence": prominence,
        }
        result = _build_entity_candidates(data)
        assert result[0]["prominence"] == "1/1"

    def test_unmatched_candidate_unchanged(self):
        candidates = [
            {"term": "unknown", "document_frequency": 1, "pages": []},
        ]
        prominence = {
            "entity_clusters": [
                {
                    "category_name": "X",
                    "entities": [{
                        "entity": "google",
                        "prominence": "3/3",
                        "prominence_source": "code",
                    }],
                },
            ],
        }
        data = {
            "content_topics": {"entity_candidates": candidates},
            "entity_prominence": prominence,
        }
        result = _build_entity_candidates(data)
        assert "prominence" not in result[0]


# ---------------------------------------------------------------------------
# SERP features
# ---------------------------------------------------------------------------


class TestBuildSerpFeatures:
    """Tests for _build_serp_features()."""

    def test_no_serp(self):
        assert _build_serp_features({"serp": None}) is None

    def test_no_features_key(self):
        assert _build_serp_features({"serp": {}}) is None

    def test_present_flags(self):
        features = {
            "ai_overview": {"present": True, "text": "..."},
            "featured_snippet": {"present": False},
            "people_also_ask": [{"question": "x"}],
            "people_also_search": [],
            "knowledge_graph": {"present": False},
            "commercial_signals": {"paid_ads_present": False},
            "local_signals": {"local_pack_present": True},
            "other_features_present": [],
        }
        result = _build_serp_features({"serp": {"serp_features": features}})
        assert result["ai_overview"] is True
        assert result["featured_snippet"] is False
        assert result["people_also_ask"] is True
        assert result["people_also_search"] is False
        assert result["knowledge_graph"] is False
        assert result["commercial_signals"] is False
        assert result["local_signals"] is True


# ---------------------------------------------------------------------------
# normalize_tree
# ---------------------------------------------------------------------------


class TestNormalizeTree:
    """Tests for _normalize_tree()."""

    def test_float_to_int(self):
        assert _normalize_tree(4.0) == 4
        assert isinstance(_normalize_tree(4.0), int)

    def test_float_stays_float(self):
        assert _normalize_tree(4.5) == 4.5

    def test_nested_dict(self):
        assert _normalize_tree({"a": 1.0, "b": 2.5}) == {"a": 1, "b": 2.5}

    def test_nested_list(self):
        assert _normalize_tree([1.0, 2.5]) == [1, 2.5]


# ---------------------------------------------------------------------------
# Full assembly (integration)
# ---------------------------------------------------------------------------


class TestAssembleBriefingData:
    """Integration tests using fixture data."""

    def test_full_assembly(self):
        result = assemble_briefing_data(
            FIXTURES,
            timestamp_override=GOLDEN_TIMESTAMP,
        )

        assert result["meta"]["seed_keyword"] == "test keyword"
        assert result["meta"]["date"] == "2026-03-09"
        assert result["meta"]["current_year"] == 2026
        assert result["meta"]["pipeline_version"] == PIPELINE_VERSION
        assert result["meta"]["phase1_completed_at"] == GOLDEN_TIMESTAMP

    def test_stats(self):
        result = assemble_briefing_data(
            FIXTURES,
            timestamp_override=GOLDEN_TIMESTAMP,
        )
        assert result["stats"] == {
            "total_keywords": 10,
            "filtered_keywords": 8,
            "total_clusters": 3,
            "competitor_count": 3,
        }

    def test_cluster_ranking_order(self):
        result = assemble_briefing_data(
            FIXTURES,
            timestamp_override=GOLDEN_TIMESTAMP,
        )
        clusters = result["keyword_data"]["clusters"]
        assert len(clusters) == 3
        assert clusters[0]["cluster_keyword"] == "keyword tool"
        assert clusters[0]["rank"] == 1
        assert clusters[0]["total_search_volume"] == 1800
        assert clusters[1]["cluster_keyword"] == "test keyword"
        assert clusters[2]["cluster_keyword"] == "seo analyse"

    def test_year_normalization_in_competitors(self):
        result = assemble_briefing_data(
            FIXTURES,
            timestamp_override=GOLDEN_TIMESTAMP,
        )
        # competitors-data.json has "2025" in titles and "2024" in timestamps
        first = result["serp_data"]["competitors"][0]
        assert "2026" in first["title"]
        assert "2024" not in first["title"]
        assert first["timestamp"] == "2026-01-15"

    def test_year_normalization_in_aio(self):
        result = assemble_briefing_data(
            FIXTURES,
            timestamp_override=GOLDEN_TIMESTAMP,
        )
        aio = result["serp_data"]["aio"]
        assert "2026" in aio["text"]
        assert "2024" not in aio["text"]

    def test_entity_prominence_merged(self):
        result = assemble_briefing_data(
            FIXTURES,
            timestamp_override=GOLDEN_TIMESTAMP,
        )
        entities = result["content_analysis"]["entity_candidates"]
        google = next(e for e in entities if e["term"] == "google")
        assert google["prominence"] == "3/3"
        assert google["prominence_source"] == "code"

    def test_data_sources(self):
        result = assemble_briefing_data(
            FIXTURES,
            timestamp_override=GOLDEN_TIMESTAMP,
        )
        ds = result["meta"]["data_sources"]
        assert len(ds["competitor_urls"]) == 3
        assert ds["location_code"] == 2276

    def test_faq_data(self):
        result = assemble_briefing_data(
            FIXTURES,
            timestamp_override=GOLDEN_TIMESTAMP,
        )
        faq = result["faq_data"]
        assert faq["paa_source"] == "serp"
        assert len(faq["questions"]) == 2

    def test_qualitative_null(self):
        result = assemble_briefing_data(
            FIXTURES,
            timestamp_override=GOLDEN_TIMESTAMP,
        )
        q = result["qualitative"]
        assert all(v is None for v in q.values())

    def test_missing_files_graceful(self, tmp_path):
        d = tmp_path / "2026-01-01_empty"
        d.mkdir()
        result = assemble_briefing_data(d, timestamp_override=GOLDEN_TIMESTAMP)
        assert result["meta"]["seed_keyword"] is None
        assert result["stats"]["total_keywords"] == 0
        assert result["serp_data"]["competitors"] is None
        assert result["content_analysis"]["proof_keywords"] is None
        assert result["faq_data"] is None


# ---------------------------------------------------------------------------
# Golden file test
# ---------------------------------------------------------------------------


class TestGoldenOutput:
    """Test byte-identical output against golden file."""

    def test_golden_match(self):
        golden_path = GOLDEN / "assemble-briefing-data--2026-03-09_test-keyword.json"
        if not golden_path.exists():
            pytest.skip("Golden file not found")

        result = assemble_briefing_data(
            FIXTURES,
            timestamp_override=GOLDEN_TIMESTAMP,
        )
        output_dict = _normalize_tree(result)
        actual = json.dumps(output_dict, indent=2, ensure_ascii=False)

        expected = golden_path.read_text(encoding="utf-8").rstrip("\n")
        assert actual == expected


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    """Tests for CLI entry point."""

    def test_cli_writes_output(self, tmp_path):
        output = tmp_path / "out.json"
        main(["--dir", str(FIXTURES), "--output", str(output)])
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["meta"]["seed_keyword"] == "test keyword"
        assert data["meta"]["current_year"] == 2026

    def test_cli_default_output_path(self, tmp_path):
        # Copy fixtures to tmp so we can write briefing-data.json there
        import shutil
        d = tmp_path / "2026-03-09_test-keyword"
        shutil.copytree(FIXTURES, d)
        main(["--dir", str(d)])
        output = d / "briefing-data.json"
        assert output.exists()
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["meta"]["seed_keyword"] == "test keyword"

    def test_cli_golden_match(self, tmp_path):
        golden_path = GOLDEN / "assemble-briefing-data--2026-03-09_test-keyword.json"
        if not golden_path.exists():
            pytest.skip("Golden file not found")

        # CLI does not support timestamp_override, so we compare everything
        # except phase1_completed_at
        output = tmp_path / "out.json"
        main(["--dir", str(FIXTURES), "--output", str(output)])
        actual = json.loads(output.read_text(encoding="utf-8"))
        expected = json.loads(golden_path.read_text(encoding="utf-8"))

        # Replace dynamic timestamp for comparison
        actual["meta"]["phase1_completed_at"] = GOLDEN_TIMESTAMP
        assert actual == expected

    def test_cli_with_meta_flags(self, tmp_path):
        output = tmp_path / "out.json"
        main([
            "--dir", str(FIXTURES),
            "--output", str(output),
            "--market", "de",
            "--language", "de",
            "--user-domain", "example.com",
            "--business-context", "SEO agency",
        ])
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["meta"]["market"] == "de"
        assert data["meta"]["language"] == "de"
        assert data["meta"]["user_domain"] == "example.com"
        assert data["meta"]["business_context"] == "SEO agency"
