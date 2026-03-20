---
name: competitor-analysis
description: Analyze top-ranking pages for target keywords and extract actionable competitive intelligence. Use when the user wants to research competitors or understand the SERP landscape.
---

# Competitor Analysis

Analyze the top-ranking pages for target keywords and extract actionable competitive intelligence.

## Data Integrity Rules

> **CRITICAL: These rules override all other instructions.**
>
> 1. **Never modify non-null fields** in the data skeleton. Deterministic fields are ground truth.
> 2. **Never invent SERP features.** If `ai_overview.present` is `false`, do not add AI overview data. If a feature array is empty, it stays empty.
> 3. **Never fabricate competitor data.** Competitors come only from the SERP parser output. Do not add, remove, or reorder competitors.
> 4. **Only fill `null` fields** during qualitative analysis (Phase 2). These are: `format`, `topics`, `unique_angle`, `strengths`, `weaknesses`, `common_themes`, `content_gaps`, `opportunities`.
> 5. **Same API response = same deterministic output.** The SERP parser and assembler are deterministic scripts. If you run them twice on the same input, the output must be byte-identical.

## Inputs

Ask the user for:
1. **Target keyword(s)** — or read from an existing keyword research file in `output/`
2. **Your domain** (optional — to exclude from competitor list)
3. **Number of competitors to analyze** (default: 5)

## Phase 1 — Deterministic Data Collection

All data extraction happens through deterministic scripts. No LLM interpretation of raw API data.

> **Token budget:** All scripts use `--output` flags, so stdout should be minimal. If a step produces unexpected verbose output, pipe through `| head -20` to keep the context window lean. Never suppress stderr.

### 1.1 Load config and prior data

```sh
source api.env   # provides $SEO_MARKET and $SEO_LANGUAGE (API credentials are loaded internally by fetch-serp.mjs)
```

Check `output/` for existing keyword research files. If one exists for the topic, offer to use it.

### 1.2 Fetch SERP data

For each primary keyword, retrieve the top 10 search results using the async SERP workflow:

```sh
node src/serp/fetch-serp.mjs "<KEYWORD>" \
  --market "$SEO_MARKET" --language "$SEO_LANGUAGE" \
  [--outdir output/YYYY-MM-DD_<slug>/] \
  [--depth 10] [--force] [--max-age N]
```

**Parameters:**
- `--outdir` (optional) — Directory to save `serp-raw.json`. If omitted, the script auto-derives a directory based on today's date and the slugified keyword: `output/YYYY-MM-DD_<slug>/`. Useful when you want to organize results in a specific location.
- `--depth` (optional, default: 10) — Number of organic results to fetch.
- `--force` (optional) — Bypass cache and fetch fresh data from the API.
- `--max-age` (optional, default: 7) — Maximum cache age in days. Cache older than this is treated as expired and fresh data is fetched.

> **Caching:** If `serp-raw.json` already exists in the output directory and contains valid data, the script reuses it without making an API call. Use `--force` to bypass the cache and fetch fresh data.

This single command handles everything:
- Reads API credentials from `api.env` (no need to pass auth headers)
- Resolves the location code from `$SEO_MARKET` internally (no separate `resolve-location.mjs` call needed)
- Posts a task to the async `task_post` endpoint, polls for completion, and retrieves results via `task_get/advanced`
- Saves the raw response to `$outdir/serp-raw.json`
- Outputs the raw JSON to stdout for pipeline chaining

> **Note:** `resolve-location.mjs` still exists in `src/utils/` and can be used standalone if needed by other parts of the pipeline.

### 1.3 Process SERP data (deterministic)

Run the deterministic SERP parser to extract structured data from the raw API response:

```sh
node src/serp/process-serp.mjs output/YYYY-MM-DD_<slug>/serp-raw.json --top <N> \
  --output output/YYYY-MM-DD_<slug>/serp-processed.json
```

This produces a structured JSON with:
- `target_keyword`, `se_results_count`, `location_code`, `language_code`
- `item_types_present` — verbatim from the API response
- `serp_features` — extracted deterministically from items by type (ai_overview, featured_snippet, people_also_ask, people_also_search, related_searches, discussions_and_forums, video, top_stories, knowledge_graph, commercial_signals, local_signals, other_features_present)
- `competitors` — organic results with rank, url, domain, title, description, is_featured_snippet, is_video, has_rating, rating, timestamp, cited_in_ai_overview

