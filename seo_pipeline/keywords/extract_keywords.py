"""Extract and normalize keyword data from DataForSEO API responses."""

import logging

from seo_pipeline.utils.math import js_round

logger = logging.getLogger(__name__)


def normalize_item(item: dict) -> dict | None:
    """
    Normalize an item from any DataForSEO keyword API response shape.

    DataForSEO provides three response shapes:
    1. related_keywords: keyword data nested under item.keyword_data
    2. keywords_for_keywords (Google Ads): flat structure with search_volume,
       cpc, monthly_searches at top level (no keyword_info wrapper)
    3. keyword_suggestions: keyword data directly on item with keyword_info

    Args:
        item: A keyword item from the DataForSEO API response

    Returns:
        A dict with normalized keys (keyword, info, props) or None if no keyword found
    """
    if not item:
        return None

    # related_keywords shape: keyword data nested under keyword_data
    kd = item.get("keyword_data")
    if isinstance(kd, dict) and kd.get("keyword"):
        return {
            "keyword": kd["keyword"],
            "info": kd.get("keyword_info") or {},
            "props": kd.get("keyword_properties") or {},
        }

    # keywords_for_keywords (Google Ads) flat shape: search_volume at top
    # level instead of nested under keyword_info. Must be checked before the
    # suggestions branch because both have a top-level "keyword" key.
    if item.get("keyword") and "search_volume" in item and "keyword_info" not in item:
        return {
            "keyword": item["keyword"],
            "info": item,
            "props": {},
        }

    # keyword_suggestions shape: keyword data directly on item
    if item.get("keyword"):
        return {
            "keyword": item["keyword"],
            "info": item.get("keyword_info") or {},
            "props": item.get("keyword_properties") or {},
        }

    return None


def extract_keywords(
    raw: dict, include_difficulty: bool = False
) -> list[dict]:
    """
    Extract keyword records from a DataForSEO Labs API response.

    Works with both related_keywords and keyword_suggestions response shapes.
    Normalizes each item and extracts keyword data into uniform records.

    Args:
        raw: The raw JSON response from DataForSEO API
        include_difficulty: Whether to extract keyword_difficulty (default: False)

    Returns:
        A list of keyword record dicts with keys:
        - keyword (str)
        - search_volume (int | None)
        - cpc (float | None)
        - monthly_searches (list | None)
        - difficulty (int | None) - only if include_difficulty=True
    """
    # Extract items from the standard response path, safely handling empty lists
    tasks = raw.get("tasks", [])
    if not tasks or not isinstance(tasks, list):
        return []

    task = tasks[0]
    if not isinstance(task, dict):
        return []

    result = task.get("result", [])
    if not result or not isinstance(result, list):
        return []

    result_item = result[0]
    if not isinstance(result_item, dict):
        return []

    # KFK (Google Ads) responses have keywords directly in result (no "items"
    # wrapper).  Detect by checking for a top-level "keyword" key on the first
    # result entry.
    if "items" not in result_item and "keyword" in result_item:
        items = result
    else:
        items = result_item.get("items")

    if not isinstance(items, list):
        return []

    logger.info("Extracting keywords from %d raw items", len(items))

    results = []
    for item in items:
        normalized = normalize_item(item)
        if not normalized:
            continue

        record = {
            "keyword": normalized["keyword"].strip(),
            "search_volume": normalized["info"].get("search_volume"),
            "cpc": normalized["info"].get("cpc"),
            "monthly_searches": normalized["info"].get("monthly_searches"),
        }

        if include_difficulty:
            raw_difficulty = normalized["props"].get("keyword_difficulty")
            if raw_difficulty is not None:
                # Clamp to [0, 100] and round using JavaScript semantics
                clamped = max(0, min(100, raw_difficulty))
                record["difficulty"] = js_round(clamped)
            else:
                record["difficulty"] = None

        results.append(record)

    logger.info("Extracted %d keywords from %d items", len(results), len(items))
    return results
