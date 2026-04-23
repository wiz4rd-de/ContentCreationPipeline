"""Deterministic briefing data assembler.

Consolidates all pipeline analysis outputs into a single briefing-data.json.
Same inputs always produce byte-identical output.

Usage:
    python -m seo_pipeline.analysis.assemble_briefing_data \
        --dir <output/YYYY-MM-DD_slug/> [--market de] [--language de] \
        [--user-domain example.com] [--business-context "..."] [--output path]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from seo_pipeline.utils.math import normalize_number

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "0.2.0"

_YEAR_RE = re.compile(r"\b(2024|2025)\b")

# Maps logical names to filenames on disk.
INPUT_FILES = {
    "serp": "serp-processed.json",
    "serp_raw": "serp-raw.json",
    "keywords_processed": "keywords-processed.json",
    "keywords_filtered": "keywords-filtered.json",
    "page_structure": "page-structure.json",
    "content_topics": "content-topics.json",
    "entity_prominence": "entity-prominence.json",
    "competitors_data": "competitors-data.json",
}


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _load_optional(directory: Path, filename: str) -> Any:
    """Load a JSON file from *directory*, returning None on missing/invalid."""
    path = directory / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _load_inputs(directory: Path) -> dict[str, Any]:
    """Load all 8 optional input files from *directory*."""
    return {
        key: _load_optional(directory, filename)
        for key, filename in INPUT_FILES.items()
    }


# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------

_DIR_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_")


def _extract_date_from_dir(dir_path: Path) -> str:
    """Extract YYYY-MM-DD from directory name, fallback to today."""
    match = _DIR_DATE_RE.match(dir_path.name)
    if match:
        return match.group(1)
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Year normalization
# ---------------------------------------------------------------------------


def normalize_years(value: Any, current_year: int) -> Any:
    """Replace 2024/2025 with *current_year* in all string values (recursive).

    Dict keys are sorted alphabetically to match the Node.js implementation.
    """
    if value is None:
        return value
    if isinstance(value, str):
        return _YEAR_RE.sub(str(current_year), value)
    if isinstance(value, list):
        return [normalize_years(v, current_year) for v in value]
    if isinstance(value, dict):
        return {
            k: normalize_years(v, current_year)
            for k, v in sorted(value.items())
        }
    return value


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _build_cluster_ranking(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Sort keyword clusters by total search volume desc, assign rank."""
    source = data["keywords_filtered"] or data["keywords_processed"]
    if source is None or not isinstance(source.get("clusters"), list):
        return []

    ranked = []
    for cluster in source["clusters"]:
        raw_kw = cluster.get("keywords")
        keywords = raw_kw if isinstance(raw_kw, list) else []
        total_volume = sum(kw.get("search_volume") or 0 for kw in keywords)
        ranked.append({
            "cluster_keyword": cluster["cluster_keyword"],
            "cluster_label": cluster.get("cluster_label"),
            "cluster_opportunity": cluster.get("cluster_opportunity"),
            "keyword_count": cluster.get("keyword_count") or len(keywords),
            "rank": 0,
            "total_search_volume": total_volume,
        })

    # Sort by total_search_volume desc, then cluster_keyword asc for determinism
    ranked.sort(key=lambda c: (-c["total_search_volume"], c["cluster_keyword"]))

    for i, item in enumerate(ranked):
        item["rank"] = i + 1

    return ranked


def _build_proof_keywords(
    data: dict[str, Any], current_year: int,
) -> list[dict[str, Any]] | None:
    if data["content_topics"] is None:
        return None
    pks = data["content_topics"].get("proof_keywords", [])
    return normalize_years(pks, current_year)


def _build_module_frequency(data: dict[str, Any]) -> dict[str, Any] | None:
    if data["page_structure"] is None:
        return None
    cc = data["page_structure"].get("cross_competitor")
    if cc is None:
        return None
    return {
        "common_modules": cc.get("common_modules", []),
        "rare_modules": cc.get("rare_modules", []),
        "module_frequency": cc.get("module_frequency", {}),
    }


def _build_section_weights(data: dict[str, Any]) -> list[dict[str, Any]] | None:
    if data["content_topics"] is None:
        return None
    return data["content_topics"].get("section_weights", [])


def _build_aio_data(data: dict[str, Any], current_year: int) -> dict[str, Any] | None:
    if data["serp"] is None:
        return None
    aio = (data["serp"].get("serp_features") or {}).get("ai_overview")
    if aio is None:
        return {"present": False}
    return normalize_years(aio, current_year)