### 1.4 Extract page data for each competitor

For each competitor URL from `serp-processed.json`, run the page extractor:

```sh
node src/extractor/extract-page.mjs "<URL>" --output output/YYYY-MM-DD_<slug>/pages/<DOMAIN>.json
```

This returns JSON with: title, meta_description, canonical_url, og_title, og_description, h1, headings, word_count, link_count, main_content_preview.

### 1.5 Assemble data skeleton

Merge SERP processed data with page extractor outputs into the final data skeleton:

```sh
node src/serp/assemble-competitors.mjs \
  output/YYYY-MM-DD_<slug>/serp-processed.json \
  output/YYYY-MM-DD_<slug>/pages/ \
  --date YYYY-MM-DD \
  --output output/YYYY-MM-DD_<slug>/competitors-data.json
```

This produces the complete data structure with all deterministic fields filled and all qualitative fields set to `null`.

## Phase 2 — Qualitative Analysis (Claude)

Read the data skeleton from `competitors-data.json`. Use WebFetch to read competitor pages for qualitative analysis (content format, topics, unique angles, strengths, weaknesses).

### 2.1 Analyze each competitor page

For each competitor in the data skeleton:

1. Use WebFetch to read the competitor page
2. Determine the qualitative fields:
   - **format** — listicle, how-to, guide, comparison, etc.
   - **topics** — key topics and subtopics covered
   - **unique_angle** — what makes this page different
   - **strengths** — what the page does well
   - **weaknesses** — where the page is thin or outdated

### 2.2 Build strategic insights

Based on all competitor analysis:
- **common_themes** — topics all competitors cover (table stakes)
- **content_gaps** — topics none or few competitors address well
- **opportunities** — differentiation angles you could own

### 2.3 Save final output

Fill ONLY the `null` fields in the data skeleton. **Never modify non-null fields. Never add SERP features not in the data skeleton.**

Write the completed analysis to:
```
output/YYYY-MM-DD_<slug>/competitors-<KEYWORD_SLUG>.json
```

## Output Directory Structure

```
output/YYYY-MM-DD_<slug>/
  serp-raw.json              ← raw API response (audit trail)
  serp-processed.json        ← deterministic SERP extraction
  pages/
    www.tourlane.de.json     ← page extractor output per competitor
    www.tui.com.json
  competitors-data.json      ← assembled data skeleton (null placeholders)
  competitors-<slug>.json    ← final output with qualitative analysis
```

## Console Summary

Print a concise competitive landscape summary to the conversation, including:
- **SERP feature overview** — which features are present and what they signal about user intent
- **Competitor comparison matrix**
- **AI Overview** — which domains Google cites (only if present in data skeleton)
- **Featured snippet** — format, source, and how to win it (only if present)
- **People Also Ask** — the questions users are asking
- **Related searches / People Also Search** — secondary keyword opportunities
- **Rich media signals** — whether video, images, podcasts etc. are present
- **Content gaps and strategic opportunities**

## SERP Feature Reference

The pipeline uses the async `task_post`/`task_get/advanced` workflow (via `fetch-serp.mjs`) instead of the synchronous `live/advanced` endpoint. The response structure is identical -- both nest results at `tasks[0].result[0]`. The async workflow is cheaper and avoids timeout issues on slow queries. The endpoint can return up to 50 different item types. The deterministic parser (`process-serp.mjs`) handles these automatically. For reference, the categories are:

#### Core ranking items
- **`organic`** — competitor URLs, titles, descriptions, rank positions
- **`paid`** — paid ads signal commercial intent
- **`featured_snippet`** — the page Google elevates above organic #1
- **`ai_overview`** — Google's AI-generated answer with referenced domains

#### User intent & related queries
- **`people_also_ask`** — questions users also search for
- **`people_also_search`** — related search refinements
- **`related_searches`** — additional related queries
- **`discussions_and_forums`** — forum threads Google surfaces

#### Rich media & content format signals
- **`video`** / **`short_videos`** — video content demand
- **`images`** — image pack presence
- **`top_stories`** — news results signal trending topic

#### Commerce & product signals
- **`commercial_units`** / **`shopping`** / **`popular_products`** — transactional intent
- **`hotels_pack`** / **`local_pack`** / **`map`** — travel/local intent

#### Knowledge & authority signals
- **`knowledge_graph`** — entity panel
- **`answer_box`** — direct answer
