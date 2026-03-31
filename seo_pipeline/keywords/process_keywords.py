"""Process keywords: intent classification, Jaccard clustering, opportunity scoring.

Deterministic keyword processor that merges raw DataForSEO responses into a
structured JSON skeleton with intent tags, Jaccard clusters, and null
placeholders for LLM-only fields. Same input always produces byte-identical
output.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from seo_pipeline.keywords.extract_keywords import extract_keywords
from seo_pipeline.utils.math import js_round, normalize_number

# Word-boundary regex patterns for DE + EN intent classification.
# Order matters: first match wins (transactional > commercial > informational).
INTENT_PATTERNS = {
    "transactional": re.compile(
        r"\b(kaufen|buy|price|preis|bestellen|coupon|gutschein|discount|rabatt)\b",
        re.IGNORECASE,
    ),
    "commercial": re.compile(
        r"\b(best|beste|bester|bestes|top|review|vergleich|vs|test|erfahrung|empfehlung)\b",
        re.IGNORECASE,
    ),
    "informational": re.compile(
        r"\b(how|wie|what|was ist|guide|anleitung|tutorial|tipps|lernen)\b",
        re.IGNORECASE,
    ),
}


def build_volume_map(raw: dict) -> dict:
    """Build a case-insensitive lookup from a separate volume API response.

    Expected shape: tasks[0].result[] with keyword, search_volume, cpc.

    Args:
        raw: Raw JSON response from the volume endpoint.

    Returns:
        Dict mapping lowercase keyword to {search_volume, cpc}.
    """
    volume_map: dict[str, dict] = {}
    tasks = raw.get("tasks") if raw else None
    if not isinstance(tasks, list) or not tasks:
        return volume_map

    results = tasks[0].get("result") if isinstance(tasks[0], dict) else None
    if not isinstance(results, list):
        return volume_map

    for item in results:
        if not isinstance(item, dict):
            continue
        kw = item.get("keyword")
        if kw is not None:
            volume_map[str(kw).lower().strip()] = {
                "search_volume": item.get("search_volume"),
                "cpc": item.get("cpc"),
            }

    return volume_map


def classify_intent(keyword: str, brand_list: list[str]) -> str | None:
    """Classify search intent deterministically.

    Checks navigational (brand list) first, then pattern-based classification
    in priority order: transactional > commercial > informational.

    Args:
        keyword: The keyword to classify.
        brand_list: List of lowercase brand strings for navigational detection.

    Returns:
        Intent string or None if no match.
    """
    lower = keyword.lower()

    # Check navigational first (brand list)
    if brand_list:
        for brand in brand_list:
            if brand in lower:
                return "navigational"

    # Check patterns in priority order
    if INTENT_PATTERNS["transactional"].search(lower):
        return "transactional"
    if INTENT_PATTERNS["commercial"].search(lower):
        return "commercial"
    if INTENT_PATTERNS["informational"].search(lower):
        return "informational"

    return None


def tokenize_keyword(keyword: str) -> list[str]:
    """Tokenize a keyword into lowercase word tokens (split on whitespace).

    This is the simple tokenizer used for Jaccard similarity, NOT the
    shared tokenizer from utils (which strips punctuation and single chars).

    Args:
        keyword: The keyword to tokenize.

    Returns:
        List of lowercase tokens.
    """
    return [t for t in keyword.lower().split() if t]


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two token sets.

    Args:
        set_a: First set of tokens.
        set_b: Second set of tokens.

    Returns:
        Jaccard coefficient (0.0 to 1.0).
    """
    intersection = len(set_a & set_b)
    union = len(set_a) + len(set_b) - intersection
    if union == 0:
        return 0.0
    return intersection / union


def compute_opportunity_score(
    volume: int | None, difficulty: int | None
) -> float | None:
    """Compute opportunity score for a keyword.

    Formula: search_volume / (keyword_difficulty + 1), rounded to 2 decimals
    using JavaScript Math.round() semantics.

    Args:
        volume: Search volume (None or 0 yields 0).
        difficulty: Keyword difficulty (None yields None).

    Returns:
        Opportunity score, 0, or None.
    """
    if difficulty is None:
        return None
    if volume is None or volume == 0:
        return 0
    return js_round((volume / (difficulty + 1)) * 100) / 100


