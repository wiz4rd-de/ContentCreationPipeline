"""Assembles competitor data skeleton by merging SERP + page extractor outputs.

Qualitative fields (format, topics, unique_angle, strengths, weaknesses,
common_themes, content_gaps, opportunities) are set to null for LLM to fill in.

Pure JSON merge with deterministic output. Same input always produces identical
results.

Usage:
    python -m seo_pipeline.serp.assemble_competitors <serp-processed.json> \\
        <pages-dir/> [--date YYYY-MM-DD] [--output path]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


def get_page_fields(page_data: dict | None) -> dict:
    """Extract page extractor fields, defaulting to null if missing or errored.

    Args:
        page_data: Page extractor output dict, or None if not found.

    Returns:
        Dict with word_count, h1, headings, link_count, meta_description fields.
    """
    if page_data is None or page_data.get("error"):
        return {
            "word_count": None,
            "h1": None,
            "headings": None,
            "link_count": None,
            "meta_description": None,
        }
    return {
        "word_count": page_data.get("word_count"),
        "h1": page_data.get("h1"),
        "headings": page_data.get("headings"),
        "link_count": page_data.get("link_count"),
        "meta_description": page_data.get("meta_description"),
    }


def load_page_data(pages_dir: str) -> dict:
    """Load page extractor outputs from directory, keyed by domain.

    Domain is derived from filename without .json extension (e.g.,
    www.example.com.json -> www.example.com).

    Files that fail to parse are skipped silently.

    Args:
        pages_dir: Path to directory containing page JSON files.

    Returns:
        Dict mapping domain (str) to page data (dict).
    """
    page_data = {}
    pages_path = Path(pages_dir)

    if not pages_path.exists():
        return page_data

    for file_path in pages_path.glob("*.json"):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            # Domain is filename without .json extension
            domain = file_path.stem
            page_data[domain] = data
        except (json.JSONDecodeError, OSError):
            # Skip malformed or unreadable files
            pass

    return page_data


def assemble_competitors(
    serp: dict, pages_dir: str, date: str | None = None
) -> dict:
    """Assemble competitor data by merging SERP + page extractor outputs.

    Adds date field and qualitative null placeholders. Each competitor receives
    page fields from the matching domain directory file, or nulls if not found.

    Args:
        serp: SERP processed output dict (from process_serp).
        pages_dir: Path to directory of page JSON files (keyed by domain).
        date: ISO 8601 date string (YYYY-MM-DD). If None, uses today's date.

    Returns:
        Competitors data dict with all fields populated (page fields defaulting
        to null if not found).
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Load all page data from directory
    page_data = load_page_data(pages_dir)

    # Build competitors list with merged fields
    competitors = []
    for comp in serp.get("competitors", []):
        page_fields = get_page_fields(page_data.get(comp["domain"]))

        competitor = {
            # Deterministic fields from SERP
            "rank": comp["rank"],
            "rank_absolute": comp["rank_absolute"],
            "url": comp["url"],
            "domain": comp["domain"],
            "title": comp["title"],
            "description": comp.get("description"),
            "is_featured_snippet": comp["is_featured_snippet"],
            "is_video": comp["is_video"],
            "has_rating": comp["has_rating"],
            "rating": comp.get("rating"),
            "timestamp": comp.get("timestamp"),
            "cited_in_ai_overview": comp["cited_in_ai_overview"],
            # Deterministic fields from page extractor
            "word_count": page_fields["word_count"],
            "h1": page_fields["h1"],
            "headings": page_fields["headings"],
            "link_count": page_fields["link_count"],
            "meta_description": page_fields["meta_description"],
            # Qualitative fields — null placeholders for LLM
            "format": None,
            "topics": None,
            "unique_angle": None,
            "strengths": None,
            "weaknesses": None,
        }
        competitors.append(competitor)

    # Build output with top-level qualitative null placeholders
    output = {
        "target_keyword": serp["target_keyword"],
        "date": date,
        "se_results_count": serp["se_results_count"],
        "location_code": serp["location_code"],
        "language_code": serp["language_code"],
        "item_types_present": serp.get("item_types_present", []),
        "serp_features": serp.get("serp_features", {}),
        "competitors": competitors,
        # Qualitative fields — null placeholders for LLM
        "common_themes": None,
        "content_gaps": None,
        "opportunities": None,
    }

    return output


def main() -> None:
    """CLI entry point: read files and output assembled data."""
    args = sys.argv[1:]

    # Parse positional and flag arguments
    positional = [arg for arg in args if not arg.startswith("--")]
    if len(positional) < 2:
        print(
            "Usage: python -m seo_pipeline.serp.assemble_competitors "
            "<serp-processed.json> <pages-dir/> [--date YYYY-MM-DD] [--output path]",
            file=sys.stderr,
        )
        sys.exit(1)

    serp_file = positional[0]
    pages_dir = positional[1]

    # Parse optional flags
    date = None
    output_path = None

    try:
        date_idx = args.index("--date")
        date = args[date_idx + 1]
    except (ValueError, IndexError):
        pass

    try:
        output_idx = args.index("--output")
        output_path = args[output_idx + 1]
    except (ValueError, IndexError):
        pass

    # Read SERP data
    try:
        serp = json.loads(Path(serp_file).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        print(f"Error reading {serp_file}: {e}", file=sys.stderr)
        sys.exit(1)

    # Assemble competitors
    result = assemble_competitors(serp, pages_dir, date)
    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    # Write output
    if output_path:
        try:
            Path(output_path).write_text(output_json, encoding="utf-8")
        except OSError as e:
            print(f"Error writing to {output_path}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
