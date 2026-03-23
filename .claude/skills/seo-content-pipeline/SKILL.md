---
name: seo-content-pipeline
description: Run the full SEO content pipeline end-to-end. Deterministic scripts handle data extraction and analysis; a single LLM call produces the qualitative briefing. Use when the user wants to run the complete pipeline for a topic.
---

# SEO Content Pipeline

Run the full SEO content pipeline: deterministic data extraction and analysis, then a single LLM call for the content briefing.

## Architecture

The pipeline has two phases:

1. **Deterministic scripts** (Phase 1): Seven scripts that extract, process, analyze, and consolidate data. Same inputs always produce byte-identical output. No LLM involvement.
2. **Single LLM call** (Phase 2): One prompt that reads the consolidated `briefing-data.json` and fills only qualitative fields (entity categorization, GEO audit, content format recommendation, unique angles, AIO strategy) before assembling the final briefing document.

This replaces the previous architecture that used multiple LLM calls for analysis tasks. All quantitative analysis is now deterministic.

## Inputs

Ask the user for:
1. **Seed keyword or topic** (required)
2. **Your domain** (optional -- excluded from competitor analysis)
3. **SEO market** (default: `de` -- used for SERP and keyword API calls)
4. **Business context** -- what do you sell/offer? who is your audience?
5. **Content goals** -- traffic, leads, authority, conversions?
6. **Content template** -- scan `templates/` for `template-*.md` files and present as options, or "Kein Template"
7. **Brand voice / tone** (optional) -- scan `templates/` for files matching `*ToneOfVoice*` or `*tov*` (case-insensitive)

## Pipeline

`$OUT` = the run-specific output directory (derived by `fetch-serp.mjs`, **never constructed manually**).

All output goes to `$OUT`.

### Phase 1: Deterministic Data Pipeline

Run each script in order. If `briefing-data.json` already exists in the output directory, skip the entire Phase 1.

> **Token budget:** All scripts use `--output` flags, so stdout should be minimal. If a step produces unexpected verbose output, pipe through `| head -20` to keep the context window lean. Never suppress stderr.

#### Step 0: Fetch SERP (determines $OUT)

**Do NOT construct `$OUT` yourself.** German umlauts must be transliterated correctly (ö→oe, ä→ae, ü→ue, ß→ss) — let `fetch-serp.mjs` handle this via its built-in `slugify`.

```bash
node src/serp/fetch-serp.mjs "<seed-keyword>" \
  --market "$SEO_MARKET" --language "$SEO_LANGUAGE" \
  --outdir $OUT/
```

The script creates `$OUT` and outputs the path to stderr. Use that path as `$OUT` for all subsequent steps.

**Note:** Cached SERP data in `serp-raw.json` is automatically reused when available; pass `--force` to bypass the cache and fetch fresh data. The `--max-age` flag (default 7 days) controls cache expiration. `--language` is required (e.g. `de` for German).

#### Step 1: SERP Processing
```bash
node src/serp/process-serp.mjs $OUT/serp-raw.json --top 10 --output $OUT/serp-processed.json
```
Input: raw DataForSEO SERP JSON (positional arg). `--top N` limits organic results (default 10). Writes structured JSON to the specified file via `--output`.

#### Step 2: Page Extraction
```bash
# For each competitor URL from serp-processed.json:
node src/extractor/extract-page.mjs "<competitor-url>" --output $OUT/pages/<competitor-slug>.json
```
Input: positional URL arg. Writes JSON to the specified file via `--output`.

#### Step 3: Keyword Processing
```bash
node src/keywords/process-keywords.mjs \
  --related $OUT/keywords-related-raw.json \
  --suggestions $OUT/keywords-suggestions-raw.json \
  --seed "<seed-keyword>" \
  [--volume $OUT/keywords-volume-raw.json] \
  [--brands "brand1,brand2"] \
  --output $OUT/keywords-processed.json
```
Merges raw DataForSEO responses, clusters related keywords, computes difficulty and opportunity scores. Writes JSON to the specified file via `--output`.

