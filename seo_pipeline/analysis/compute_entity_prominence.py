"""Deterministic entity prominence calculator.

Re-computes prominence by counting how many competitor pages mention each
entity's synonyms. Short synonyms (<=4 chars) use word-boundary regex to
avoid false positives; longer synonyms use simple substring matching.

Usage:
    python -m seo_pipeline.analysis.compute_entity_prominence \
        --entities <entities.json> --pages-dir <pages/> [--output path]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

from seo_pipeline.models.analysis import (
    Entity,
    EntityCluster,
    EntityProminence,
    ProminenceCorrection,
    ProminenceDebug,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synonym matching
# ---------------------------------------------------------------------------


def _synonym_appears_in_text(synonym: str, text: str) -> bool:
    """Check if a synonym appears in the (already lowercased) text.

    Short synonyms (length <= 4) use word-boundary regex to avoid false
    positives. Longer synonyms use simple substring containment.
    """
    lower = synonym.lower()
    if len(lower) <= 4:
        escaped = re.escape(lower)
        return re.search(r"\b" + escaped + r"\b", text) is not None
    return lower in text


# ---------------------------------------------------------------------------
# Prominence string parsing
# ---------------------------------------------------------------------------


def _parse_prominence_count(prom_str: str | None) -> int | None:
    """Parse "N/M" prominence string and return N, or None if unparseable."""
    if prom_str is None:
        return None
    match = re.match(r"^(\d+)\s*/\s*\d+$", str(prom_str))
    if match:
        return int(match.group(1))
    return None


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------


def compute_entity_prominence(
    entities_path: Path,
    pages_dir: Path,
) -> EntityProminence:
    """Compute entity prominence from synonym matches across competitor pages.

    Args:
        entities_path: Path to entity clusters JSON file.
        pages_dir: Directory containing extracted page JSON files.

    Returns:
        EntityProminence model with updated prominence values and optional
        debug corrections.
    """
    entities_data: dict[str, Any] = json.loads(
        entities_path.read_text(encoding="utf-8")
    )

    # Load page texts (sorted for determinism)
    page_files = sorted(p for p in pages_dir.iterdir() if p.suffix == ".json")
    page_texts: list[str] = []
    for f in page_files:
        page = json.loads(f.read_text(encoding="utf-8"))
        page_texts.append((page.get("main_content_text") or "").lower())

    total_pages = len(page_texts)

    logger.info(
        "Entity prominence: %d clusters, %d pages",
        len(entities_data.get("entity_clusters", [])),
        total_pages,
    )

    corrections: list[dict[str, Any]] = []
    output_clusters: list[EntityCluster] = []

    for cluster in entities_data["entity_clusters"]:
        output_entities: list[Entity] = []

        for entity in cluster["entities"]:
            synonyms: list[str] = entity.get("synonyms") or []

            # Count pages where any synonym appears
            count = 0
            for text in page_texts:
                for syn in synonyms:
                    if _synonym_appears_in_text(syn, text):
                        count += 1
                        break

            code_prominence = f"{count}/{total_pages}"
            gemini_count = _parse_prominence_count(entity.get("prominence"))
            delta = abs(count - gemini_count) if gemini_count is not None else None

            if delta is not None and delta >= 2:
                corrections.append(
                    {
                        "entity": entity["entity"],
                        "category": cluster["category_name"],
                        "gemini": entity["prominence"],
                        "code": code_prominence,
                        "delta": delta,
                    }
                )

            output_entities.append(
                Entity(
                    entity=entity["entity"],
                    prominence=code_prominence,
                    prominence_gemini=entity.get("prominence"),
                    prominence_source="code",
                    synonyms=synonyms,
                )
            )

        output_clusters.append(
            EntityCluster(
                category_name=cluster["category_name"],
                entities=output_entities,
            )
        )

    logger.info(
        "Entity prominence complete: %d clusters, %d corrections",
        len(output_clusters),
        len(corrections),
    )

    result = EntityProminence(entity_clusters=output_clusters)

    if corrections:
        # Sort deterministically by category, then entity name
        corrections.sort(key=lambda c: (c["category"], c["entity"]))
        result = EntityProminence(
            entity_clusters=output_clusters,
            debug=ProminenceDebug(
                corrections=[ProminenceCorrection(**c) for c in corrections]
            ),
        )

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute entity prominence from synonym matches."
    )
    parser.add_argument(
        "--entities",
        required=True,
        type=Path,
        help="Path to entity clusters JSON file.",
    )
    parser.add_argument(
        "--pages-dir",
        required=True,
        type=Path,
        help="Directory with page JSON files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: stdout).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    result = compute_entity_prominence(args.entities, args.pages_dir)
    output_json = json.dumps(
        result.model_dump(by_alias=True), indent=2, ensure_ascii=False
    )

    if args.output:
        args.output.write_text(output_json, encoding="utf-8")
    else:
        sys.stdout.write(output_json + "\n")


if __name__ == "__main__":
    main()
