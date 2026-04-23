# SEO Content Creation Pipeline

Deterministic SEO content pipeline — Python modules handle all data extraction; LLM calls are constrained to qualitative analysis on a pre-built data skeleton.

> Originally implemented in Node.js; see git history for the legacy tree.

## Architecture

Every byte of data processing is handled by deterministic Python modules that produce identical output for identical input. LLM calls are confined to three qualitative stages: filling null placeholders in the briefing skeleton, assembling the final briefing markdown, and (optionally) generating the article draft. The LLM never re-ranks, re-scores, or modifies any deterministic field.

The pipeline runs in three phases:

- **Phase 1 (deterministic):** Pipeline modules fetch, parse, cluster, score, and assemble all keyword, SERP, competitor, and content analysis data into `briefing-data.json`. Every intermediate file is JSON-in, JSON-out.
- **Phase 2 (LLM):** Qualitative fields are filled on the skeleton, then the final briefing markdown is assembled. The LLM operates on the pre-built skeleton and cannot alter deterministic data.
- **Phase 3 (LLM, optional):** Generates a publish-ready article draft from the content briefing. A fact-check stage can verify the draft against web sources.

```
                         Seed Keyword + Market
                                |
               +----------------+----------------+
               |                                 |
               v                                 v
    +---------------------+           +---------------------+
    | keywords/           |           | serp/               |
    | fetch_keywords.py   |           | fetch_serp.py       |
    | DataForSEO related, |           | DataForSEO SERP     |
    | suggestions, KFK    |           | (async task_post/get)|
    +---------------------+           +---------------------+
               |                                 |
               v                                 v
    +---------------------+           +---------------------+
    | keywords/           |           | serp/               |
    | process_keywords.py |           | process_serp.py     |
    | intent, clusters,   |           | AI Overview, PAA,   |
    | opportunity scores  |           | featured snippets   |
    +---------------------+           +---------------------+
               |                                 |
               v                          +------+------+
    +---------------------+               |             |
    | keywords/           |               v             v
    | filter_keywords.py  |    +----------------+  +------------------+
    | blocklist, brand,   |    | extractor/     |  | serp/            |
    | FAQ priority        |    | extract_page.py|  | assemble_        |
    +---------------------+    | (per URL)      |  | competitors.py   |
               |               +----------------+  +------------------+
               |                      |                    |
               |               pages/<domain>.json         |
               |                      |                    |
               |                      v                    |
               |          +--------------------------+     |
               |          | analysis/                |     |
               |          | analyze_page_structure.py|     |
               |          | analyze_content_topics.py|     |
               |          | compute_entity_prominence|     |
               |          +--------------------------+     |
               |                      |                    |
               +----------+-----------+--------------------+
                          |
                          v
               +---------------------+
               | analysis/           |  consolidates everything
               | assemble_briefing_  |  into briefing-data.json
               | data.py             |
               +---------------------+
                          |
                  briefing-data.json
                     (Phase 1 done)
                          |
                          v
               +---------------------+
               | analysis/           |  fills qualitative
               | fill_qualitative.py |  null fields (LLM)
               +---------------------+
                          |
                          v
               +---------------------+
               | analysis/           |  final briefing markdown
               | assemble_briefing_  |  (LLM)
               | md.py               |
               +---------------------+
                          |
                    brief-<slug>.md
                          |
                          v
               +---------------------+
               | drafting/           |  SEO-optimized article
               | write_draft.py      |  (LLM, optional)
               +---------------------+
                          |
                    draft-<slug>.md
                          |
                          v
               +---------------------+
               | analysis/           |  fact-check + ToV audit
               | fact_check.py       |  (LLM + WebSearch)
               | tov_check.py        |
               +---------------------+
```

