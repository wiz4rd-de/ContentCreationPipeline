---
name: seo-keyword-research
description: Retrieve keyword data from the configured SEO API and produce a structured keyword report. Use when the user wants to research keywords, find search volumes, or explore keyword opportunities.
---

# SEO Keyword Research

Retrieve keyword data from the configured SEO API and produce a structured keyword report.

## Inputs

Ask the user for:
1. **Seed keyword or topic** (required)
2. **Target market** (default: from `SEO_MARKET` in config)
3. **Number of keywords to return** (default: 30)

## Steps

### 1. Load API config

```sh
source api.env
```

If `api.env` does not exist, tell the user to create it from the example:
```
cp api.env.example api.env
```

### 2. Call the keyword API

Adapt URL, auth header, and payload to `$SEO_PROVIDER` — see `api.env.example` for provider-specific endpoints and credentials.

```sh
# Example (DataForSEO). Adapt for your provider.
curl -s -X POST "$DATAFORSEO_BASE/keywords_data/google_ads/search_volume/live" \
  -H "Authorization: Basic $DATAFORSEO_AUTH" \
  -H "Content-Type: application/json" \
  -d '[{"keywords": ["<SEED_KEYWORD>"], "language_code": "'"$SEO_LANGUAGE"'", "location_code": <LOCATION_CODE>}]' \
  | jq '.tasks[0].result'
```

> `location_code` is derived from `$SEO_MARKET` (e.g. `de` → 2276 for Germany). Refer to your provider's docs for the full mapping.

### 3. Parse and structure the results

From the API response, extract and organize into a table:

| Keyword | Search Volume | Keyword Difficulty | CPC | Search Intent |
|---------|--------------|-------------------|-----|---------------|
| ...     | ...          | ...               | ... | ...           |

Classify search intent as: **informational**, **navigational**, **commercial**, or **transactional**.

If the API does not return intent data, infer it from the keyword phrasing:
- "how to", "what is", "guide" → informational
- "best", "top", "review", "vs" → commercial
- "buy", "price", "discount", "coupon" → transactional
- brand names, specific product names → navigational

### 4. Group into clusters

Group related keywords into topical clusters. For each cluster, note:
- Primary keyword (highest volume)
- Supporting keywords
- Dominant intent

### 5. Save output

Write the structured results to:
```
output/YYYY-MM-DD_<SEED_KEYWORD_SLUG>/keywords-<SEED_KEYWORD_SLUG>.json
```

JSON schema:
```json
{
  "seed_keyword": "...",
  "market": "...",
  "date": "YYYY-MM-DD",
  "clusters": [
    {
      "name": "cluster name",
      "primary_keyword": { "keyword": "...", "volume": 0, "difficulty": 0, "cpc": 0, "intent": "..." },
      "supporting_keywords": [ ... ]
    }
  ]
}
```

Also print a human-readable summary to the conversation.
