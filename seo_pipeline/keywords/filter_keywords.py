"""Filter keywords: blocklist, brand, foreign-language filtering.

Deterministic keyword filter that applies blocklist, brand, and foreign-language
filtering to processed keyword data. Keywords are tagged with filter_status and
filter_reason (not deleted) to preserve the audit trail.

Also computes FAQ prioritization by scoring PAA questions against keyword overlaps.
"""

import json
import re
from pathlib import Path

from seo_pipeline.utils.text import is_foreign_language


def _load_blocklist(blocklist_path: str | None = None) -> dict[str, list[str]]:
    """Load blocklist from file (custom or default).

    Args:
        blocklist_path: Path to custom blocklist JSON. If None, uses default.

    Returns:
        Dict mapping category to list of blocked terms.
    """
    if blocklist_path:
        with open(blocklist_path, encoding="utf-8") as f:
            return json.load(f)

    # Use default blocklist
    default_path = Path(__file__).parent.parent / "data" / "blocklist_default.json"
    with open(default_path, encoding="utf-8") as f:
        return json.load(f)


def _build_blocklist_entries(blocklist: dict) -> list[dict]:
    """Build flat blocklist lookup with deterministic ordering.

    Maps each term to its category for efficient lookup and reason tagging.
    Sorts by category + term for deterministic first-match behavior.

    Args:
        blocklist: Dict mapping category to list of terms.

    Returns:
        List of {term, category} dicts sorted by category then term.
    """
    entries = []
    for category, terms in blocklist.items():
        if isinstance(terms, list):
            for term in terms:
                entries.append({"term": term.lower(), "category": category})

    # Sort for deterministic first-match behavior
    entries.sort(key=lambda e: (e["category"], e["term"]))
    return entries


def _category_to_reason(category: str) -> str:
    """Map blocklist category to filter_reason.

    Args:
        category: Blocklist category name.

    Returns:
        Filter reason: "ethics" or "off_topic".
    """
    if category == "ethics":
        return "ethics"
    return "off_topic"


def _filter_keyword(
    kw: dict, blocklist_entries: list[dict], brand_list: list[str]
) -> dict:
    """Filter a single keyword and return filter status and reason.

    Args:
        kw: Keyword dict with 'keyword' key.
        blocklist_entries: List of blocklist entries sorted by category + term.
        brand_list: List of brand names to filter (case-insensitive).

    Returns:
        Dict with 'filter_status' ('keep' or 'removed') and 'filter_reason'
        ('ethics', 'brand', 'off_topic', 'foreign_language', or None).
    """
    kw_lower = kw["keyword"].lower()

    # 1. Check blocklist (case-insensitive substring match)
    for entry in blocklist_entries:
        if entry["term"] in kw_lower:
            reason = _category_to_reason(entry["category"])
            return {"filter_status": "removed", "filter_reason": reason}

    # 2. Check brands (case-insensitive substring match)
    for brand in brand_list:
        if brand in kw_lower:
            return {"filter_status": "removed", "filter_reason": "brand"}

    # 3. Foreign-language heuristic
    if is_foreign_language(kw["keyword"]):
        return {"filter_status": "removed", "filter_reason": "foreign_language"}

    return {"filter_status": "keep", "filter_reason": None}


def _tokenize_question(question: str) -> list[str]:
    """Tokenize question for FAQ scoring.

    Splits on whitespace and removes punctuation from tokens.

    Args:
        question: Question string to tokenize.

    Returns:
        List of tokens (lowercase, punctuation removed).
    """
    question_lower = question.lower()
    # Strip punctuation from tokens for matching (e.g. "Thailand?" -> "thailand")
    tokens = question_lower.split()
    cleaned = []
    for token in tokens:
        # Remove non-alphanumeric + hyphen + accented chars
        cleaned_token = re.sub(r"[^a-z\u00e0-\u024f\u1e00-\u1eff0-9\-]", "", token)
        if cleaned_token:
            cleaned.append(cleaned_token)
    return cleaned


def _assign_priority(index: int, total: int) -> str:
    """Assign priority tier based on position in ranked list.

    Top 30% = pflicht, 30-70% = empfohlen, bottom 30% = optional.

    Args:
        index: Position in list (0-indexed).
        total: Total number of items.

    Returns:
        Priority tier: "pflicht", "empfohlen", or "optional".
    """
    if total == 0:
        return "optional"
    position = index / total
    if position < 0.3:
        return "pflicht"
    if position < 0.7:
        return "empfohlen"
    return "optional"


