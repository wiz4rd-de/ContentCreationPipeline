"""Extract and normalize keyword data from DataForSEO API responses."""

from seo_pipeline.utils.math import js_round


def normalize_item(item: dict) -> dict | None:
    """
    Normalize an item from either DataForSEO API response shape.

    DataForSEO provides two response shapes:
    1. related_keywords: keyword data nested under item.keyword_data
    2. keyword_suggestions: keyword data directly on item

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

    items = result_item.get("items")

    if not isinstance(items, list):
        return []

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

    return results
