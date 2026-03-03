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

**DataForSEO:**
```sh
curl -s -X POST "$DATAFORSEO_BASE/serp/google/organic/live/regular" \
  -u "$DATAFORSEO_LOGIN:$DATAFORSEO_PASSWORD" \
  -H "Content-Type: application/json" \
  -d '[{"keyword": "<KEYWORD>", "language_code": "'"$SEO_LANGUAGE"'", "location_code": 2840, "depth": 10}]' \
  | jq '.tasks[0].result[0].items'
```

**Generic / fallback — use WebFetch or curl:**
```sh
# Fetch each competitor page for content analysis
curl -sL "https://competitor-url.example.com/page" | lynx -stdin -dump -nolist
```

Or use the WebFetch tool to retrieve and analyze competitor pages directly.

### 3. Analyze each competitor page

For each of the top-ranking pages, extract:

- **URL and domain**
- **Title tag** and **meta description**
- **H1 and heading structure** (H2s, H3s)
- **Estimated word count**
- **Content format** (listicle, how-to, guide, comparison, etc.)
- **Key topics and subtopics covered**
- **Unique angles or differentiators**
- **Internal/external linking patterns** (if visible)

Use WebFetch to read competitor pages when possible. Fall back to curl + text extraction for simpler parsing.

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
