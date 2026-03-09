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

All output goes to `output/YYYY-MM-DD_<seed-keyword-slug>/`.

### Phase 1: Deterministic Data Pipeline

Run each script in order. If `briefing-data.json` already exists in the output directory, skip the entire Phase 1.

#### Step 1: SERP Processing
```bash
node src/serp/process-serp.mjs --keyword "<seed-keyword>" --market <market> --out output/YYYY-MM-DD_<slug>/
```
Extracts SERP features (AIO, PAA, featured snippets), identifies competitors, and saves `serp-processed.json`.

#### Step 2: Page Extraction
```bash
# For each competitor URL from serp-processed.json:
node src/extractor/extract-page.mjs --url "<competitor-url>" --out output/YYYY-MM-DD_<slug>/
```
Extracts full readable text, headings, HTML signals, and readability metrics from each competitor page.

#### Step 3: Keyword Processing
```bash
node src/keywords/process-keywords.mjs --keyword "<seed-keyword>" --market <market> --out output/YYYY-MM-DD_<slug>/
```
Expands seed keyword, clusters related keywords, computes difficulty and opportunity scores. Saves `keywords-processed.json`.

#### Step 4: Keyword Filtering
```bash
node src/keywords/filter-keywords.mjs --dir output/YYYY-MM-DD_<slug>/
```
Applies ethics, brand, and off-topic filters. Prioritizes FAQ questions with token overlap scoring. Saves `keywords-filtered.json`.

#### Step 5: Page Structure Analysis
```bash
node src/analysis/analyze-page-structure.mjs --dir output/YYYY-MM-DD_<slug>/
```
Detects modules (FAQ, table, list, video, image_gallery, form), computes content depth scores, classifies modules as common or rare across competitors. Saves `page-structure.json`.

#### Step 6: Content Topic Analysis
```bash
node src/analysis/analyze-content-topics.mjs --dir output/YYYY-MM-DD_<slug>/
```
TF-IDF entity extraction, Jaccard heading clustering, section weight analysis, proof keyword identification. Saves `content-topics.json`.

#### Step 7: Briefing Data Assembly
```bash
node src/analysis/assemble-briefing-data.mjs --dir output/YYYY-MM-DD_<slug>/
```
Consolidates all pipeline outputs into a single `briefing-data.json` with:
- Ranked keyword clusters (by total search volume)
- Proof keywords and entity candidates with prominence
- Section weights and module frequency (common/rare)
- AIO data and FAQ questions with priority ranking
- Content format signals
- A `qualitative` section with all fields set to `null` (filled by Phase 2)

Show the user a summary of what was discovered: number of keywords, clusters, competitors analyzed, SERP features detected. Confirm before proceeding.

### Phase 2: Content Briefing (Single LLM Call)

Follow the instructions in the `content-briefing` skill. This skill:
1. Reads `briefing-data.json` and the selected template
2. Constructs a single LLM prompt with the full data skeleton
3. Fills ONLY qualitative fields (entity categorization, GEO audit, unique angles, format recommendation, AIO strategy)
4. Assembles the final briefing markdown following the template structure
5. Saves `briefing-data.json` (updated) + `brief-<slug>.md`

**Key constraint:** The LLM does NOT re-count, re-rank, or modify any deterministic data. All quantitative values are pre-computed and authoritative.

Present the final briefing for review.

### Step 3: Content Draft (optional)

Ask the user if they want to generate a full article draft from the brief.

If yes, follow the instructions in the `content-draft` skill:
- Use the brief from Phase 2 as input
- Load keyword and competitor data for SEO and differentiation
- Write the complete article
- Save to `output/YYYY-MM-DD_<slug>/draft-<slug>.md`

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

All files in `output/YYYY-MM-DD_<seed-keyword-slug>/`.

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