## Prerequisites

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- A [DataForSEO](https://dataforseo.com/) account (login + password)
- An LLM provider API key (Anthropic, OpenAI, or Google)

## Setup

1. Clone the repository:

   ```bash
   git clone <repo-url>
   cd ContentCreationPipeline
   ```

2. Install dependencies:

   ```bash
   uv sync --all-extras
   ```

   This creates a `.venv` and installs all runtime dependencies plus the CLI (`typer`), API (`fastapi`), dev (`pytest`, `ruff`), and LLM-provider extras.

3. Configure API credentials:

   ```bash
   cp api.env.example api.env
   ```

   Edit `api.env` and set your DataForSEO credentials plus LLM provider config:

   ```env
   SEO_PROVIDER=dataforseo
   DATAFORSEO_AUTH=<base64 of login:password>
   DATAFORSEO_BASE=https://api.dataforseo.com/v3
   SEO_MARKET=de
   SEO_LANGUAGE=de

   LLM_PROVIDER=anthropic
   LLM_MODEL=claude-sonnet-4-20250514
   LLM_API_KEY=sk-ant-...
   ```

   Generate the DataForSEO auth string with: `echo -n 'login:password' | base64`

4. Verify the setup:

   ```bash
   uv run pytest
   ```

## Usage

### Full pipeline

Run the complete pipeline end-to-end via the Typer CLI:

```bash
uv run seo-pipeline run-pipeline "thailand urlaub" \
  --location de --language de \
  --tov templates/DT_ToV_v3.md \
  --template templates/template-reisemagazin.md \
  --user-domain example.com \
  --business-context "Tour operator selling guided Thailand trips"
```

The `run-pipeline` subcommand orchestrates all 11 stages (SERP fetch, SERP processing, page extraction, keyword fetch/process/filter, content analysis, briefing assembly, qualitative fill, briefing markdown, article draft, fact-check).

### Claude Code skills

Each pipeline phase is also available as a Claude Code skill (from `.claude/skills/`):

| Skill | Scope |
|-------|-------|
| `/seo-content-pipeline` | Full pipeline orchestrator |
| `/seo-keyword-research` | Fetch keyword data from DataForSEO, cluster by intent and volume |
| `/competitor-analysis` | Analyze top-ranking pages, extract structure and content signals |
| `/content-strategy` | Synthesize keyword + competitor data into a prioritized content roadmap |
| `/content-briefing` | Generate a detailed writing brief from `briefing-data.json` |
| `/content-draft` | Write a publish-ready article from an existing brief |
| `/content-revision` | Revise an existing draft with structured SME input |
| `/fact-check` | Verify factual claims in a draft via WebSearch |
| `/tov-check` | Run a tone-of-voice compliance audit on a draft |

### Direct CLI

Every pipeline stage can be run standalone for debugging, piping, or integration. See `uv run seo-pipeline --help` for the full command list.

```bash
# Keyword research
uv run seo-pipeline fetch-keywords "thailand urlaub" \
  --market de --language de --outdir output/2026-04-23_thailand-urlaub --limit 50
uv run seo-pipeline process-keywords \
  --related output/2026-04-23_thailand-urlaub/keywords-related-raw.json \
  --suggestions output/2026-04-23_thailand-urlaub/keywords-suggestions-raw.json \
  --seed "thailand urlaub" \
  --output output/2026-04-23_thailand-urlaub/keywords-processed.json
uv run seo-pipeline filter-keywords \
  --keywords output/2026-04-23_thailand-urlaub/keywords-processed.json \
  --serp output/2026-04-23_thailand-urlaub/serp-processed.json \
  --seed "thailand urlaub" \
  --output output/2026-04-23_thailand-urlaub/keywords-filtered.json

# SERP analysis
uv run seo-pipeline fetch-serp "thailand urlaub" \
  --market de --language de --force \
  --outdir output/2026-04-23_thailand-urlaub
uv run seo-pipeline process-serp output/2026-04-23_thailand-urlaub/serp-raw.json \
  --top 10 --output output/2026-04-23_thailand-urlaub/serp-processed.json

# Page extraction
uv run seo-pipeline extract-page "https://example.com/page" \
  --output output/2026-04-23_thailand-urlaub/pages/example-com.json

# Content analysis
uv run seo-pipeline analyze-page-structure \
  --pages-dir output/2026-04-23_thailand-urlaub/pages/ \
  --output output/2026-04-23_thailand-urlaub/page-structure.json
uv run seo-pipeline analyze-content-topics \
  --pages-dir output/2026-04-23_thailand-urlaub/pages/ \
  --seed "thailand urlaub" \
  --output output/2026-04-23_thailand-urlaub/content-topics.json
uv run seo-pipeline compute-entity-prominence \
  --entities output/2026-04-23_thailand-urlaub/content-topics.json \
  --pages-dir output/2026-04-23_thailand-urlaub/pages/ \
  --output output/2026-04-23_thailand-urlaub/entity-prominence.json

# Briefing assembly
uv run seo-pipeline assemble-briefing-data \
  --dir output/2026-04-23_thailand-urlaub/ \
  --market de --language de
uv run seo-pipeline summarize-briefing \
  --file output/2026-04-23_thailand-urlaub/briefing-data.json

# LLM stages
uv run seo-pipeline fill-qualitative --dir output/2026-04-23_thailand-urlaub/
uv run seo-pipeline assemble-briefing-md --dir output/2026-04-23_thailand-urlaub/
uv run seo-pipeline write-draft --brief output/2026-04-23_thailand-urlaub/brief-thailand-urlaub.md

# Post-draft checks
uv run seo-pipeline extract-claims \
  --draft output/2026-04-23_thailand-urlaub/draft-thailand-urlaub.md \
  --output output/2026-04-23_thailand-urlaub/claims-extracted.json
uv run seo-pipeline fact-check \
  --draft output/2026-04-23_thailand-urlaub/draft-thailand-urlaub.md
uv run seo-pipeline tov-check \
  --draft output/2026-04-23_thailand-urlaub/draft-thailand-urlaub.md
```

All subcommands that produce JSON support `--output <path>` for file output (default: stdout).

## Pipeline Stages (Phase 1 — deterministic)

Each module reads structured input (JSON files or arguments) and produces structured output. All sorting is stable. All output is byte-identical for identical input.

### 1. `serp/fetch_serp.py`

Calls DataForSEO `task_post` and `task_get/advanced` endpoints to retrieve top organic search results. Handles caching automatically: if `serp-raw.json` exists and is fresh, reuses it; otherwise fetches from the API.

- **CLI:** `uv run seo-pipeline fetch-serp "<keyword>" --market <code> --language <code> --outdir <dir>`
- **Flags:** `--depth` (default 10), `--timeout` (default 120s), `--force` (bypass cache), `--max-age` (default 7 days)
- **Output:** `serp-raw.json` in `--outdir`

### 2. `keywords/fetch_keywords.py`

Calls DataForSEO `related_keywords`, `keyword_suggestions`, and `keywords_for_keywords` endpoints, saves raw responses, then merges internally to produce a deduplicated keyword list.

- **CLI:** `uv run seo-pipeline fetch-keywords "<seed>" --market <code> --language <code> --outdir <dir>`
- **Flags:** `--limit` (default 50)
- **Output:** `keywords-related-raw.json`, `keywords-suggestions-raw.json`, `keywords-for-keywords-raw.json`, `keywords-expanded.json`

### 3. `keywords/process_keywords.py`

Merges raw API responses into a structured skeleton with intent tags (DE+EN regex), Jaccard-similarity n-gram clusters (threshold >= 0.5), and opportunity scores. Null placeholders for LLM-only fields (`cluster_label`, `strategic_notes`).

- **CLI:** `uv run seo-pipeline process-keywords --related <file> --suggestions <file> --seed <keyword>`
- **Flags:** `--volume`, `--kfk`, `--brands`, `--output`
- **Output:** JSON with `clusters[]`, each containing `keywords[]` with intent, volume, CPC, opportunity score

### 4. `keywords/filter_keywords.py`

Tags keywords with filter status (blocklist, brand, foreign-language) without deleting them — tag, don't delete. Computes FAQ prioritization by scoring PAA questions against keyword token overlaps.

- **CLI:** `uv run seo-pipeline filter-keywords --keywords <file> --serp <file> --seed <keyword>`
- **Flags:** `--blocklist`, `--brands`, `--output`
- **Output:** JSON with `clusters[]` (keywords annotated with `filter_status` + `filter_reason`), `faq_selection[]`, `removal_summary`
- **Default blocklist:** `seo_pipeline/data/blocklist_default.json` (ethics, booking portals, spam patterns)

### 5. `serp/process_serp.py`

Parses a raw DataForSEO advanced SERP response into structured features: AI Overview, featured snippets, People Also Ask, related searches, discussions, video, top stories, knowledge graph, commercial and local signals.

- **CLI:** `uv run seo-pipeline process-serp <file> --top <n>`
- **Output:** JSON with `serp_features`, `competitors[]`

### 6. `extractor/extract_page.py`

Fetches a URL and parses it with `trafilatura` + `beautifulsoup4`. Extracts headings (h2-h4), word count, link counts, meta tags, and HTML content signals (FAQ sections, tables, lists, video embeds, images, forms).

- **CLI:** `uv run seo-pipeline extract-page "<URL>"`
- **Output:** JSON with `headings[]`, `word_count`, `link_count`, `html_signals`, `main_content_text`

### 7. Content analysis modules

Three modules that analyze the extracted pages:

**`analysis/analyze_page_structure.py`** — Detects content modules (FAQ, table, list, video, form, image gallery) per competitor page. Computes per-section word/sentence counts, depth scores, and cross-competitor module frequency.

**`analysis/analyze_content_topics.py`** — Extracts n-gram term frequencies with IDF boost (Leipzig Wikipedia 1M corpus), clusters headings by Jaccard overlap, and reports content format signals across competitors.

**`analysis/compute_entity_prominence.py`** — Re-computes entity mention counts across competitor page texts using exact synonym matching. Records discrepancies against any prior LLM-supplied values.

### 8. `analysis/assemble_briefing_data.py`

Consolidates all pipeline outputs from a run directory into a single `briefing-data.json`. Normalizes years, ranks keyword clusters by total search volume, and sets all qualitative fields to `null`.

- **CLI:** `uv run seo-pipeline assemble-briefing-data --dir <dir>`
- **Flags:** `--market`, `--language`, `--user-domain`, `--business-context`, `--output`
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

Imported by pipeline stages or used by specific skills:

| Module | Purpose |
|--------|---------|
| `keywords/extract_keywords.py` | Normalizes keyword records from DataForSEO responses |
| `keywords/merge_keywords.py` | Deduplicates keywords from related + suggestions + KFK response files |
| `keywords/prepare_strategist_data.py` | Builds a data skeleton for the content-strategy skill |
| `serp/assemble_competitors.py` | Merge SERP data + extracted page JSON into `competitors-data.json` |
| `analysis/merge_qualitative.py` | Merges LLM qualitative output back into `briefing-data.json` |
| `analysis/summarize_briefing.py` | Generates a concise briefing summary for token-efficient display |
| `analysis/score_draft_wdfidf.py` | Scores a draft against competitor pages using WDF*IDF |
| `analysis/extract_claims.py` | Extracts factual claims from draft markdown (deterministic regex) |
| `utils/tokenizer.py` | Deterministic text tokenization with stopword filtering (de/en) |
| `utils/slugify.py` | URL-safe slug generation with German umlaut transliteration |
| `utils/load_api_config.py` | Loads and parses `api.env` credentials |
| `utils/preflight.py` | Pre-run validation of API config and environment |
| `utils/resolve_location.py` | Maps ISO country codes to DataForSEO location codes |
| `utils/text.py`, `utils/math.py` | Shared text and math helpers |

## Qualitative Analysis (Phase 2 — LLM)

After `briefing-data.json` is assembled, two LLM stages produce the final briefing:

### `analysis/fill_qualitative.py` — fills the skeleton

A single batched LLM call fills these null fields:

| Field | Description |
|-------|-------------|
| `entity_clusters` | Grouped entities with semantic relationships and prominence data |
| `geo_audit` | GEO (Generative Engine Optimization) readiness assessment |
| `content_format_recommendation` | Recommended content format based on SERP and competitor signals |
| `unique_angles` | Differentiation opportunities not covered by competitors |
| `aio_strategy` | Strategy for AI Overview optimization |

Writes `qualitative.json`, then `merge_qualitative.py` merges it back into `briefing-data.json`.

### `analysis/assemble_briefing_md.py` — writes the briefing

A second LLM call assembles the final 9-section briefing markdown (`brief-<slug>.md`) from the filled skeleton, optionally constrained by a template and tone-of-voice guide.

**Data integrity constraint:** Neither LLM stage re-ranks keywords, re-scores opportunities, modifies competitor data, or alters any deterministic field. They read the skeleton and fill nulls only.

## Article Draft (Phase 3 — LLM, optional)

`drafting/write_draft.py` transforms the content brief into a publish-ready article:

- Enforces SEO best practices (primary keyword in title/H1/first 100 words, secondary keyword distribution)
- Follows outline from brief exactly
- Applies brand voice guidelines from selected template
- Generates meta description, title tag, alt text suggestions
- Produces `draft-<slug>.md` with meta table, article content, and TODO/VERIFY markers for editorial review

### Post-draft checks

- **`analysis/extract_claims.py`** — Deterministic regex-based extraction of factual claims from the draft.
- **`analysis/fact_check.py`** — Verifies each extracted claim via WebSearch, produces `fact-check-report.json` / `.md`, and applies corrections.
- **`analysis/tov_check.py`** — Runs a tone-of-voice compliance audit against a ToV guide (default: `templates/DT_ToV_v3.md`).
- **`analysis/score_draft_wdfidf.py`** — WDF*IDF scoring against competitor proof keywords.

## Output Directory

Each pipeline run produces a dated directory:

```
output/2026-04-23_thailand-urlaub/
  keywords-related-raw.json              # Raw DataForSEO related keywords response
  keywords-suggestions-raw.json          # Raw DataForSEO suggestions response
  keywords-for-keywords-raw.json         # Raw DataForSEO keywords-for-keywords response
  keywords-expanded.json                 # Deduplicated merged keywords
  keywords-processed.json                # Clustered, intent-tagged, scored keywords
  keywords-filtered.json                 # Tagged with filter status + FAQ selection
  serp-raw.json                          # Raw DataForSEO SERP response
  serp-processed.json                    # Extracted SERP features + competitor list
  pages/
    example-com.json                     # Per-domain page extraction (one per competitor)
    other-site-de.json
  competitors-data.json                  # Merged SERP + page data with null qualitative fields
  page-structure.json                    # Module detection + cross-competitor analysis
  content-topics.json                    # Proof keywords, entity candidates, section weights
  entity-prominence.json                 # Code-verified entity mention counts
  briefing-data.json                     # Consolidated data skeleton (Phase 1 output)
  qualitative.json                       # LLM-generated qualitative fields (Phase 2 intermediate)
  brief-thailand-urlaub.md               # Final content briefing (Phase 2 output)
  draft-thailand-urlaub.md               # Article draft (Phase 3 output, optional)
  claims-extracted.json                  # Deterministic claim extraction from draft
  fact-check-report.json / .md           # Fact-check results (if run)
```

## Project Structure

```
seo_pipeline/
  cli/
    main.py                              # Typer CLI entrypoint (seo-pipeline)
  serp/
    fetch_serp.py                        # SERP data fetcher (async task_post/task_get)
    process_serp.py                      # SERP feature extraction from raw API response
    assemble_competitors.py              # Merge SERP data + page extractions
  keywords/
    fetch_keywords.py                    # DataForSEO API caller + merge orchestrator
    extract_keywords.py                  # Keyword record normalization
    merge_keywords.py                    # Deduplication + stable sort by volume
    process_keywords.py                  # Intent tagging, Jaccard clustering, scoring
    filter_keywords.py                   # Blocklist/brand/language tagging + FAQ priority
    prepare_strategist_data.py           # Data skeleton for content-strategy skill
  extractor/
    extract_page.py                      # trafilatura + BeautifulSoup page parser
  analysis/
    analyze_page_structure.py            # Module detection, section depth scoring
    analyze_content_topics.py            # TF-IDF proof keywords, entity candidates
    compute_entity_prominence.py         # Code-verified entity counts across pages
    assemble_briefing_data.py            # Consolidate all outputs into briefing-data.json
    fill_qualitative.py                  # LLM qualitative field fill
    merge_qualitative.py                 # Merge LLM qualitative output into data skeleton
    assemble_briefing_md.py              # LLM final briefing markdown assembly
    summarize_briefing.py                # Token-efficient briefing summary
    score_draft_wdfidf.py                # WDF*IDF scoring for draft quality
    extract_claims.py                    # Deterministic claim extraction from draft
    fact_check.py                        # LLM + WebSearch claim verification
    tov_check.py                         # Tone-of-voice compliance audit
  drafting/
    write_draft.py                       # LLM article draft generation
  llm/
    client.py                            # LLM provider client (via litellm)
    config.py                            # LLMConfig (provider, model, keys)
    prompts/                             # Prompt templates
  models/
    analysis.py, common.py, keywords.py, # Pydantic models for structured I/O
    llm_responses.py, page.py, serp.py
  utils/
    resolve_location.py                  # Market code -> DataForSEO location code
    slugify.py                           # URL-safe slug generator (ö->oe, ä->ae, ü->ue, ß->ss)
    tokenizer.py                         # Deterministic tokenization + stopword filtering
    text.py, math.py                     # Shared helpers
    load_api_config.py                   # api.env credential loader
    preflight.py                         # Pre-run environment validation
  data/
    location_codes.json                  # ISO -> numeric location mapping (15 markets)
    stopwords.json                       # German + English stopword lists
    idf_de.json                          # IDF reference corpus (Leipzig Wikipedia 1M)
    blocklist_default.json               # Default keyword blocklist
  api/                                   # FastAPI surface (hosted pipeline, WIP)

tests/                                   # pytest test suite
  test_serp/, test_keywords/, test_analysis/, test_extractor/,
  test_utils/, test_llm/, test_drafting/, test_models/
  fixtures/                              # Test input fixtures
  golden/                                # Golden snapshot outputs

.claude/
  skills/                                # Claude Code skill definitions
    seo-content-pipeline/                # Full pipeline orchestrator
    seo-keyword-research/                # Keyword research skill
    competitor-analysis/                 # Competitor analysis skill
    content-strategy/                    # Content strategy skill
    content-briefing/                    # Content briefing skill
    content-draft/                       # Article draft skill
    content-revision/                    # SME-driven revision skill
    fact-check/                          # Fact-check skill
    tov-check/                           # ToV audit skill

templates/
  template-reisemagazin.md               # Travel magazine article template
  template-urlaubsseite.md               # Transactional destination page template
  template-themenseite.md                # Topic page template
  DT_ToV_v3.md                           # Brand tone of voice (v3, AI-native)
  DT_ToV_v2.md                           # Brand tone of voice (v2)
  DT_ToneOfVoice.md                      # Brand tone of voice (v1)

output/                                  # Generated pipeline runs (gitignored)
api.env.example                          # API configuration template
pyproject.toml                           # Project config + dependencies
uv.lock                                  # Locked dependency versions
```

## Testing

```bash
uv run pytest
```

Uses `pytest` with `pytest-asyncio`. Every deterministic module has byte-identity tests: given the same input JSON, the module produces the exact same output. Golden snapshot tests under `tests/golden/` verify end-to-end pipeline behavior against frozen fixture data.

## Design Decisions

**Determinism first.** The LLM should guess, infer, and interpret as little as possible. Data extraction is handled by deterministic modules that produce byte-identical output for the same input. The LLM's role is constrained to qualitative analysis only, operating on a pre-built data skeleton with null placeholders.

**Tag, don't delete.** Filtered keywords are tagged with `filter_status` and `filter_reason` rather than removed. This preserves a full audit trail and lets downstream steps make informed decisions.

**Null placeholder strategy.** All qualitative fields are explicitly set to `null` in the data skeleton. The LLM's job is to fill those nulls — nothing else. This makes it trivial to verify that deterministic data was not modified.

**Stable sorting everywhere.** All array sorts use stable comparison functions with tiebreakers (typically alphabetical on keyword string). This guarantees byte-identical output across runs and Python versions.

**Year normalization.** Keywords containing year references (e.g. "thailand urlaub 2025") are normalized to the current year to prevent stale data from skewing cluster formation.

**Structured I/O everywhere.** Every module reads and writes Pydantic-validated structures, serialized to JSON at module boundaries. This makes each stage independently testable and pipeable.

**IDF-boosted term scoring.** Content topic analysis uses a production IDF table (Leipzig Wikipedia 1M corpus) to boost topic-specific terms and downweight common language patterns.

**Caching with TTL.** SERP data is cached automatically; `--force` bypasses the cache; `--max-age` controls expiration (default 7 days). Avoids unnecessary API calls during iterative development.

## Supported Markets

The pipeline supports 15 markets via `seo_pipeline/data/location_codes.json`:

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

**Symptom:** `API error 403: ...` from `fetch-serp` or `fetch-keywords`

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

### ENOTDIR / output directory errors

**Symptom:** `FileNotFoundError: No such file or directory` or similar during pipeline run

**Cause:** A file exists where a directory is expected, or the output path structure is wrong

**Fix:** Ensure the `output/` directory exists and is writable. Delete any stale files that conflict with expected directory paths.

### Base64 encoding of credentials

**Symptom:** `API error 401` despite correct login/password

**Cause:** `DATAFORSEO_AUTH` in `api.env` is not properly base64-encoded, or includes trailing whitespace/newline

**Fix:** Regenerate with:

```bash
echo -n 'login:password' | base64
```

The `-n` flag is critical — without it, a newline gets encoded into the credentials.

### Stale SERP cache

**Symptom:** Pipeline returns old SERP data even after the search landscape changed

**Cause:** `fetch-serp` caches results in `serp-raw.json` and reuses them by default

**Fix:** Re-run with `--force` to bypass the cache:

```bash
uv run seo-pipeline fetch-serp "keyword" --market de --language de --outdir <dir> --force
```

### Python version too old

**Symptom:** Syntax errors on type annotations or `ImportError` on standard library features

**Cause:** Python < 3.11 is not supported (see `pyproject.toml` `requires-python`)

**Fix:** Upgrade to Python 3.11+. `uv` will select a compatible interpreter automatically when running `uv sync`. Check with:

```bash
uv run python --version
```

### LLM provider not configured

**Symptom:** `ValueError: LLM_PROVIDER not set` when running Phase 2 stages

**Cause:** `api.env` is missing LLM configuration, or the environment variables were not loaded

**Fix:** Set `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_API_KEY` in `api.env`. Supported providers: `anthropic`, `openai`, `google` (routed via `litellm`).
