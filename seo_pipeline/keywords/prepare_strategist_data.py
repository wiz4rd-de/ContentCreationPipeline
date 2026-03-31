"""Prepare strategist data: consolidate keywords and SERP info for content strategy LLM.

Deterministic data preparation that flattens keyword clusters, deduplicates with
year normalization (2024-2029 -> YYYY), filters foreign-language keywords, and
consolidates SERP features, PAA questions, and competitor keywords into a structured
skeleton for the LLM content strategist step.
"""

import re

from seo_pipeline.utils.math import js_round
from seo_pipeline.utils.text import is_foreign_language


def _year_normalized_key(keyword: str) -> str:
    """Normalize years 2024-2029 to YYYY for dedup purposes.

    Args:
        keyword: The keyword to normalize.

    Returns:
        Normalized keyword with years replaced by yyyy (lowercase).
    """
    normalized = keyword.lower().strip()
    normalized = re.sub(r'\b(202[4-9])\b', 'yyyy', normalized)
    return normalized


def _flatten_keywords(data: dict) -> list[dict]:
    """Flatten keywords from cluster structure into a single list.

    Args:
        data: Keywords data with potential 'clusters' key.

    Returns:
        List of keyword dicts from all clusters.
    """
    if not isinstance(data, dict):
        return []

    clusters = data.get('clusters')
    if clusters is None or not isinstance(clusters, list):
        return []

    result = []
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        keywords = cluster.get('keywords')
        if keywords is None or not isinstance(keywords, list):
            continue
        result.extend(keywords)

    return result


def _deduplicate_with_year_normalization(
    keywords: list[dict],
) -> tuple[list[dict], int]:
    """Deduplicate keywords by year-normalized key, keeping highest volume version.

    On volume tie, uses alphabetical order (case-insensitive) for determinism.

    Args:
        keywords: List of keyword dicts with 'keyword' and optionally 'search_volume'.

    Returns:
        Tuple of (deduped_list, count_of_deduplicated_items).
    """
    dedup_map = {}

    for kw in keywords:
        if not isinstance(kw, dict):
            continue

        norm_key = _year_normalized_key(kw.get('keyword', ''))
        existing = dedup_map.get(norm_key)

        if existing is None:
            dedup_map[norm_key] = kw
        else:
            existing_vol = existing.get('search_volume')
            current_vol = kw.get('search_volume')

            # Treat None/missing as -1 for comparison
            existing_vol = existing_vol if existing_vol is not None else -1
            current_vol = current_vol if current_vol is not None else -1

            if current_vol > existing_vol:
                dedup_map[norm_key] = kw
            elif current_vol == existing_vol:
                # Alphabetical tie-break (case-insensitive)
                existing_kw_lower = existing.get('keyword', '').lower()
                current_kw_lower = kw.get('keyword', '').lower()
                if current_kw_lower < existing_kw_lower:
                    dedup_map[norm_key] = kw

    deduped = list(dedup_map.values())
    dedup_count = len(keywords) - len(deduped)
    return deduped, dedup_count


def _sort_by_volume_desc(keywords: list[dict]) -> list[dict]:
    """Sort keywords by search_volume descending, with alphabetical tie-break.

    Args:
        keywords: List of keyword dicts.

    Returns:
        Sorted list (ascending order is a new list).
    """
    def sort_key(kw):
        vol = kw.get('search_volume')
        vol = vol if vol is not None else -1
        kw_lower = (kw.get('keyword') or '').lower()
        return (-vol, kw_lower)

    return sorted(keywords, key=sort_key)


def _extract_paa_questions(serp_data: dict) -> list[dict]:
    """Extract PAA questions from SERP data.

    Handles both string and object formats for backward compatibility.

    Args:
        serp_data: SERP data with serp_features.people_also_ask.

    Returns:
        List of {question, answer} dicts.
    """
    questions = []
    serp_features = serp_data.get('serp_features')
    if not isinstance(serp_features, dict):
        return questions

    paa_raw = serp_features.get('people_also_ask')
    if not isinstance(paa_raw, list):
        return questions

    for q in paa_raw:
        if isinstance(q, str) and q:
            questions.append({'question': q, 'answer': None})
        elif isinstance(q, dict):
            question = q.get('question')
            if isinstance(question, str) and question:
                questions.append({
                    'question': question,
                    'answer': q.get('answer'),
                })

    return questions


def _extract_serp_snippets(serp_data: dict) -> list[dict]:
    """Extract SERP snippets from competitor data.

    Args:
        serp_data: SERP data with competitors list.

    Returns:
        List of snippet dicts with rank, title, description, url, domain.
    """
    snippets = []
    competitors = serp_data.get('competitors')
    if not isinstance(competitors, list):
        return snippets

    for comp in competitors:
        if not isinstance(comp, dict):
            continue

        # Skip if both title and description are missing
        if comp.get('title') is None and comp.get('description') is None:
            continue

        snippets.append({
            'rank': comp.get('rank'),
            'title': comp.get('title'),
            'description': comp.get('description'),
            'url': comp.get('url'),
            'domain': comp.get('domain'),
        })

    return snippets


def _process_competitor_keywords(comp_kws_data) -> list[dict]:
    """Process competitor keywords with sorting.

    Args:
        comp_kws_data: Raw competitor keywords data (list or None).

    Returns:
        Sorted list of {keyword, search_volume, difficulty} dicts.
    """
    keywords = []
    if not isinstance(comp_kws_data, list):
        return keywords

    for kw in comp_kws_data:
        if not isinstance(kw, dict):
            continue

        # Skip if both keyword and search_volume are missing
        if kw.get('keyword') is None and kw.get('search_volume') is None:
            continue

        keywords.append({
            'keyword': kw.get('keyword'),
            'search_volume': kw.get('search_volume'),
            'difficulty': kw.get('difficulty'),
        })

    # Sort by volume desc, then alphabetically for determinism
    def sort_key(kw):
        vol = kw.get('search_volume')
        vol = vol if vol is not None else -1
        kw_str = kw.get('keyword') or ''
        return (-vol, kw_str.lower())

    return sorted(keywords, key=sort_key)


