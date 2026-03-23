# Claude Content Creation Pipeline

Deterministic SEO content pipeline -- scripts handle all data extraction; a single LLM call does qualitative analysis only.

## Architecture

Every byte of data processing is handled by deterministic Node.js scripts that produce identical output for identical input. The LLM is constrained to a single, final step: filling in qualitative null placeholders on a pre-built data skeleton. It never re-ranks, re-scores, or modifies any deterministic field.

The pipeline runs in two phases:

- **Phase 1 (deterministic):** 11 scripts fetch, parse, cluster, score, and assemble all keyword, SERP, competitor, and content analysis data into `briefing-data.json`. Every intermediate file is JSON-in, JSON-out via stdout.
- **Phase 2 (single LLM call):** The LLM reads `briefing-data.json` and fills 6 qualitative fields (entity clusters, GEO audit, format recommendation, unique angles, AIO strategy, final briefing). It operates on the pre-built skeleton and cannot alter deterministic data.

```
                         Seed Keyword + Market
                                |
                                v
                     +---------------------+
                     | resolve-location.mjs |  market code -> DataForSEO location code
                     +---------------------+
                                |
                                v
                     +---------------------+
                     | fetch-keywords.mjs   |  DataForSEO related + suggestions endpoints
                     +---------------------+
                           |         |
          keywords-related-raw.json  keywords-suggestions-raw.json
                           |         |
                           v         v
                     +---------------------+
                     | process-keywords.mjs |  intent tags, Jaccard clusters, opportunity scores
                     +---------------------+
                                |
                    keywords-processed.json
                                |
         +----------------------+----------------------+
         |                                             |
         v                                             v
+---------------------+                    +---------------------+
| filter-keywords.mjs |                    | process-serp.mjs    |  SERP feature extraction
+---------------------+                    +---------------------+
         |                                             |
 keywords-filtered.json                      serp-processed.json
         |                                        |         |
         |                        +---------------+         |
         |                        v                         v
         |             +---------------------+   +-------------------------+
         |             | extract-page.mjs    |   | assemble-competitors.mjs|
         |             +---------------------+   +-------------------------+
         |                   (per URL)                      |
         |                        |                competitors-data.json
         |                  pages/<domain>.json              |
         |                        |                         |
         |                        v                         |
         |             +---------------------------+        |
         |             | analyze-page-structure.mjs |       |
         |             +---------------------------+        |
         |                        |                         |
         |               page-structure.json                |
         |                        |                         |
         |                        v                         |
         |             +---------------------------+        |
         |             | analyze-content-topics.mjs |       |
         |             +---------------------------+        |
         |                        |                         |
         |               content-topics.json                |
         |                        |                         |
         |                        v                         |
         |             +-------------------------------+    |
         |             | compute-entity-prominence.mjs  |   |
         |             +-------------------------------+    |
         |                        |                         |
         |              entity-prominence.json              |
         |                        |                         |
         +----------+-------------+-------------------------+
                    |
                    v
         +---------------------------+
         | assemble-briefing-data.mjs |  consolidates everything
         +---------------------------+
                    |
            briefing-data.json
                    |
                    v
         +---------------------------+
         |   Single LLM call         |  fills 6 qualitative null fields
         +---------------------------+
                    |
              brief-<slug>.md
```

## Prerequisites

