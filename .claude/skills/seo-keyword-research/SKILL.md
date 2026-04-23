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
4. **Brand list** (optional, for navigational intent tagging)

## Steps

### 1. Load API config

```sh
source api.env
```

If `api.env` does not exist, tell the user to create it from the example:
```
cp api.env.example api.env
```

### Phase 1 — Deterministic data collection

All steps in this phase are deterministic scripts. No LLM inference.

#### 1a. Resolve location code

```sh
uv run python -m seo_pipeline.utils.resolve_location "$SEO_MARKET"
```

#### 1b. Expand keywords (related + suggestions)

```sh
uv run seo-pipeline fetch-keywords "<SEED_KEYWORD>" \
  --market "$SEO_MARKET" --language "$SEO_LANGUAGE" --outdir "$OUTDIR" --limit 50
```

Produces:
- `$OUTDIR/keywords-related-raw.json`
- `$OUTDIR/keywords-suggestions-raw.json`
- `$OUTDIR/keywords-expanded.json`

#### 1c. Process keywords into structured skeleton

```sh
uv run seo-pipeline process-keywords \
  --related "$OUTDIR/keywords-related-raw.json" \
  --suggestions "$OUTDIR/keywords-suggestions-raw.json" \
  --seed "<SEED_KEYWORD>" \
  [--brands "brand1,brand2"] \
  --output "$OUTDIR/keywords-processed.json"
```

This script deterministically:
1. Reads all raw JSON files
2. Deduplicates keywords (case-insensitive, trimmed)
3. Extracts volume, CPC, monthly_searches, and keyword difficulty per keyword (difficulty comes from `keyword_data.keyword_properties.keyword_difficulty` in the related/suggestions responses)
4. Tags search intent via regex patterns (DE + EN)
5. Clusters keywords via n-gram Jaccard overlap (threshold >= 0.5)
6. Outputs a JSON skeleton with `null` placeholders for LLM fields (`cluster_label`, `strategic_notes`)

### Phase 2 — Qualitative LLM analysis

The LLM fills ONLY the null fields in the processed skeleton:
- `cluster_label`: a human-readable name for each cluster
- `strategic_notes`: qualitative analysis per cluster

**Do NOT re-classify intent, re-cluster, or modify any numeric data.** Only fill null placeholders.

### 3. Save output

Write the final results to:
```
output/YYYY-MM-DD_<SEED_KEYWORD_SLUG>/keywords-<SEED_KEYWORD_SLUG>.json
```

JSON schema (output of `seo-pipeline process-keywords`):
```json
{
  "seed_keyword": "...",
  "total_keywords": 0,
  "total_clusters": 0,
  "clusters": [
    {
      "cluster_keyword": "highest volume keyword",
      "cluster_label": null,
      "strategic_notes": null,
      "keyword_count": 0,
      "keywords": [
        {
          "keyword": "...",
          "search_volume": 0,
          "cpc": 0,
          "monthly_searches": [],
          "difficulty": 0,
          "intent": "informational|commercial|transactional|navigational|null"
        }
      ]
    }
  ]
}
```

Also print a human-readable summary to the conversation.
