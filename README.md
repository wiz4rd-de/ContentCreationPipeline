# Claude Content Creation Pipeline

Deterministic SEO content pipeline -- scripts handle all data extraction; a single LLM call does qualitative analysis only.

## Architecture

Every byte of data processing is handled by deterministic Node.js scripts (~9,300 LOC) that produce identical output for identical input. The LLM is constrained to a single, final step: filling in qualitative null placeholders on a pre-built data skeleton. It never re-ranks, re-scores, or modifies any deterministic field.

The pipeline runs in three phases:

- **Phase 1 (deterministic):** 8 pipeline scripts fetch, parse, cluster, score, and assemble all keyword, SERP, competitor, and content analysis data into `briefing-data.json`. Every intermediate file is JSON-in, JSON-out via stdout.
- **Phase 2 (single LLM call):** The LLM reads `briefing-data.json` and fills 6 qualitative fields (entity clusters, GEO audit, format recommendation, unique angles, AIO strategy, final briefing). It operates on the pre-built skeleton and cannot alter deterministic data.
- **Phase 3 (optional, LLM):** Generates a publish-ready article draft from the content briefing, enforcing SEO best practices and brand voice guidelines.

```
                         Seed Keyword + Market
                                |
               +----------------+----------------+
               |                                 |
               v                                 v
    +---------------------+           +---------------------+
    | fetch-keywords.mjs  |           | fetch-serp.mjs      |
    | DataForSEO related  |           | DataForSEO SERP     |
    | + suggestions       |           | (async task_post/get)|
    +---------------------+           +---------------------+
               |                                 |
               v                                 v
    +---------------------+           +---------------------+
    | process-keywords.mjs|           | process-serp.mjs    |
    | intent, clusters,   |           | AI Overview, PAA,   |
    | opportunity scores  |           | featured snippets   |
    +---------------------+           +---------------------+
               |                                 |
               v                          +------+------+
    +---------------------+               |             |
    | filter-keywords.mjs |               v             v
    | blocklist, brand,   |    +----------------+  +------------------+
    | FAQ priority        |    | extract-page   |  | assemble-        |
    +---------------------+    | (per URL)      |  | competitors.mjs  |
               |               +----------------+  +------------------+
               |                      |                    |
               |               pages/<domain>.json         |
               |                      |                    |
               |                      v                    |
               |          +--------------------------+     |
               |          | analyze-page-structure   |     |
               |          | analyze-content-topics   |     |
               |          | compute-entity-prominence|     |
               |          +--------------------------+     |
               |                      |                    |
               +----------+-----------+--------------------+
                          |
                          v
               +---------------------+
               | assemble-briefing-  |  consolidates everything
               | data.mjs           |  into briefing-data.json
               +---------------------+
                          |
                  briefing-data.json
                     (Phase 1 done)
                          |
                          v
               +---------------------+
               | Single LLM call     |  fills 6 qualitative
               | (Phase 2)           |  null fields
               +---------------------+
                          |
                    brief-<slug>.md
                          |
                          v
               +---------------------+
               | Article draft       |  SEO-optimized article
               | (Phase 3, optional) |  with brand voice
               +---------------------+
                          |
                    draft-<slug>.md
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

2. Install dependencies:

   ```bash
   npm install
   cd src/extractor && npm install && cd ../..
   ```

3. Configure API credentials:

   ```bash
   cp api.env.example api.env
   ```

   Edit `api.env` and set your DataForSEO credentials:

   ```env
   SEO_PROVIDER=dataforseo
   DATAFORSEO_AUTH=<base64 of login:password>
   DATAFORSEO_BASE=https://api.dataforseo.com/v3
   SEO_MARKET=de
   SEO_LANGUAGE=de
   ```

   Generate the auth string with: `echo -n 'login:password' | base64`

4. Verify the setup:

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
| Brand voice | no | Pick from `templates/*ToV*` or skip |

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

### Direct CLI

Every pipeline script can be run standalone for debugging, piping, or integration:

```bash
# Keyword research
node src/keywords/fetch-keywords.mjs "thailand urlaub" \
  --market de --language de --outdir output/2026-03-23_thailand-urlaub --limit 50
node src/keywords/process-keywords.mjs \
  --related keywords-related-raw.json --suggestions keywords-suggestions-raw.json \
  --seed "thailand urlaub"
node src/keywords/filter-keywords.mjs \
  --keywords keywords-processed.json --serp serp-processed.json --seed "thailand urlaub"

# SERP analysis
node src/serp/fetch-serp.mjs "thailand urlaub" --market de --language de --force
node src/serp/process-serp.mjs serp-raw.json --top 10

# Page extraction
node src/extractor/extract-page.mjs "https://example.com/page"

# Content analysis
node src/analysis/analyze-page-structure.mjs --pages-dir output/dir/pages/
node src/analysis/analyze-content-topics.mjs --pages-dir output/dir/pages/ --seed "thailand urlaub"
node src/analysis/compute-entity-prominence.mjs --entities entities.json --pages-dir output/dir/pages/

# Assembly
node src/analysis/assemble-briefing-data.mjs --dir output/2026-03-23_thailand-urlaub/

# Utilities
node src/utils/resolve-location.mjs de          # -> 2276
node src/utils/slugify.mjs "thailand urlaub"     # -> thailand-urlaub
node scripts/clean-output.mjs --keep-days 30
```

All scripts support `--output <path>` for file output (default: stdout).

## Pipeline Steps (Phase 1)

Each script reads JSON (from files or stdout) and writes JSON to stdout. All sorting is stable. All output is byte-identical for identical input.

### 1. fetch-serp.mjs

Calls DataForSEO `task_post` and `task_get/advanced` endpoints to retrieve top organic search results. Handles caching automatically: if `serp-raw.json` exists and is fresh, reuses it; otherwise fetches from the API.

- **Flags:** `<keyword>` (positional), `--market`, `--language` (required), `--outdir`, `--depth` (default 10), `--timeout` (default 120s), `--force` (bypass cache), `--max-age` (default 7 days)
- **Output:** `serp-raw.json` in `--outdir`

### 2. fetch-keywords.mjs

Calls DataForSEO `related_keywords` and `keyword_suggestions` endpoints, saves raw responses, then merges internally to produce a deduplicated keyword list.

- **Flags:** `<seed>` (positional), `--market`, `--language`, `--outdir` (required), `--limit` (default 50)
- **Output:** `keywords-related-raw.json`, `keywords-suggestions-raw.json`, `keywords-expanded.json`

### 3. process-keywords.mjs

Merges raw API responses into a structured skeleton with intent tags (DE+EN regex), Jaccard-similarity n-gram clusters (threshold >= 0.5), and opportunity scores. Null placeholders for LLM-only fields (`cluster_label`, `strategic_notes`).

- **Flags:** `--related`, `--suggestions`, `--seed` (required), `--volume`, `--brands` (optional)
- **Output:** JSON with `clusters[]`, each containing `keywords[]` with intent, volume, CPC, opportunity score

### 4. filter-keywords.mjs

Tags keywords with filter status (blocklist, brand, foreign-language) without deleting them -- tag, don't delete. Computes FAQ prioritization by scoring PAA questions against keyword token overlaps.

- **Flags:** `--keywords`, `--serp`, `--seed` (required), `--blocklist`, `--brands` (optional)
- **Output:** JSON with `clusters[]` (keywords annotated with `filter_status` + `filter_reason`), `faq_selection[]`, `removal_summary`
- **Default blocklist:** `src/keywords/blocklist-default.json` (ethics, booking portals, spam patterns)

### 5. process-serp.mjs

Parses a raw DataForSEO advanced SERP response into structured features: AI Overview, featured snippets, People Also Ask, related searches, discussions, video, top stories, knowledge graph, commercial and local signals.

- **Flags:** `<file>` (positional), `--top` (default 10)
- **Output:** JSON with `serp_features`, `competitors[]`

### 6. extract-page.mjs

Fetches a URL and parses it with jsdom + @mozilla/readability. Extracts headings (h2-h4), word count, link counts, meta tags, and HTML content signals (FAQ sections, tables, lists, video embeds, images, forms).

- **Flags:** `<URL>` (positional)
- **Output:** JSON with `headings[]`, `word_count`, `link_count`, `html_signals`, `main_content_text`
- **Dependencies:** jsdom, @mozilla/readability (installed locally in `src/extractor/`)

### 7. Content analysis scripts

Three scripts that analyze the extracted pages:

**analyze-page-structure.mjs** -- Detects content modules (FAQ, table, list, video, form, image gallery) per competitor page. Computes per-section word/sentence counts, depth scores, and cross-competitor module frequency.

**analyze-content-topics.mjs** -- Extracts n-gram term frequencies with IDF boost (Leipzig Wikipedia 1M corpus), clusters headings by Jaccard overlap, and reports content format signals across competitors.

**compute-entity-prominence.mjs** -- Re-computes entity mention counts across competitor page texts using exact synonym matching. Records discrepancies against any prior LLM-supplied values.

### 8. assemble-briefing-data.mjs

Consolidates all pipeline outputs from a run directory into a single `briefing-data.json`. Normalizes years, ranks keyword clusters by total search volume, and sets all qualitative fields to `null`.

- **Flags:** `--dir` (required)
- **Reads (all optional, gracefully absent):** `serp-processed.json`, `keywords-processed.json`, `keywords-filtered.json`, `page-structure.json`, `content-topics.json`, `entity-prominence.json`, `competitors-data.json`
- **Output:** writes `briefing-data.json` to `--dir`

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

### Utility modules

These are imported by pipeline scripts or used by specific skills:

| Module | Purpose |
|--------|---------|
| `extract-keywords.mjs` | Shared ES module that normalizes keyword records from DataForSEO responses |
| `merge-keywords.mjs` | Deduplicates keywords from two raw response files |
| `prepare-strategist-data.mjs` | Builds a data skeleton for the content-strategy skill |
| `merge-qualitative.mjs` | Merges LLM qualitative output back into briefing-data.json |
| `summarize-briefing.mjs` | Generates a concise briefing summary for token-efficient display |
| `score-draft-wdfidf.mjs` | Scores a draft against WDF*IDF proof keywords |
| `tokenizer.mjs` | Deterministic text tokenization with stopword filtering (de/en) |
| `slugify.mjs` | URL-safe slug generation with German umlaut transliteration |
| `load-api-config.mjs` | Loads and parses `api.env` credentials |
| `preflight.mjs` | Pre-run validation of API config and environment |
| `resolve-location.mjs` | Maps ISO country codes to DataForSEO location codes |

### Standalone scripts

| Script | Purpose |
|--------|---------|
| `scripts/build-idf-table.mjs` | Computes IDF table from Wikipedia corpus (one-time setup) |
| `scripts/clean-output.mjs` | Deletes old output directories by age threshold |

## Qualitative Analysis (Phase 2)

After `briefing-data.json` is assembled, a single LLM call fills these 6 null fields:

| Field | Description |
|-------|-------------|
| `entity_clusters` | Grouped entities with semantic relationships and prominence data |
| `geo_audit` | GEO (Generative Engine Optimization) readiness assessment |
| `content_format_recommendation` | Recommended content format based on SERP and competitor signals |
| `unique_angles` | Differentiation opportunities not covered by competitors |
| `aio_strategy` | Strategy for AI Overview optimization |
| `briefing` | Final assembled content briefing document (9-section markdown) |

**Data integrity constraint:** The LLM never re-ranks keywords, re-scores opportunities, modifies competitor data, or alters any deterministic field. It reads the skeleton and fills nulls only.

## Article Draft (Phase 3)

An optional phase that transforms the content brief into a publish-ready article:

- Enforces SEO best practices (primary keyword in title/H1/first 100 words, secondary keyword distribution)
- Follows outline from brief exactly
- Applies brand voice guidelines from selected template
- Generates meta description, title tag, alt text suggestions
- Produces `draft-<slug>.md` with meta table, article content, and TODO/VERIFY markers for editorial review

## Output Directory

Each pipeline run produces a dated directory:

```
output/2026-03-23_thailand-urlaub/
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
  qualitative.json                # LLM-generated qualitative fields (Phase 2 intermediate)
  brief-thailand-urlaub.md        # Final content briefing (Phase 2 output)
  draft-thailand-urlaub.md        # Article draft (Phase 3 output, optional)
```

## Project Structure

```
src/
  utils/
    resolve-location.mjs          # Market code -> DataForSEO location code
    slugify.mjs                    # URL-safe slug generator (ö->oe, ä->ae, ü->ue, ß->ss)
    tokenizer.mjs                  # Deterministic tokenization + stopword filtering
    load-api-config.mjs            # api.env credential loader
    preflight.mjs                  # Pre-run environment validation
    location-codes.json            # ISO -> numeric location mapping (16 markets)
    stopwords.json                 # German + English stopword lists
    idf-de.json                    # IDF reference corpus (Leipzig Wikipedia 1M)
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
    merge-qualitative.mjs          # Merge LLM qualitative output into data skeleton
    summarize-briefing.mjs         # Token-efficient briefing summary
    score-draft-wdfidf.mjs         # WDF*IDF scoring for draft quality

scripts/
  build-idf-table.mjs             # One-time IDF table builder from Wikipedia corpus
  clean-output.mjs                 # Delete old output directories

test/
  scripts/
    *.test.mjs                     # 25 test files, 552 tests (node --test)

.claude/
  skills/
    seo-content-pipeline/          # Full pipeline orchestrator
    seo-keyword-research/          # Keyword research skill
    competitor-analysis/           # Competitor analysis skill
    content-strategy/              # Content strategy skill
    content-briefing/              # Content briefing skill
    content-draft/                 # Article draft skill

templates/
  template-reisemagazin.md         # Travel magazine article template
  template-urlaubsseite.md         # Transactional destination page template
  DT_ToV_v3.md                     # Brand tone of voice (v3, AI-native)
  DT_ToV_v2.md                     # Brand tone of voice (v2)
  DT_ToneOfVoice.md               # Brand tone of voice (v1)

output/                            # Generated pipeline runs (gitignored)
api.env.example                    # API configuration template
package.json                       # Project config + test runner
```

## Testing

25 test files, 552 passing tests, 0 failures. Zero external test dependencies -- uses Node.js built-in `node --test`.

```bash
npm test
```

Every deterministic script has byte-identity tests: given the same input JSON, the script produces the exact same output, byte for byte. Tests include an end-to-end integration test that validates the full pipeline flow with fixture data.

## Design Decisions

**Determinism first.** The LLM should guess, infer, and interpret as little as possible. Data extraction is handled by deterministic scripts that produce byte-identical output for the same input. The LLM's role is constrained to qualitative analysis only, operating on a pre-built data skeleton with null placeholders.

**Tag, don't delete.** Filtered keywords are tagged with `filter_status` and `filter_reason` rather than removed. This preserves a full audit trail and lets downstream steps make informed decisions.

**Null placeholder strategy.** All qualitative fields are explicitly set to `null` in the data skeleton. The LLM's job is to fill those nulls -- nothing else. This makes it trivial to verify that deterministic data was not modified.

**Stable sorting everywhere.** All array sorts use stable comparison functions with tiebreakers (typically alphabetical on keyword string). This guarantees byte-identical output across runs and Node.js versions.

**Year normalization.** Keywords containing year references (e.g. "thailand urlaub 2025") are normalized to the current year to prevent stale data from skewing cluster formation.

**JSON in, JSON out via stdout.** Every script reads JSON from files/flags and writes JSON to stdout. This enables Unix-style piping and makes each script independently testable.

**Local extractor dependencies.** jsdom and @mozilla/readability are installed in `src/extractor/` with their own `package.json`, keeping the core pipeline lightweight.

**IDF-boosted term scoring.** Content topic analysis uses a production IDF table (Leipzig Wikipedia 1M corpus) to boost topic-specific terms and downweight common language patterns.

**Caching with TTL.** SERP data is cached automatically; `--force` bypasses the cache; `--max-age` controls expiration (default 7 days). Avoids unnecessary API calls during iterative development.

## Supported Markets

The pipeline supports 16 markets via `src/utils/location-codes.json`:

| Code | Market | Code | Market |
|------|--------|------|--------|
| `de` | Germany | `nl` | Netherlands |
| `at` | Austria | `pl` | Poland |
| `ch` | Switzerland | `br` | Brazil |
| `us` | United States | `au` | Australia |
| `gb` | United Kingdom | `ca` | Canada |
| `fr` | France | `in` | India |
| `es` | Spain | `jp` | Japan |
| `it` | Italy | | |

## Troubleshooting

### HTTP 403 from DataForSEO

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

### Missing extractor dependencies

**Symptom:** `Error: Cannot find module 'jsdom'` or `MODULE_NOT_FOUND` from `extract-page.mjs`

**Cause:** `src/extractor/node_modules` does not exist -- dependencies are installed separately from root

**Fix:**

```bash
cd src/extractor && npm install && cd ../..
```

### ENOTDIR / output directory errors

**Symptom:** `ENOTDIR: not a directory` or `ENOENT: no such file or directory` during pipeline run

**Cause:** A file exists where a directory is expected, or the output path structure is wrong

**Fix:** Ensure the `output/` directory exists and is writable. Delete any stale files that conflict with expected directory paths.

### Base64 encoding of credentials

**Symptom:** `API error 401` despite correct login/password

**Cause:** `DATAFORSEO_AUTH` in `api.env` is not properly base64-encoded, or includes trailing whitespace/newline

**Fix:** Regenerate with:

```bash
echo -n 'login:password' | base64
```

The `-n` flag is critical -- without it, a newline gets encoded into the credentials.

### Stale SERP cache

**Symptom:** Pipeline returns old SERP data even after the search landscape changed

**Cause:** `fetch-serp.mjs` caches results in `serp-raw.json` and reuses them by default

**Fix:** Re-run with `--force` flag to bypass the cache:

```bash
node src/serp/fetch-serp.mjs "keyword" --market de --language de --force
```

### Node.js version too old

**Symptom:** Syntax errors on `import` statements or `AbortSignal.timeout is not a function`

**Cause:** Node.js < 18 does not support ESM, `AbortSignal.timeout()`, or the built-in test runner

**Fix:** Upgrade to Node.js 18 or later. Check with:

```bash
node --version
```