def process_keywords(
    related_raw: dict,
    suggestions_raw: dict,
    seed: str,
    volume_raw: dict | None = None,
    brands: list[str] | None = None,
) -> dict:
    """Process keywords with intent classification, Jaccard clustering, and scoring.

    Pipeline:
    1. Extract and deduplicate keywords from related + suggestions (with difficulty)
    2. Merge volume from optional volume endpoint
    3. Stable sort by volume desc, alpha tie-break
    4. Classify search intent
    5. Jaccard clustering (greedy, threshold >= 0.5)
    6. Opportunity scoring and within-cluster re-sort
    7. Build output skeleton

    Args:
        related_raw: Raw JSON from related_keywords API.
        suggestions_raw: Raw JSON from keyword_suggestions API.
        seed: Seed keyword string.
        volume_raw: Optional raw JSON from volume endpoint.
        brands: Optional list of brand strings for navigational intent.

    Returns:
        Dict with seed_keyword, total_keywords, total_clusters, clusters.
    """
    brand_list = [b.lower().strip() for b in (brands or []) if b.strip()]

    # Build volume lookup
    volume_map = build_volume_map(volume_raw) if volume_raw else {}

    # 1. Extract and deduplicate (case-insensitive, trimmed)
    related_keywords = extract_keywords(related_raw, include_difficulty=True)
    suggestions_keywords = extract_keywords(suggestions_raw, include_difficulty=True)

    seen: dict[str, dict] = {}  # lowercase key -> record

    for kw in related_keywords:
        key = kw["keyword"].lower().strip()
        if key not in seen:
            seen[key] = kw

    for kw in suggestions_keywords:
        key = kw["keyword"].lower().strip()
        if key not in seen:
            seen[key] = kw

    # Ensure seed keyword is always present
    seed_key = seed.lower().strip()
    if seed_key not in seen:
        seen[seed_key] = {
            "keyword": seed.strip(),
            "search_volume": None,
            "cpc": None,
            "monthly_searches": None,
        }

    # 2. Merge volume from separate endpoint if available; difficulty comes
    # from extracted keyword records
    merged = []
    for kw in seen.values():
        key = kw["keyword"].lower().strip()
        vol = volume_map.get(key)

        search_volume = (
            vol["search_volume"]
            if vol and vol.get("search_volume") is not None
            else kw.get("search_volume")
        )
        cpc = (
            vol["cpc"]
            if vol and vol.get("cpc") is not None
            else kw.get("cpc")
        )

        merged.append({
            "keyword": kw["keyword"],
            "search_volume": search_volume,
            "cpc": normalize_number(cpc),
            "monthly_searches": kw.get("monthly_searches"),
            "difficulty": kw.get("difficulty"),
        })

    # 3. Stable sort: volume desc, then alphabetical tie-break
    merged.sort(
        key=lambda kw: (
            -(kw["search_volume"] if kw["search_volume"] is not None else -1),
            kw["keyword"].lower(),
        )
    )

    # 4. Tag intent
    for kw in merged:
        kw["intent"] = classify_intent(kw["keyword"], brand_list)

    # 5. Cluster via Jaccard overlap (>= 0.5, greedy to highest-volume keyword)
    # Keywords are already sorted by volume desc, so first keyword in each
    # cluster is the highest-volume one (the cluster representative).
    token_sets = [set(tokenize_keyword(kw["keyword"])) for kw in merged]
    cluster_assignment = [-1] * len(merged)
    next_cluster_id = 0

    for i in range(len(merged)):
        if cluster_assignment[i] != -1:
            continue

        # Start a new cluster with this keyword as representative
        cluster_id = next_cluster_id
        next_cluster_id += 1
        cluster_assignment[i] = cluster_id

        # Greedily assign unassigned keywords with Jaccard >= 0.5
        for j in range(i + 1, len(merged)):
            if cluster_assignment[j] != -1:
                continue
            if jaccard_similarity(token_sets[i], token_sets[j]) >= 0.5:
                cluster_assignment[j] = cluster_id

    # Group into cluster objects
    cluster_map: dict[int, dict] = {}  # cluster_id -> {rep_idx, members}
    for i in range(len(merged)):
        cid = cluster_assignment[i]
        if cid not in cluster_map:
            cluster_map[cid] = {"rep_idx": i, "members": []}
        cluster_map[cid]["members"].append(i)

    # Build cluster array (already in order since we iterate merged in volume-desc)
    clusters = []
    for info in cluster_map.values():
        representative = merged[info["rep_idx"]]
        keywords = [merged[idx] for idx in info["members"]]

        clusters.append({
            "cluster_keyword": representative["keyword"],
            "cluster_label": None,
            "strategic_notes": None,
            "keyword_count": len(keywords),
            "keywords": keywords,
        })

    # 6. Opportunity score per keyword + re-sort within clusters
    for cluster in clusters:
        # Compute scores
        for kw in cluster["keywords"]:
            kw["opportunity_score"] = compute_opportunity_score(
                kw["search_volume"], kw["difficulty"]
            )

        # Re-sort: score desc, then volume desc, then alphabetical tie-break
        cluster["keywords"].sort(
            key=lambda kw: (
                -(
                    kw["opportunity_score"]
                    if kw["opportunity_score"] is not None
                    else -1
                ),
                -(kw["search_volume"] if kw["search_volume"] is not None else -1),
                kw["keyword"].lower(),
            )
        )

        # Cluster-level aggregate: average of all scores
        # (nulls count as 0 in sum, but still count toward cluster size)
        score_sum = sum(
            kw["opportunity_score"] if kw["opportunity_score"] is not None else 0
            for kw in cluster["keywords"]
        )
        cluster["cluster_opportunity"] = normalize_number(
            js_round((score_sum / len(cluster["keywords"])) * 100) / 100
            if cluster["keywords"]
            else 0
        )

    # 7. Output JSON skeleton
    return {
        "seed_keyword": seed.strip(),
        "total_keywords": len(merged),
        "total_clusters": len(clusters),
        "clusters": clusters,
    }