#### Step 4: Keyword Filtering
```bash
node src/keywords/filter-keywords.mjs \
  --keywords $OUT/keywords-processed.json \
  --serp $OUT/serp-processed.json \
  --seed "<seed-keyword>" \
  [--blocklist blocklist.json] \
  [--brands "brand1,brand2"] \
  --output $OUT/keywords-filtered.json
```
Applies ethics, brand, and off-topic filters. Prioritizes FAQ questions with token overlap scoring. Writes JSON to the specified file via `--output`.

#### Step 5: Page Structure Analysis
```bash
node src/analysis/analyze-page-structure.mjs --pages-dir $OUT/pages/ --output $OUT/page-structure.json
```
Detects modules (FAQ, table, list, video, image_gallery, form), computes content depth scores, classifies modules as common or rare across competitors. Writes JSON to the specified file via `--output`.

#### Step 6: Content Topic Analysis
```bash
node src/analysis/analyze-content-topics.mjs --pages-dir $OUT/pages/ --seed "<seed-keyword>" --output $OUT/content-topics.json
```
TF-IDF entity extraction, Jaccard heading clustering, section weight analysis, proof keyword identification. Writes JSON to the specified file via `--output`.

#### Step 7: Briefing Data Assembly
```bash
node src/analysis/assemble-briefing-data.mjs --dir $OUT/ \
  --market "$SEO_MARKET" --language "$SEO_LANGUAGE" \
  --user-domain "$USER_DOMAIN" --business-context "$BUSINESS_CONTEXT"
```
Consolidates all pipeline outputs into a single `briefing-data.json` with:
- Ranked keyword clusters (by total search volume)
- Proof keywords and entity candidates with prominence
- Section weights and module frequency (common/rare)
- AIO data and FAQ questions with priority ranking
- Content format signals
- A `qualitative` section with all fields set to `null` (filled by Phase 2)

#### Step 8: Briefing Summary

```bash
node src/analysis/summarize-briefing.mjs --file $OUT/briefing-data.json
```

Prints a compact summary of the assembled data. Show this output to the user and confirm before proceeding to Phase 2. Do NOT read `briefing-data.json` directly — the summary script extracts all necessary stats.

### Phase 2: Content Briefing

Follow the instructions in the `content-briefing` skill to fill qualitative fields and assemble the final briefing document.

**Key constraint:** The LLM does NOT re-count, re-rank, or modify any deterministic data. All quantitative values are pre-computed and authoritative.

Present the final briefing for review.

### Step 3: Content Draft (optional)

Ask the user if they want to generate a full article draft from the brief.

If yes, follow the instructions in the `content-draft` skill:
- Use the brief from Phase 2 as input
- Load keyword and competitor data for SEO and differentiation
- Write the complete article
- Save to `$OUT/draft-<slug>.md`

Present the finished draft for review.

## Output

At the end of the pipeline, the user has:

| File | Description | Source |
|------|-------------|--------|
| `serp-processed.json` | SERP features, AIO data, competitors | Deterministic (Step 1) |
| `competitors-data.json` | Extracted competitor page content | Deterministic (Step 2) |
| `keywords-processed.json` | Clustered keywords with scores | Deterministic (Step 3) |
| `keywords-filtered.json` | Filtered keywords + FAQ ranking | Deterministic (Step 4) |
| `page-structure.json` | Module detection, content depth | Deterministic (Step 5) |
| `content-topics.json` | TF-IDF entities, section weights | Deterministic (Step 6) |
| `briefing-data.json` | Consolidated data + qualitative fields | Deterministic + LLM (Step 7 + Phase 2) |
| `brief-<slug>.md` | Final content briefing document | LLM (Phase 2) |
| `draft-<slug>.md` | Article draft (if requested) | LLM (Step 3) |

All files in `$OUT`.

## Data Flow

```
process-serp.mjs ──────────────┐
extract-page.mjs (per URL) ────┤
process-keywords.mjs ──────────┤
filter-keywords.mjs ───────────┤──> assemble-briefing-data.mjs ──> briefing-data.json
analyze-page-structure.mjs ────┤                                         |
analyze-content-topics.mjs ────┘                                         v
                                                              content-briefing skill
                                                              (single LLM call)
                                                                   |         |
                                                                   v         v
                                                         briefing-data.json  brief-<slug>.md
                                                         (qualitative filled) (final briefing)
```
