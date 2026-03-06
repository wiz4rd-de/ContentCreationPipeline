// Shared keyword extraction from DataForSEO Labs responses.
// Handles both response shapes:
//   - related_keywords: item.keyword_data.keyword / .keyword_info / .keyword_properties
//   - keyword_suggestions: item.keyword / .keyword_info / .keyword_properties (no wrapper)
//
// Deterministic: same input always produces the same output array.

/**
 * Normalize an item from either API shape into a uniform { keyword, info, props } object.
 * Returns null if the item has no keyword string.
 */
function normalizeItem(item) {
  // related_keywords shape: keyword data nested under keyword_data
  if (item?.keyword_data?.keyword) {
    const kd = item.keyword_data;
    return {
      keyword: kd.keyword,
      info: kd.keyword_info || {},
      props: kd.keyword_properties || {},
    };
  }
  // keyword_suggestions shape: keyword data directly on item
  if (item?.keyword) {
    return {
      keyword: item.keyword,
      info: item.keyword_info || {},
      props: item.keyword_properties || {},
    };
  }
  return null;
}

/**
 * Extract keyword records from a DataForSEO Labs response.
 * Works with both related_keywords and keyword_suggestions response shapes.
 *
 * @param {object} raw - The raw JSON response from DataForSEO
 * @param {object} [options]
 * @param {boolean} [options.includeDifficulty=false] - Whether to extract keyword_difficulty
 * @returns {Array<object>} Array of keyword records
 */
export function extractKeywords(raw, options = {}) {
  const { includeDifficulty = false } = options;
  const items = raw?.tasks?.[0]?.result?.[0]?.items;
  if (!Array.isArray(items)) return [];

  const results = [];
  for (const item of items) {
    const normalized = normalizeItem(item);
    if (!normalized) continue;

    const record = {
      keyword: normalized.keyword.trim(),
      search_volume: normalized.info.search_volume ?? null,
      cpc: normalized.info.cpc ?? null,
      monthly_searches: normalized.info.monthly_searches ?? null,
    };

    if (includeDifficulty) {
      const rawDifficulty = normalized.props.keyword_difficulty;
      record.difficulty = rawDifficulty != null
        ? Math.max(0, Math.min(100, Math.round(rawDifficulty)))
        : null;
    }

    results.push(record);
  }

  return results;
}