def _build_faq_data(data: dict[str, Any], current_year: int) -> dict[str, Any] | None:
    if data["keywords_filtered"] is None:
        return None
    faq_selection = data["keywords_filtered"].get("faq_selection")
    if not isinstance(faq_selection, list):
        return None
    return {
        "questions": normalize_years(faq_selection, current_year),
        "paa_source": "serp",
    }


def _build_entity_candidates(data: dict[str, Any]) -> list[dict[str, Any]] | None:
    base_candidates = (data["content_topics"] or {}).get("entity_candidates")
    if base_candidates is None:
        return None

    if data["entity_prominence"] is None:
        return base_candidates

    # Build prominence lookup from entity clusters
    prominence_map: dict[str, dict[str, Any]] = {}
    clusters = data["entity_prominence"].get("entity_clusters")
    if isinstance(clusters, list):
        for cluster in clusters:
            if isinstance(cluster.get("entities"), list):
                for entity in cluster["entities"]:
                    prominence_map[entity["entity"].lower()] = {
                        "prominence": entity["prominence"],
                        "prominence_source": entity.get("prominence_source"),
                    }

    result = []
    for candidate in base_candidates:
        prom = prominence_map.get(candidate["term"].lower())
        if prom:
            result.append({
                **candidate,
                "prominence": prom["prominence"],
                "prominence_source": prom["prominence_source"],
            })
        else:
            result.append(candidate)
    return result


def _build_serp_features(data: dict[str, Any]) -> dict[str, bool] | None:
    if data["serp"] is None:
        return None
    features = data["serp"].get("serp_features")
    if features is None:
        return None

    summary: dict[str, bool] = {}
    for key, val in features.items():
        if key in ("ai_overview", "featured_snippet", "knowledge_graph"):
            summary[key] = (val or {}).get("present", False)
        elif isinstance(val, list):
            summary[key] = len(val) > 0
        elif isinstance(val, dict):
            # Signal objects (commercial_signals, local_signals): any True value
            summary[key] = any(v is True for v in val.values())
        else:
            summary[key] = False
    return summary


def _build_competitors(
    data: dict[str, Any], current_year: int,
) -> list[dict[str, Any]] | None:
    if data["competitors_data"] is not None:
        comps = data["competitors_data"].get("competitors", [])
        return normalize_years(comps, current_year)
    if data["serp"] is not None:
        comps = data["serp"].get("competitors", [])
        return normalize_years(comps, current_year)
    return None


def _build_page_structures(data: dict[str, Any]) -> list[dict[str, Any]] | None:
    if data["page_structure"] is None:
        return None
    return data["page_structure"].get("competitors", [])


def _build_content_format_signals(data: dict[str, Any]) -> dict[str, Any] | None:
    if data["content_topics"] is None:
        return None
    return data["content_topics"].get("content_format_signals", {})


def _build_stats_summary(data: dict[str, Any]) -> dict[str, int]:
    source = data["keywords_filtered"] or data["keywords_processed"]
    total_keywords = (source or {}).get("total_keywords", 0)
    filtered_count = (
        data["keywords_filtered"] or {}
    ).get("filtered_keywords", total_keywords)
    cluster_count = (
        len(source["clusters"])
        if source and isinstance(source.get("clusters"), list)
        else 0
    )
    competitor_count = len(
        (data["competitors_data"] or {}).get("competitors")
        or (data["serp"] or {}).get("competitors")
        or []
    )
    return {
        "total_keywords": total_keywords,
        "filtered_keywords": filtered_count,
        "total_clusters": cluster_count,
        "competitor_count": competitor_count,
    }


def _build_keyword_data(
    data: dict[str, Any], current_year: int,
) -> dict[str, Any]:
    clusters = _build_cluster_ranking(data)
    source = data["keywords_filtered"] or data["keywords_processed"]
    total_kw = (source or {}).get("total_keywords", 0)
    filtered = (
        (data["keywords_filtered"] or {}).get("filtered_keywords")
        if data["keywords_filtered"] is not None
        else (source or {}).get("total_keywords", 0)
    )
    return {
        "clusters": normalize_years(clusters, current_year),
        "total_keywords": total_kw,
        "filtered_count": filtered if filtered is not None else total_kw,
        "removal_summary": (data["keywords_filtered"] or {}).get("removal_summary")
        if data["keywords_filtered"] is not None
        else None,
    }


def _build_avg_word_count(data: dict[str, Any]) -> int | float | None:
    if data["page_structure"] is None:
        return None
    cc = data["page_structure"].get("cross_competitor")
    if cc is None:
        return None
    return cc.get("avg_word_count")


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------