def main() -> None:
    """CLI wrapper for process_keywords."""
    parser = argparse.ArgumentParser(
        description="Process keywords with intent, Jaccard clustering, and scoring"
    )
    parser.add_argument(
        "--related", required=True, help="Path to related_keywords raw JSON file"
    )
    parser.add_argument(
        "--suggestions",
        required=True,
        help="Path to keyword_suggestions raw JSON file",
    )
    parser.add_argument(
        "--seed", required=True, help="Seed keyword"
    )
    parser.add_argument(
        "--volume", default=None, help="Path to volume raw JSON file (optional)"
    )
    parser.add_argument(
        "--brands", default=None, help="Comma-separated brand list (optional)"
    )
    parser.add_argument(
        "--output", default=None, help="Output file path (default: stdout)"
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

        with open(related_path, encoding="utf-8") as f:
            related_raw = json.load(f)
        with open(suggestions_path, encoding="utf-8") as f:
            suggestions_raw = json.load(f)

        volume_raw = None
        if args.volume:
            volume_path = Path(args.volume)
            if not volume_path.exists():
                print(
                    f"Error: volume file not found: {args.volume}", file=sys.stderr
                )
                sys.exit(1)
            with open(volume_path, encoding="utf-8") as f:
                volume_raw = json.load(f)

        brands = None
        if args.brands:
            brands = [b.strip() for b in args.brands.split(",") if b.strip()]

        result = process_keywords(
            related_raw, suggestions_raw, args.seed,
            volume_raw=volume_raw, brands=brands,
        )

        output_json = json.dumps(result, indent=2)
        if args.output:
            Path(args.output).write_text(output_json, encoding="utf-8")
        else:
            print(output_json)

    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
