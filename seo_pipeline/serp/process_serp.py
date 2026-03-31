"""Deterministic SERP parser for DataForSEO advanced endpoint responses.

Extracts structured data from raw SERP JSON. Same input always produces
identical output. This is a pure transform -- no network calls, no LLM.

Usage:
    python -m seo_pipeline.serp.process_serp <raw-serp.json> [--top N] [--output path]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def clean_aio_text(text: str) -> str:
    """Clean AI Overview text encoding artifacts.

    Conservative: only fixes known patterns from DataForSEO responses.
    Steps:
      1. Remove zero-width characters (U+200B, U+200C, U+200D, U+FEFF)
      2. Degree symbol normalization (ring operator -> degree sign)
      3. HTML entity leftovers (&amp; &nbsp; &lt; &gt;)
      4. Collapse multiple spaces (preserve newlines)
      5. Trim leading/trailing whitespace per line
      6. Collapse consecutive blank lines
    """
    # 1. Remove zero-width characters
    text = re.sub("[\u200b\u200c\u200d\ufeff]", "", text)

    # 2. Degree symbol normalization: "23 ∘ C" / "23 ∘C" -> "23 °C"
    text = re.sub(r"\s*[\u2218\u00b0]\s*([CF])\b", r" °\1", text)

    # 3. HTML entity leftovers
    text = text.replace("&amp;", "&")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")

    # 4. Collapse multiple spaces (but preserve newlines)
    text = re.sub(r"[^\S\n]+", " ", text)

    # 5. Trim leading/trailing whitespace per line
    text = "\n".join(line.strip() for line in text.split("\n"))

    # 6. Collapse consecutive blank lines (3+ newlines -> 2)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


def _items_by_type(items: list[dict], item_type: str) -> list[dict]:
    """Filter items list by type field."""
    return [i for i in items if i.get("type") == item_type]


def _extract_ai_overview(items: list[dict]) -> dict:
    """Extract AI Overview data from SERP items."""
    ai_items = _items_by_type(items, "ai_overview")
    if not ai_items:
        return {
            "present": False,
            "title": None,
            "text": None,
            "references": [],
            "references_count": 0,
        }

    item = ai_items[0]
    title = item.get("title") or None

    text_parts: list[str] = []
    seen_refs: set[str] = set()
    references: list[dict] = []

    if item.get("items"):
        for element in item["items"]:
            # Gather text from nested sub-items
            if element.get("items"):
                for sub in element["items"]:
                    txt = (
                        sub.get("description")
                        or sub.get("content")
                        or sub.get("text")
                    )
                    if txt:
                        text_parts.append(txt)
            # Also check the element itself for text
            elem_txt = (
                element.get("description")
                or element.get("content")
                or element.get("text")
            )
            if elem_txt:
                text_parts.append(elem_txt)

            if element.get("references"):
                for ref in element["references"]:
                    key = ref.get("url") or ref.get("domain")
                    if key and key not in seen_refs:
                        seen_refs.add(key)
                        references.append({
                            "domain": ref.get("domain") or None,
                            "url": ref.get("url") or None,
                            "title": ref.get("title") or None,
                        })

    text = clean_aio_text("\n".join(text_parts)) if text_parts else None

    # Field order matches JS: present, references, title, text, references_count
    return {
        "present": True,
        "references": references,
        "title": title,
        "text": text,
        "references_count": len(references),
    }


def _extract_featured_snippet(items: list[dict]) -> dict:
    """Extract featured snippet data from SERP items."""
    organic = _items_by_type(items, "organic")
    snippet = next((i for i in organic if i.get("is_featured_snippet") is True), None)
    if snippet is None:
        # Check for dedicated featured_snippet type
        dedicated = _items_by_type(items, "featured_snippet")
        if not dedicated:
            return {"present": False}
        d = dedicated[0]
        fs = d.get("featured_snippet") or {}
        return {
            "present": True,
            "format": fs.get("type") or None,
            "source_domain": d.get("domain") or None,
            "source_url": d.get("url") or None,
        }
    fs = snippet.get("featured_snippet") or {}
    return {
        "present": True,
        "format": fs.get("type") or None,
        "source_domain": snippet.get("domain") or None,
        "source_url": snippet.get("url") or None,
    }


def _extract_people_also_ask(items: list[dict]) -> list[dict]:
    """Extract People Also Ask questions from SERP items."""
    paa_items = _items_by_type(items, "people_also_ask")
    questions: list[dict] = []
    for paa in paa_items:
        if paa.get("items"):
            for q in paa["items"]:
                if q.get("title") is None:
                    continue
                expanded_element = q.get("expanded_element")
                expanded = (
                    expanded_element[0]
                    if isinstance(expanded_element, list) and len(expanded_element) > 0
                    else None
                )
                questions.append({
                    "question": q["title"],
                    "answer": (
                        (expanded.get("description") or None)
                        if expanded else None
                    ),
                    "url": (expanded.get("url") or None) if expanded else None,
                    "domain": (expanded.get("domain") or None) if expanded else None,
                })
    return questions


def _extract_people_also_search(items: list[dict]) -> list[str]:
    """Extract People Also Search queries from SERP items."""
    pas_items = _items_by_type(items, "people_also_search")
    queries: list[str] = []
    for pas in pas_items:
        if pas.get("items"):
            for q in pas["items"]:
                if isinstance(q, str):
                    queries.append(q)
    return queries


def _extract_related_searches(items: list[dict]) -> list[str]:
    """Extract related search queries from SERP items."""
    rs_items = _items_by_type(items, "related_searches")
    queries: list[str] = []
    for rs in rs_items:
        if rs.get("items"):
            for q in rs["items"]:
                if isinstance(q, str):
                    queries.append(q)
    return queries


def _extract_discussions(items: list[dict]) -> list[dict]:
    """Extract discussions and forums from SERP items."""
    disc_items = _items_by_type(items, "discussions_and_forums")
    results: list[dict] = []
    for d in disc_items:
        if d.get("items"):
            for item in d["items"]:
                results.append({
                    "source": item.get("domain") or item.get("source") or None,
                    "url": item.get("url") or None,
                    "title": item.get("title") or None,
                })
        else:
            results.append({
                "source": d.get("domain") or d.get("source") or None,
                "url": d.get("url") or None,
                "title": d.get("title") or None,
            })
    return results


def _extract_video(items: list[dict]) -> list[dict]:
    """Extract video results from SERP items."""
    video_items = _items_by_type(items, "video")
    results: list[dict] = []
    for v in video_items:
        if v.get("items"):
            for item in v["items"]:
                results.append({
                    "title": item.get("title") or None,
                    "url": item.get("url") or None,
                    "source": item.get("domain") or item.get("source") or None,
                })
        else:
            results.append({
                "title": v.get("title") or None,
                "url": v.get("url") or None,
                "source": v.get("domain") or v.get("source") or None,
            })
    return results


def _extract_top_stories(items: list[dict]) -> list[dict]:
    """Extract top stories from SERP items."""
    ts_items = _items_by_type(items, "top_stories")
    results: list[dict] = []
    for ts in ts_items:
        if ts.get("items"):
            for item in ts["items"]:
                results.append({
                    "title": item.get("title") or None,
                    "url": item.get("url") or None,
                    "source": item.get("domain") or item.get("source") or None,
                })
        else:
            results.append({
                "title": ts.get("title") or None,
                "url": ts.get("url") or None,
                "source": ts.get("domain") or ts.get("source") or None,
            })
    return results


def _extract_knowledge_graph(items: list[dict]) -> dict:
    """Extract knowledge graph data from SERP items."""
    kg_items = _items_by_type(items, "knowledge_graph")
    if not kg_items:
        return {"present": False}
    kg = kg_items[0]
    return {
        "present": True,
        "title": kg.get("title") or None,
        "description": kg.get("description") or None,
    }


def _extract_commercial_signals(items: list[dict]) -> dict:
    """Extract commercial intent signals from SERP items."""
    types = {i.get("type") for i in items}
    return {
        "paid_ads_present": "paid" in types,
        "shopping_present": "shopping" in types,
        "commercial_units_present": "commercial_units" in types,
        "popular_products_present": "popular_products" in types,
    }


def _extract_local_signals(items: list[dict]) -> dict:
    """Extract local search signals from SERP items."""
    types = {i.get("type") for i in items}
    return {
        "local_pack_present": "local_pack" in types,
        "map_present": "map" in types,
        "hotels_pack_present": "hotels_pack" in types,
    }


def _extract_other_features(items: list[dict]) -> list[str]:
    """Extract feature types not handled by dedicated extractors."""
    dedicated_types = {
        "organic", "ai_overview", "featured_snippet",
        "people_also_ask", "people_also_search", "related_searches",
        "discussions_and_forums", "video", "top_stories", "knowledge_graph",
        "paid", "shopping", "commercial_units", "popular_products",
        "local_pack", "map", "hotels_pack",
    }
    present: set[str] = set()
    for item in items:
        item_type = item.get("type")
        if item_type and item_type not in dedicated_types:
            present.add(item_type)
    return sorted(present)


def _extract_competitors(
    items: list[dict],
    ai_overview: dict,
    top_n: int,
) -> list[dict]:
    """Extract organic competitor results with AIO citation cross-reference."""
    organic_items = _items_by_type(items, "organic")
    ai_domains: set[str] = set()
    if ai_overview.get("present") and ai_overview.get("references"):
        for ref in ai_overview["references"]:
            if ref.get("domain"):
                ai_domains.add(ref["domain"])

    competitors: list[dict] = []
    for item in organic_items[:top_n]:
        rating = item.get("rating")
        competitors.append({
            "rank": item.get("rank_group"),
            "rank_absolute": item.get("rank_absolute"),
            "url": item.get("url") or None,
            "domain": item.get("domain") or None,
            "title": item.get("title") or None,
            "description": item.get("description") or None,
            "is_featured_snippet": item.get("is_featured_snippet") is True,
            "is_video": item.get("is_video") is True,
            "has_rating": rating is not None,
            "rating": {
                "value": rating.get("value"),
                "votes_count": rating.get("votes_count"),
                "rating_max": rating.get("rating_max"),
            } if rating else None,
            "timestamp": item.get("timestamp") or None,
            "cited_in_ai_overview": (
                item.get("domain") in ai_domains
                if item.get("domain") else False
            ),
        })
    return competitors


def process_serp(raw: dict, top_n: int = 10) -> dict:
    """Process raw DataForSEO SERP response into structured output.

    Args:
        raw: Raw JSON response from DataForSEO advanced endpoint.
        top_n: Maximum number of organic competitors to include.

    Returns:
        Structured dict matching the process-serp golden output format.

    Raises:
        ValueError: If no result found at tasks[0].result[0].
    """
    tasks = raw.get("tasks") or []
    result = (
        ((tasks[0].get("result") or [])[0])
        if tasks and (tasks[0].get("result"))
        else None
    )
    if result is None:
        msg = "No result found at tasks[0].result[0]"
        raise ValueError(msg)

    items = result.get("items") or []

    ai_overview = _extract_ai_overview(items)

    return {
        "target_keyword": result.get("keyword"),
        "se_results_count": result.get("se_results_count"),
        "location_code": result.get("location_code"),
        "language_code": result.get("language_code"),
        "item_types_present": result.get("item_types") or [],
        "serp_features": {
            "ai_overview": ai_overview,
            "featured_snippet": _extract_featured_snippet(items),
            "people_also_ask": _extract_people_also_ask(items),
            "people_also_search": _extract_people_also_search(items),
            "related_searches": _extract_related_searches(items),
            "discussions_and_forums": _extract_discussions(items),
            "video": _extract_video(items),
            "top_stories": _extract_top_stories(items),
            "knowledge_graph": _extract_knowledge_graph(items),
            "commercial_signals": _extract_commercial_signals(items),
            "local_signals": _extract_local_signals(items),
            "other_features_present": _extract_other_features(items),
        },
        "competitors": _extract_competitors(items, ai_overview, top_n),
    }


def main() -> None:
    """CLI entry point for process_serp."""
    parser = argparse.ArgumentParser(
        description="Extract structured data from raw DataForSEO SERP JSON"
    )
    parser.add_argument(
        "input_file", nargs="?", default=None, help="Path to raw SERP JSON file"
    )
    parser.add_argument(
        "--top", type=int, default=10, help="Number of top competitors (default: 10)"
    )
    parser.add_argument("--output", help="Path to write output JSON file")

    args = parser.parse_args()

    if not args.input_file:
        parser.print_usage(sys.stderr)
        sys.exit(1)

    raw = json.loads(Path(args.input_file).read_text(encoding="utf-8"))

    try:
        output = process_serp(raw, top_n=args.top)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    json_str = json.dumps(output, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(json_str, encoding="utf-8")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