def _calculate_stats(
    deduped_keywords: list[dict],
    latin_keywords: list[dict],
    all_keywords: list[dict],
    paa_questions: list[dict],
    serp_snippets: list[dict],
    competitor_keywords: list[dict],
    all_raw_keywords: list[dict],
) -> dict:
    """Calculate statistics for the output.

    Args:
        deduped_keywords: Keywords after year-normalization dedup.
        latin_keywords: Keywords after foreign-language filtering.
        all_keywords: Final sorted keywords list (for count).
        paa_questions: PAA questions extracted.
        serp_snippets: SERP snippets extracted.
        competitor_keywords: Competitor keywords.
        all_raw_keywords: Original flat keyword list (before dedup).

    Returns:
        Dict with stats.
    """
    # Volume stats
    volume_values = []
    for kw in latin_keywords:
        vol = kw.get('search_volume')
        if vol is not None and vol > 0:
            volume_values.append(vol)

    total_volume = sum(volume_values)
    avg_volume = (
        js_round(total_volume / len(volume_values))
        if volume_values
        else 0
    )

    # Difficulty stats
    difficulty_values = []
    for kw in latin_keywords:
        diff = kw.get('difficulty')
        if diff is not None:
            difficulty_values.append(diff)

    if difficulty_values:
        avg_diff_raw = sum(difficulty_values) / len(difficulty_values)
        avg_difficulty = js_round(avg_diff_raw * 100) / 100
    else:
        avg_difficulty = None

    return {
        'total_keywords': len(all_keywords),
        'keywords_with_volume': len(volume_values),
        'total_search_volume': total_volume,
        'avg_search_volume': avg_volume,
        'avg_difficulty': avg_difficulty,
        'paa_count': len(paa_questions),
        'serp_snippet_count': len(serp_snippets),
        'competitor_keyword_count': len(competitor_keywords),
        'foreign_filtered_count': len(deduped_keywords) - len(latin_keywords),
        'year_dedup_count': len(all_raw_keywords) - len(deduped_keywords),
    }


def prepare_strategist_data(
    keywords_data: dict,
    serp_data: dict,
    seed_keyword: str,
    competitor_kws_data=None,
) -> dict:
    """Prepare consolidated data for content strategist LLM.

    Flattens keyword clusters, deduplicates with year normalization, filters
    foreign-language keywords, extracts PAA questions and SERP snippets, and
    classifies keywords into top 20, autocomplete, and content ideas.

    Args:
        keywords_data: Processed keywords JSON (from process_keywords).
        serp_data: Processed SERP JSON (from process_serp).
        seed_keyword: Original search seed keyword.
        competitor_kws_data: Optional list of competitor keywords.

    Returns:
        Dict with seed_keyword, top_keywords, all_keywords, autocomplete,
        content_ideas, paa_questions, serp_snippets, competitor_keywords, and stats.
    """
    # Flatten keywords from clusters
    all_raw_keywords = _flatten_keywords(keywords_data)

    # Deduplicate with year normalization
    deduped, year_dedup_count = _deduplicate_with_year_normalization(all_raw_keywords)

    # Filter foreign-language keywords
    latin_keywords = [
        kw for kw in deduped
        if not is_foreign_language(kw.get('keyword', ''))
    ]

    # Sort by volume descending
    sorted_keywords = _sort_by_volume_desc(latin_keywords)

    # Top 20 keywords
    top_keywords = []
    for kw in sorted_keywords[:20]:
        top_keywords.append({
            'keyword': kw.get('keyword'),
            'search_volume': kw.get('search_volume'),
            'difficulty': kw.get('difficulty'),
            'intent': kw.get('intent'),
            'opportunity_score': kw.get('opportunity_score'),
        })

    # All keywords (full sorted list)
    all_keywords = []
    for kw in sorted_keywords:
        all_keywords.append({
            'keyword': kw.get('keyword'),
            'search_volume': kw.get('search_volume'),
            'difficulty': kw.get('difficulty'),
            'intent': kw.get('intent'),
            'opportunity_score': kw.get('opportunity_score'),
        })

    # Classify keywords: autocomplete vs content ideas
    seed_lower = seed_keyword.lower().strip()
    autocomplete = []
    content_ideas = []

    for kw in sorted_keywords:
        kw_lower = (kw.get('keyword') or '').lower().strip()
        if kw_lower == seed_lower:
            continue
        if seed_lower in kw_lower:
            autocomplete.append(kw.get('keyword'))
        else:
            content_ideas.append(kw.get('keyword'))

    # Extract PAA questions and SERP snippets
    paa_questions = _extract_paa_questions(serp_data)
    serp_snippets = _extract_serp_snippets(serp_data)

    # Process competitor keywords
    competitor_keywords = _process_competitor_keywords(competitor_kws_data)

    # Calculate stats
    stats = _calculate_stats(
        deduped,
        latin_keywords,
        all_keywords,
        paa_questions,
        serp_snippets,
        competitor_keywords,
        all_raw_keywords,
    )

    return {
        'seed_keyword': seed_keyword.strip(),
        'top_keywords': top_keywords,
        'all_keywords': all_keywords,
        'autocomplete': autocomplete,
        'content_ideas': content_ideas,
        'paa_questions': paa_questions,
        'serp_snippets': serp_snippets,
        'competitor_keywords': competitor_keywords,
        'stats': stats,
    }