def assemble_briefing_data(
    directory: Path,
    *,
    market: str | None = None,
    language: str | None = None,
    user_domain: str | None = None,
    business_context: str | None = None,
    timestamp_override: str | None = None,
) -> dict[str, Any]:
    """Assemble all pipeline outputs into a single briefing-data dict.

    Parameters
    ----------
    directory:
        Path to the output directory containing analysis JSON files.
    market, language, user_domain, business_context:
        Optional metadata flags passed through to the meta section.
    timestamp_override:
        If set, used instead of ``datetime.now()`` for ``phase1_completed_at``.
        Useful for deterministic testing.

    Returns
    -------
    dict
        The assembled briefing data structure.
    """
    data = _load_inputs(directory)

    found = [k for k, v in data.items() if v is not None]
    missing = [k for k, v in data.items() if v is None]
    logger.info(
        "Briefing assembly: found %d/%d input files (missing: %s)",
        len(found),
        len(data),
        ", ".join(missing) if missing else "none",
    )

    date_str = _extract_date_from_dir(directory)
    current_year = int(date_str[:4])

    # Seed keyword from keywords-processed, keywords-filtered, or serp
    seed_keyword = (
        (data["keywords_processed"] or {}).get("seed_keyword")
        or (data["keywords_filtered"] or {}).get("seed_keyword")
        or (data["serp"] or {}).get("target_keyword")
    )

    phase1_completed_at = (
        timestamp_override
        if timestamp_override is not None
        else datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + "000Z"
    )

    module_freq = _build_module_frequency(data)

    return {
        "meta": {
            "seed_keyword": seed_keyword,
            "date": date_str,
            "current_year": current_year,
            "pipeline_version": PIPELINE_VERSION,
            "market": market,
            "language": language,
            "user_domain": user_domain,
            "business_context": business_context,
            "phase1_completed_at": phase1_completed_at,
            "data_sources": {
                "competitor_urls": [
                    c["url"]
                    for c in (data["serp"] or {}).get("competitors", [])
                ],
                "location_code": (
                    ((data["serp_raw"] or {}).get("tasks") or [{}])[0]
                    .get("data", {})
                    .get("location_code")
                ),
            },
        },
        "stats": _build_stats_summary(data),
        "keyword_data": _build_keyword_data(data, current_year),
        "serp_data": {
            "competitors": _build_competitors(data, current_year),
            "serp_features": _build_serp_features(data),
            "aio": _build_aio_data(data, current_year),
        },
        "content_analysis": {
            "proof_keywords": _build_proof_keywords(data, current_year),
            "entity_candidates": _build_entity_candidates(data),
            "section_weights": _build_section_weights(data),
            "content_format_signals": _build_content_format_signals(data),
        },
        "competitor_analysis": {
            "page_structures": _build_page_structures(data),
            "common_modules": module_freq["common_modules"] if module_freq else None,
            "rare_modules": module_freq["rare_modules"] if module_freq else None,
            "avg_word_count": _build_avg_word_count(data),
        },
        "faq_data": _build_faq_data(data, current_year),
        "qualitative": {
            "entity_clusters": None,
            "unique_angles": None,
            "content_format_recommendation": None,
            "geo_audit": None,
            "aio_strategy": None,
            "briefing": None,
        },
    }


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _normalize_tree(obj: Any) -> Any:
    """Recursively apply normalize_number to all numeric values."""
    if isinstance(obj, dict):
        return {k: _normalize_tree(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_tree(v) for v in obj]
    if isinstance(obj, float):
        return normalize_number(obj)
    return obj


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assemble briefing data from pipeline outputs.",
    )
    parser.add_argument(
        "--dir", type=Path, required=True,
        help="Output directory containing analysis JSON files.",
    )
    parser.add_argument("--market", default=None, help="Market identifier.")
    parser.add_argument("--language", default=None, help="Language code.")
    parser.add_argument("--user-domain", default=None, help="User domain.")
    parser.add_argument("--business-context", default=None, help="Business context.")
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output file path (default: <dir>/briefing-data.json).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    result = assemble_briefing_data(
        args.dir,
        market=args.market,
        language=args.language,
        user_domain=args.user_domain,
        business_context=args.business_context,
    )
    output_dict = _normalize_tree(result)
    output_json = json.dumps(output_dict, indent=2, ensure_ascii=False) + "\n"

    output_path = args.output or (args.dir / "briefing-data.json")
    output_path.write_text(output_json, encoding="utf-8")
    print("Wrote briefing-data.json", file=sys.stderr)


if __name__ == "__main__":
    main()