def filter_keywords(
    keywords_data: dict,
    serp_data: dict,
    seed_keyword: str,
    blocklist_path: str | None = None,
    brands: str | None = None,
) -> dict:
    """Filter keywords by blocklist, brand, and foreign-language criteria.

    Also computes FAQ prioritization by scoring PAA questions against keyword overlaps.

    Args:
        keywords_data: Processed keywords JSON (from process_keywords).
        serp_data: Processed SERP JSON (from process_serp).
        seed_keyword: Original search seed keyword.
        blocklist_path: Optional path to custom blocklist JSON.
        brands: Optional comma-separated list of brand names to filter.

    Returns:
        Dict with:
        - seed_keyword: The seed keyword
        - total_keywords: Total keywords before filtering
        - filtered_keywords: Keywords kept after filtering
        - removed_count: Keywords removed
        - removal_summary: Count by removal reason
        - clusters: Clusters with tagged keywords
        - faq_selection: Scored and prioritized FAQ questions
    """
    # Load blocklist and parse brands
    blocklist = _load_blocklist(blocklist_path)
    blocklist_entries = _build_blocklist_entries(blocklist)

    brand_list = []
    if brands:
        brand_list = [b.strip().lower() for b in brands.split(",") if b.strip()]

    # Initialize counters
    removal_summary = {"ethics": 0, "brand": 0, "off_topic": 0, "foreign_language": 0}
    total_keywords = 0
    removed_count = 0

    # Filter keywords in clusters
    clusters = []
    if isinstance(keywords_data.get("clusters"), list):
        for cluster in keywords_data["clusters"]:
            tagged_keywords = []
            if isinstance(cluster.get("keywords"), list):
                for kw in cluster["keywords"]:
                    total_keywords += 1
                    filter_result = _filter_keyword(kw, blocklist_entries, brand_list)
                    if filter_result["filter_status"] == "removed":
                        removed_count += 1
                        if filter_result["filter_reason"]:
                            removal_summary[filter_result["filter_reason"]] += 1

                    tagged_kw = {**kw, **filter_result}
                    tagged_keywords.append(tagged_kw)

            clusters.append(
                {
                    "cluster_keyword": cluster.get("cluster_keyword"),
                    "cluster_label": cluster.get("cluster_label"),
                    "strategic_notes": cluster.get("strategic_notes"),
                    "keyword_count": cluster.get("keyword_count", len(tagged_keywords)),
                    "keywords": tagged_keywords,
                    "cluster_opportunity": cluster.get("cluster_opportunity"),
                }
            )

    filtered_keywords = total_keywords - removed_count

    # --- FAQ prioritization ---
    # Score PAA questions by counting keyword token overlaps.
    # Only consider "keep" keywords for scoring.

    keep_keywords = []
    for cluster in clusters:
        for kw in cluster["keywords"]:
            if kw["filter_status"] == "keep":
                keep_keywords.append(kw["keyword"].lower())

    # Tokenize keywords into individual words for overlap matching
    keep_tokens = set()
    for kw in keep_keywords:
        for token in kw.split():
            if token:
                keep_tokens.add(token)

    # Extract PAA questions from serp data
    paa_raw = serp_data.get("serp_features", {}).get("people_also_ask")
    paa_questions = []
    if isinstance(paa_raw, list):
        for q in paa_raw:
            if isinstance(q, str) and q:
                paa_questions.append(
                    {"question": q, "answer": None, "url": None, "domain": None}
                )
            elif (
                isinstance(q, dict)
                and isinstance(q.get("question"), str)
                and q["question"]
            ):
                paa_questions.append(
                    {
                        "question": q["question"],
                        "answer": q.get("answer"),
                        "url": q.get("url"),
                        "domain": q.get("domain"),
                    }
                )

    # Score each question by keyword token overlaps
    scored_faqs = []
    for paa in paa_questions:
        question_tokens = _tokenize_question(paa["question"])
        score = sum(1 for token in question_tokens if token in keep_tokens)
        scored_faqs.append({"question": paa["question"], "relevance_score": score})

    # Sort by relevance_score descending, then alphabetical for determinism
    scored_faqs.sort(key=lambda x: (-x["relevance_score"], x["question"]))

    # Assign priority tiers
    faq_selection = [
        {
            "question": faq["question"],
            "priority": _assign_priority(idx, len(scored_faqs)),
            "relevance_score": faq["relevance_score"],
        }
        for idx, faq in enumerate(scored_faqs)
    ]

    # --- Build output ---

    return {
        "seed_keyword": seed_keyword.strip(),
        "total_keywords": total_keywords,
        "filtered_keywords": filtered_keywords,
        "removed_count": removed_count,
        "removal_summary": removal_summary,
        "clusters": clusters,
        "faq_selection": faq_selection,
    }
