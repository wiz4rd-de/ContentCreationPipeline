"""Merge and deduplicate keywords from DataForSEO API responses."""

import argparse
import json
import sys
from pathlib import Path

from seo_pipeline.keywords.extract_keywords import extract_keywords


def merge_keywords(related_raw: dict, suggestions_raw: dict, seed: str) -> dict:
    """
    Merge and deduplicate keywords from two DataForSEO API responses.

    Combines keywords from both related_keywords and keyword_suggestions responses,
    deduplicates case-insensitively (preferring related_keywords on collision),
    ensures the seed keyword is always present, and sorts by search_volume
    (descending) with alphabetical tie-breaking.

    Args:
        related_raw: Raw JSON response from related_keywords API
        suggestions_raw: Raw JSON response from keyword_suggestions API
        seed: The seed keyword to ensure is always present

    Returns:
        A dict with keys:
        - seed_keyword: The input seed keyword (trimmed)
        - total_keywords: Count of merged keywords
        - keywords: List of keyword records, each with:
            - keyword (str)
            - search_volume (int | None)
            - cpc (float | None)
            - monthly_searches (list | None)
            - source ('related', 'suggestions', or 'seed')
    """
    # Extract keywords from both sources
    related_keywords = extract_keywords(related_raw)
    suggestions_keywords = extract_keywords(suggestions_raw)

    # Deduplicate case-insensitively, preferring related_keywords on collision
    seen = {}  # lowercase keyword -> merged record

    for kw in related_keywords:
        key = kw["keyword"].lower().strip()
        if key not in seen:
            seen[key] = {**kw, "source": "related"}

    for kw in suggestions_keywords:
        key = kw["keyword"].lower().strip()
        if key not in seen:
            seen[key] = {**kw, "source": "suggestions"}

    # Ensure seed keyword is always included
    seed_key = seed.lower().strip()
    if seed_key not in seen:
        seen[seed_key] = {
            "keyword": seed.strip(),
            "search_volume": None,
            "cpc": None,
            "monthly_searches": None,
            "source": "seed",
        }

    # Stable sort: search_volume desc, then alphabetical tie-break
    merged = list(seen.values())
    merged.sort(
        key=lambda kw: (
            -(kw["search_volume"] if kw["search_volume"] is not None else -1),
            kw["keyword"].lower(),
        )
    )

    # Output
    return {
        "seed_keyword": seed.strip(),
        "total_keywords": len(merged),
        "keywords": merged,
    }


def main() -> None:
    """CLI wrapper for merge_keywords."""
    parser = argparse.ArgumentParser(
        description="Merge and deduplicate keywords from DataForSEO API responses"
    )
    parser.add_argument(
        "--related", required=True, help="Path to related_keywords raw JSON file"
    )
    parser.add_argument(
        "--suggestions", required=True, help="Path to keyword_suggestions raw JSON file"
    )
    parser.add_argument(
        "--seed", required=True, help="Seed keyword to ensure inclusion"
    )

    args = parser.parse_args()

    try:
        related_path = Path(args.related)
        suggestions_path = Path(args.suggestions)

        if not related_path.exists():
            print(f"Error: related file not found: {args.related}", file=sys.stderr)
            sys.exit(1)
        if not suggestions_path.exists():
            print(
                f"Error: suggestions file not found: {args.suggestions}",
                file=sys.stderr,
            )
            sys.exit(1)

        related_raw = json.loads(related_path.read_text(encoding="utf-8"))
        suggestions_raw = json.loads(suggestions_path.read_text(encoding="utf-8"))

        result = merge_keywords(related_raw, suggestions_raw, args.seed)
        print(json.dumps(result, indent=2))

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