- Node.js >= 18
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
- A [DataForSEO](https://dataforseo.com/) account (login + password)

## Setup

1. Clone the repository:

   ```bash
   git clone <repo-url>
   cd ClaudeContentCreationPipeline
   ```

2. Configure API credentials:

   ```bash
   cp api.env.example api.env
   ```

   Edit `api.env` and set your DataForSEO credentials:

   ```env
   SEO_PROVIDER=dataforseo
   DATAFORSEO_AUTH=<base64 of login:password>
   DATAFORSEO_BASE=https://api.dataforseo.com/v3
   ```

   Generate the auth string with: `echo -n 'login:password' | base64`

3. Set your market and language in `api.env`:

   ```env
   SEO_MARKET=de
   SEO_LANGUAGE=de
   ```

4. Install extractor dependencies (jsdom + @mozilla/readability):

   ```bash
   cd src/extractor && npm install && cd ../..
   ```

5. Verify the setup:

   ```bash
   npm test
   ```

## Usage

### Full pipeline

Run the complete pipeline with a single skill:

```
/seo-content-pipeline
```

Claude will collect these inputs interactively:

| Input | Required | Description |
|-------|----------|-------------|
| Seed keyword | yes | The topic to research (e.g. "thailand urlaub") |
| Your domain | no | Excluded from competitor analysis |
| Market | no | ISO country code, default `de` |
| Business context | yes | What you sell, target audience |
| Content goals | yes | Traffic, leads, authority, conversions |
| Content template | no | Pick from `templates/template-*.md` or skip |
| Brand voice | no | Pick from `templates/*ToneOfVoice*` or skip |

### Individual skills

Each pipeline phase is also available as a standalone skill:

| Skill | Scope |
|-------|-------|
| `/seo-keyword-research` | Fetch keyword data from DataForSEO, cluster by intent and volume |
| `/competitor-analysis` | Analyze top-ranking pages, extract structure and content signals |
| `/content-strategy` | Synthesize keyword + competitor data into a prioritized content roadmap |
| `/content-briefing` | Generate a detailed writing brief from `briefing-data.json` |
| `/content-draft` | Write a publish-ready article from an existing brief |
| `/implement-issues` | Work through GitHub issues in `IMPLEMENTATION.md` via agent orchestration |

## Pipeline Steps (Phase 1)

Each script reads JSON (from files or stdout) and writes JSON to stdout. All sorting is stable. All output is byte-identical for identical input.

### 1. resolve-location.mjs

Resolves an ISO country code to a DataForSEO numeric location code via local lookup. Zero network calls.

```bash
node src/utils/resolve-location.mjs de
# stdout: 2276 (integer, not JSON)
```

- **Input:** positional `<market>` (ISO 3166-1 alpha-2)
- **Output:** stdout integer
- **Data source:** `src/utils/location-codes.json`

### 2. fetch-serp.mjs

Calls DataForSEO `task_post` and `task_get/advanced` endpoints to retrieve top organic search results for a keyword. Handles caching automatically: if `serp-raw.json` exists and is fresh, reuses it; otherwise fetches from the API.

```bash
node src/serp/fetch-serp.mjs "thailand urlaub" \
  --market de --language de --outdir output/2026-03-09_thailand-urlaub \
  --depth 10 --force
```

- **Flags:**
  - `<keyword>` (positional, required) — the search keyword
  - `--market` (required) — ISO country code (e.g. `de`)
  - `--language` (required) — language code (e.g. `de`)
  - `--outdir` (optional) — where to save `serp-raw.json`. If omitted, auto-derives `output/YYYY-MM-DD_<slug>/`
  - `--depth` (optional, default 10) — number of organic results to fetch
  - `--timeout` (optional, default 120) — API request timeout in seconds
  - `--force` (optional) — bypass cache and fetch fresh data from API
  - `--max-age` (optional, default 7) — maximum cache age in days; older cache is treated as expired
- **Output files:** `serp-raw.json` (raw DataForSEO API response) in `--outdir`
- **Stdout:** raw SERP JSON (same as `serp-raw.json`)
- **Data source:** DataForSEO API via credentials in `api.env`

**Caching:** If `serp-raw.json` exists in the output directory and was created within `--max-age` days, the script reuses it without an API call. Use `--force` to bypass the cache.

### 3. fetch-keywords.mjs

Calls DataForSEO `related_keywords` and `keyword_suggestions` endpoints, saves raw responses, then runs `merge-keywords.mjs` internally to produce a deduplicated keyword list.

```bash
node src/keywords/fetch-keywords.mjs "thailand urlaub" \
  --market de --language de --outdir output/2026-03-09_thailand-urlaub --limit 50
```

- **Flags:** `<seed>` (positional), `--market`, `--language`, `--outdir` (all required), `--limit` (optional, default 50)
- **Output files:** `keywords-related-raw.json`, `keywords-suggestions-raw.json`, `keywords-expanded.json` in outdir
- **Stdout:** merged keyword JSON (same as `keywords-expanded.json`)
- **Data source:** DataForSEO API via credentials in `api.env`

### 4. process-keywords.mjs

Merges raw API responses into a structured skeleton with intent tags (DE+EN regex), Jaccard-similarity n-gram clusters (threshold >= 0.5), and opportunity scores. Null placeholders for LLM-only fields (`cluster_label`, `strategic_notes`).

```bash
node src/keywords/process-keywords.mjs \
  --related output/dir/keywords-related-raw.json \
  --suggestions output/dir/keywords-suggestions-raw.json \
  --seed "thailand urlaub"
```

- **Flags:** `--related`, `--suggestions`, `--seed` (required), `--volume`, `--brands` (optional)
- **Output:** stdout JSON with `clusters[]`, each containing `keywords[]` with intent, volume, CPC, opportunity score

### 5. filter-keywords.mjs

Tags keywords with filter status (blocklist, brand, foreign-language) without deleting them -- tag, don't delete. Computes FAQ prioritization by scoring PAA questions against keyword token overlaps.

```bash
node src/keywords/filter-keywords.mjs \
  --keywords output/dir/keywords-processed.json \
  --serp output/dir/serp-processed.json \
  --seed "thailand urlaub"
```

- **Flags:** `--keywords`, `--serp`, `--seed` (required), `--blocklist`, `--brands` (optional)
- **Output:** stdout JSON with `clusters[]` (keywords annotated with `filter_status` + `filter_reason`), `faq_selection[]`, `removal_summary`
- **Default blocklist:** `src/keywords/blocklist-default.json`

### 6. process-serp.mjs

Parses a raw DataForSEO advanced SERP response into structured features: AI Overview, featured snippets, People Also Ask, related searches, discussions, video, top stories, knowledge graph, commercial and local signals.

```bash
node src/serp/process-serp.mjs output/dir/serp-raw.json --top 10
```

- **Flags:** `<file>` (positional, required), `--top` (optional, default 10)
- **Output:** stdout JSON with `serp_features`, `competitors[]`

### 7. extract-page.mjs

Fetches a URL and parses it with jsdom + @mozilla/readability. Extracts headings (h2-h4), word count, link counts, meta tags, and HTML content signals (FAQ sections, tables, lists, video embeds, images, forms).

```bash
node src/extractor/extract-page.mjs "https://example.com/page"
```

- **Flags:** `<URL>` (positional, required)
- **Output:** stdout JSON with `headings[]`, `word_count`, `link_count`, `html_signals`, `main_content_text`
- **Dependencies:** jsdom, @mozilla/readability (installed locally in `src/extractor/`)

### 8. assemble-competitors.mjs

Merges SERP ranking data with per-page extractor outputs. Qualitative fields (`format`, `topics`, `unique_angle`, `strengths`, `weaknesses`) are set to `null` as LLM placeholders.

```bash
node src/serp/assemble-competitors.mjs output/dir/serp-processed.json output/dir/pages/
```

- **Flags:** `<serp-file>` `<pages-dir>` (positional, required), `--date` (optional, default today)
- **Output:** stdout JSON with `competitors[]` (deterministic + null qualitative fields), `common_themes: null`, `content_gaps: null`, `opportunities: null`

### 9. analyze-page-structure.mjs

Detects content modules (FAQ, table, list, video, form, image gallery) per competitor page. Computes per-section word/sentence counts, depth scores, and cross-competitor module frequency.

```bash
node src/analysis/analyze-page-structure.mjs --pages-dir output/dir/pages/
```

- **Flags:** `--pages-dir` (required)
- **Output:** stdout JSON with `competitors[]` (each with `detected_modules[]`, `sections[]`), `cross_competitor` (module frequency, averages)

### 10. analyze-content-topics.mjs

Extracts n-gram term frequencies (TF-IDF proxy), clusters headings by Jaccard overlap into section weight groups, and reports content format signals across competitors.

```bash
node src/analysis/analyze-content-topics.mjs \
  --pages-dir output/dir/pages/ --seed "thailand urlaub" --language de
```

- **Flags:** `--pages-dir`, `--seed` (required), `--language` (optional, default `de`)
- **Output:** stdout JSON with `proof_keywords[]` (top 50), `entity_candidates[]` (top 30), `section_weights[]`, `content_format_signals`
- **Data source:** `src/utils/stopwords.json` for stopword filtering

### 11. compute-entity-prominence.mjs

Re-computes entity mention counts across competitor page texts using exact synonym matching. Records discrepancies against any prior LLM-supplied prominence values in `_debug.corrections`.

```bash
node src/analysis/compute-entity-prominence.mjs \
  --entities output/dir/entities.json --pages-dir output/dir/pages/
```

- **Flags:** `--entities`, `--pages-dir` (required)
- **Output:** stdout JSON with `entity_clusters[]` (each entity has code-verified `prominence` as `"N/M"` string, `prominence_source: "code"`)

### 12. assemble-briefing-data.mjs

Consolidates all pipeline outputs from a run directory into a single `briefing-data.json`. Normalizes years, ranks keyword clusters by total search volume, and sets all qualitative fields to `null`.

```bash
node src/analysis/assemble-briefing-data.mjs --dir output/2026-03-09_thailand-urlaub/
```

- **Flags:** `--dir` (required) -- path to the pipeline run output directory
- **Reads (all optional, gracefully absent):** `serp-processed.json`, `keywords-processed.json`, `keywords-filtered.json`, `page-structure.json`, `content-topics.json`, `entity-prominence.json`, `competitors-data.json`
- **Output:** writes `briefing-data.json` to `--dir` and emits the same JSON to stdout

Output structure:

```json
{
  "meta": { "seed_keyword", "date", "current_year", "pipeline_version" },
  "keyword_data": { "clusters", "total_keywords", "filtered_count", "removal_summary" },
  "serp_data": { "competitors", "serp_features", "aio" },
  "content_analysis": { "proof_keywords", "entity_candidates", "section_weights", "content_format_signals" },
  "competitor_analysis": { "page_structures", "common_modules", "rare_modules", "avg_word_count" },
  "faq_data": { "questions", "paa_source" },
  "qualitative": {
    "entity_clusters": null,
    "unique_angles": null,
    "content_format_recommendation": null,
    "geo_audit": null,
    "aio_strategy": null,
    "briefing": null
  }
}
```

### Utility scripts (not pipeline steps)

These scripts are imported by other pipeline scripts or used by specific skills:

- **`extract-keywords.mjs`** -- shared ES module that normalizes keyword records from DataForSEO response shapes. No CLI interface.
- **`merge-keywords.mjs`** -- deduplicates keywords from two raw response files. Called internally by `fetch-keywords.mjs`.
- **`prepare-strategist-data.mjs`** -- builds a data skeleton for the content-strategy skill (top keywords, autocomplete, PAA, SERP snippets). Used by `/content-strategy`.

## Qualitative Analysis (Phase 2)

After `briefing-data.json` is assembled, a single LLM call fills these 6 null fields:

| Field | Description |
|-------|-------------|
| `entity_clusters` | Grouped entities with semantic relationships and prominence data |
| `geo_audit` | GEO (Generative Engine Optimization) readiness assessment |
| `content_format_recommendation` | Recommended content format based on SERP and competitor signals |
| `unique_angles` | Differentiation opportunities not covered by competitors |
| `aio_strategy` | Strategy for AI Overview optimization |
| `briefing` | Final assembled content briefing |

**Data integrity constraint:** The LLM never re-ranks keywords, re-scores opportunities, modifies competitor data, or alters any deterministic field. It reads the skeleton and fills nulls only.

## Output Directory

Each pipeline run produces a dated directory:

```
output/2026-03-09_thailand-urlaub/
  keywords-related-raw.json       # Raw DataForSEO related keywords response
  keywords-suggestions-raw.json   # Raw DataForSEO suggestions response
  keywords-expanded.json          # Deduplicated merged keywords
  keywords-processed.json         # Clustered, intent-tagged, scored keywords
  keywords-filtered.json          # Tagged with filter status + FAQ selection
  serp-raw.json                   # Raw DataForSEO SERP response
  serp-processed.json             # Extracted SERP features + competitor list
  pages/
    example-com.json              # Per-domain page extraction (one per competitor)
    other-site-de.json
  competitors-data.json           # Merged SERP + page data with null qualitative fields
  page-structure.json             # Module detection + cross-competitor analysis
  content-topics.json             # Proof keywords, entity candidates, section weights
  entity-prominence.json          # Code-verified entity mention counts
  briefing-data.json              # Consolidated data skeleton (Phase 1 output)
  brief-thailand-urlaub.md        # Final content briefing (Phase 2 output)
```

## Project Structure

```
src/
  utils/
    resolve-location.mjs          # Market code -> DataForSEO location code
    slugify.mjs                    # URL-safe slug generator
    location-codes.json            # ISO -> numeric location mapping
    stopwords.json                 # Stopword lists for TF-IDF filtering
  keywords/
    fetch-keywords.mjs             # DataForSEO API caller + merge orchestrator
    extract-keywords.mjs           # Shared keyword normalization module
    merge-keywords.mjs             # Deduplication + stable sort by volume
    process-keywords.mjs           # Intent tagging, Jaccard clustering, scoring
    filter-keywords.mjs            # Blocklist/brand/language tagging + FAQ priority
    prepare-strategist-data.mjs    # Data skeleton for content-strategy skill
    blocklist-default.json         # Default keyword blocklist
  serp/
    fetch-serp.mjs                 # SERP data fetcher (async task_post/task_get)
    process-serp.mjs               # SERP feature extraction from raw API response
    assemble-competitors.mjs       # Merge SERP data + page extractions
  extractor/
    extract-page.mjs               # jsdom + Readability page parser
    package.json                   # Local deps: jsdom, @mozilla/readability
  analysis/
    analyze-page-structure.mjs     # Module detection, section depth scoring
    analyze-content-topics.mjs     # TF-IDF proof keywords, entity candidates
    compute-entity-prominence.mjs  # Code-verified entity counts across pages
    assemble-briefing-data.mjs     # Consolidate all outputs into briefing-data.json

test/
  scripts/
    resolve-location.test.mjs
    extract-keywords.test.mjs
    merge-keywords.test.mjs
    process-keywords.test.mjs
    filter-keywords.test.mjs
    extract-page.test.mjs
    process-serp.test.mjs
    fetch-serp.test.mjs
    slugify.test.mjs
    analyze-page-structure.test.mjs
    analyze-content-topics.test.mjs
    compute-entity-prominence.test.mjs
    assemble-briefing-data.test.mjs
    prepare-strategist-data.test.mjs
    example.test.mjs

.claude/
  skills/
    seo-content-pipeline/          # Full pipeline orchestrator
    seo-keyword-research/          # Keyword research skill
    competitor-analysis/           # Competitor analysis skill
    content-strategy/              # Content strategy skill
    content-briefing/              # Content briefing skill
    content-draft/                 # Article draft skill
    implement-issues/              # GitHub issue orchestration skill

templates/
  template-urlaubsseite.md         # Transactional destination page template
  template-reisemagazin.md         # Travel magazine article template
  DT_ToneOfVoice.md               # Brand tone of voice guide

output/                            # Generated pipeline runs (gitignored)
api.env.example                    # API configuration template
package.json                       # Test runner config (node --test)
```

## Testing

13 test files, 272 passing tests. Zero external test dependencies -- uses Node.js built-in `node --test`.

```bash
npm test
```

Every deterministic script has byte-identity tests: given the same input JSON, the script produces the exact same output, byte for byte.

## Design Decisions

**Tag, don't delete.** Filtered keywords are tagged with `filter_status` and `filter_reason` rather than removed. This preserves a full audit trail and lets downstream steps make informed decisions.

**Null placeholder strategy.** All qualitative fields are explicitly set to `null` in the data skeleton. The LLM's job is to fill those nulls -- nothing else. This makes it trivial to verify that deterministic data was not modified.

**Stable sorting everywhere.** All array sorts use stable comparison functions with tiebreakers (typically alphabetical on keyword string). This guarantees byte-identical output across runs and Node.js versions.

**Year normalization.** Keywords containing year references (e.g. "thailand urlaub 2025") are normalized to the current year to prevent stale data from skewing cluster formation.

**JSON in, JSON out via stdout.** Every script reads JSON from files/flags and writes JSON to stdout. This enables Unix-style piping and makes each script independently testable.

**Local extractor dependencies.** jsdom and @mozilla/readability are installed in `src/extractor/` with their own `package.json`, keeping the root project dependency-free. The root `package.json` has zero dependencies.

## Troubleshooting

### 1. HTTP 403 from DataForSEO

**Symptom:** `API error 403: ...` from `fetch-serp.mjs` or `fetch-keywords.mjs`

**Cause:** Invalid credentials, expired account, or exceeded API quota

**Fix:** Verify credentials with a direct curl test:

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Basic $(cat api.env | grep DATAFORSEO_AUTH | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '[{"keyword":"test","language_code":"en","location_code":2840}]' \
  "https://api.dataforseo.com/v3/dataforseo_labs/google/related_keywords/live"
```

Check your account status at https://app.dataforseo.com/

### 2. Missing extractor dependencies

**Symptom:** `Error: Cannot find module 'jsdom'` or `MODULE_NOT_FOUND` from `extract-page.mjs`

**Cause:** `src/extractor/node_modules` does not exist — dependencies are installed separately from root

**Fix:**

```bash
cd src/extractor && npm install && cd ../..
```

### 3. ENOTDIR / output directory errors

**Symptom:** `ENOTDIR: not a directory` or `ENOENT: no such file or directory` during pipeline run

**Cause:** A file exists where a directory is expected, or the output path structure is wrong

**Fix:** Ensure the `output/` directory exists and is writable. Delete any stale files that conflict with expected directory paths.

### 4. Base64 encoding of credentials

**Symptom:** `API error 401` despite correct login/password

**Cause:** `DATAFORSEO_AUTH` in `api.env` is not properly base64-encoded, or includes trailing whitespace/newline

**Fix:** Regenerate with:

```bash
echo -n 'login:password' | base64
```

The `-n` flag is critical — without it, a newline gets encoded into the credentials.

### 5. Stale SERP cache

**Symptom:** Pipeline returns old SERP data even after the search landscape changed

**Cause:** `fetch-serp.mjs` caches results in `serp-raw.json` and reuses them by default

**Fix:** Re-run with `--force` flag to bypass the cache:

```bash
node src/serp/fetch-serp.mjs "keyword" --market de --language de --force
```

### 6. Node.js version too old

**Symptom:** Syntax errors on `import` statements or `AbortSignal.timeout is not a function`

**Cause:** Node.js < 18 does not support ESM, `AbortSignal.timeout()`, or the built-in test runner

**Fix:** Upgrade to Node.js 18 or later. Check with:

```bash
node --version
```
