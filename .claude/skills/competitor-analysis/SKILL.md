---
name: competitor-analysis
description: Analyze top-ranking pages for target keywords and extract actionable competitive intelligence. Use when the user wants to research competitors or understand the SERP landscape.
---

# Competitor Analysis

Analyze the top-ranking pages for target keywords and extract actionable competitive intelligence.

## Inputs

Ask the user for:
1. **Target keyword(s)** — or read from an existing keyword research file in `output/`
2. **Your domain** (optional — to exclude from competitor list)
3. **Number of competitors to analyze** (default: 5)

## Steps

### 1. Load config and prior data

```sh
source api.env
```

Check `output/` for existing keyword research files. If one exists for the topic, offer to use it.

### 2. Fetch SERP data

For each primary keyword, retrieve the top 10 search results.

Adapt URL, auth header, and payload to `$SEO_PROVIDER` — see `api.env.example` for provider-specific endpoints and credentials.

```sh
# Example (DataForSEO). Adapt for your provider.
curl -s -X POST "$DATAFORSEO_BASE/serp/google/organic/live/regular" \
  -H "Authorization: Basic $DATAFORSEO_AUTH" \
  -H "Content-Type: application/json" \
  -d '[{"keyword": "<KEYWORD>", "language_code": "'"$SEO_LANGUAGE"'", "location_code": <LOCATION_CODE>, "depth": 10}]' \
  | jq '.tasks[0].result[0].items'
```

> `location_code` is derived from `$SEO_MARKET` (e.g. `de` → 2276 for Germany). Refer to your provider's docs for the full mapping.

Use WebFetch to retrieve and analyze competitor pages for content analysis.

### 3. Analyze each competitor page

For each competitor URL, run the page extractor to get precise structural data:

```sh
node src/extractor/extract-page.mjs "<URL>"
```

This returns JSON with: title, meta_description, canonical_url, og_title, og_description, h1, headings, word_count, link_count, main_content_preview.

Use these precise values in your analysis instead of estimating from WebFetch. You may still use WebFetch for qualitative analysis (content format, topics, unique angles) that requires reading comprehension.

For each page, extract or determine:

- **URL and domain**
- **Title tag** and **meta description** (from extractor)
- **H1 and heading structure** (from extractor)
- **Word count** (from extractor)
- **Content format** (listicle, how-to, guide, comparison, etc.)
- **Key topics and subtopics covered**
- **Unique angles or differentiators**
- **Internal/external linking patterns** (from extractor)

### 4. Build the competitive landscape

Create a comparison matrix:

| Competitor | Word Count | Format | Key Topics | Unique Angle | Content Gap |
|-----------|-----------|--------|-----------|-------------|-------------|
| ...       | ...       | ...    | ...       | ...         | ...         |

Identify:
- **Common themes** all competitors cover (table stakes)
- **Content gaps** topics none or few competitors address well
- **Differentiation opportunities** angles you could own
- **Weaknesses** areas where competitors are thin or outdated

### 5. Save output

Write to:
```
output/YYYY-MM-DD_<SEED_KEYWORD_SLUG>/competitors-<KEYWORD_SLUG>.json
```

JSON schema:
```json
{
  "target_keyword": "...",
  "date": "YYYY-MM-DD",
  "competitors": [
    {
      "url": "...",
      "domain": "...",
      "title": "...",
      "word_count": 0,
      "format": "...",
      "topics": ["..."],
      "unique_angle": "...",
      "strengths": ["..."],
      "weaknesses": ["..."]
    }
  ],
  "common_themes": ["..."],
  "content_gaps": ["..."],
  "opportunities": ["..."]
}
```

Print a concise competitive landscape summary to the conversation.
