# Python Rewrite Plan

This repo is the Python rewrite of [ClaudeContentCreationPipeline](https://github.com/wiz4rd-de/ClaudeContentCreationPipeline) (Node.js, frozen at v1.0.0).

## GitHub Strategy

- **Original repo** (`ClaudeContentCreationPipeline`): archived at v1.0.0, maintenance mode (bugfixes only)
- **This repo** (`ContentCreationPipeline`): Python rewrite with CLI and web API
- Node.js source (`src/`, `package.json`) is kept in this repo during migration for reference and side-by-side testing. It gets removed in Phase 8 after full parity is confirmed.

## Python Project Structure

```
/
  src/                   # Original Node.js source (kept during migration)
  package.json           # Kept so `node src/...` still works during migration
  pyproject.toml         # Python project config
  seo_pipeline/
    __init__.py
    models/              # Pydantic models (shared by CLI, API, and internal code)
      __init__.py
      common.py          # Heading, LinkCount, HtmlSignals
      serp.py            # SerpProcessed, Competitor, AiOverview, etc.
      keywords.py        # Keyword, KeywordCluster, ProcessedKeywords, FilteredKeywords
      page.py            # ExtractedPage, PageStructure
      analysis.py        # ContentTopics, EntityProminence, BriefingData, Claims
    utils/
      __init__.py
      slugify.py
      tokenizer.py
      load_api_config.py
      resolve_location.py
      preflight.py
      math.py            # js_round() — matches JS Math.round() half-up behavior
    serp/
      __init__.py
      fetch_serp.py
      process_serp.py
      assemble_competitors.py
    keywords/
      __init__.py
      fetch_keywords.py
      extract_keywords.py
      merge_keywords.py
      process_keywords.py
      filter_keywords.py
      prepare_strategist_data.py
    extractor/
      __init__.py
      extract_page.py
    analysis/
      __init__.py
      analyze_content_topics.py
      analyze_page_structure.py
      assemble_briefing_data.py
      compute_entity_prominence.py
      extract_claims.py
      merge_qualitative.py
      summarize_briefing.py
      score_draft_wdfidf.py
    data/                # Static data files
      location_codes.json
      stopwords.json
      idf_de.json
      blocklist_default.json
    cli/
      __init__.py
      main.py            # Typer CLI (Phase 6)
    api/
      __init__.py
      main.py            # FastAPI (Phase 7)
  tests/
    conftest.py
    golden/              # Golden output snapshots from Node.js (parity baseline)
    test_utils/
    test_serp/
    test_keywords/
    test_extractor/
    test_analysis/
```

## Dependencies (managed via `uv`)

```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "httpx",
    "readability-lxml",
    "beautifulsoup4",
    "lxml",
]

[project.optional-dependencies]
cli = ["typer[all]>=0.9"]
api = ["fastapi>=0.100", "uvicorn[standard]"]
dev = ["pytest>=8.0", "pytest-asyncio", "ruff"]

[project.scripts]
seo-pipeline = "seo_pipeline.cli.main:app"
```

**Environment management:**
- `uv init` / `uv sync` replaces `npm install`
- `uv run pytest` replaces `npm test`
- `uv run seo-pipeline <subcommand>` for CLI

## Execution Modes

Every pipeline stage supports all three:

1. **CLI subcommand:** `uv run seo-pipeline process-serp input.json --output out.json`
2. **Direct module:** `uv run python -m seo_pipeline.serp.process_serp input.json --output out.json`
3. **Python import:** `from seo_pipeline.serp.process_serp import process_serp`

## Migration Phases

### Phase 0: Scaffolding (~1 day)

- **Keep Node.js source intact** — it stays as reference and for side-by-side testing
- `uv init` — create `pyproject.toml` with project metadata and dependency groups
- `uv sync` — create venv and install deps
- Create `seo_pipeline/` package structure with empty `__init__.py` files alongside existing `src/`
- Configure `pytest` and `ruff` in `pyproject.toml`
- Reuse existing `test/fixtures/` (no copy needed, they're in the same repo)
- Generate golden output snapshots: run every Node.js script against its test fixtures, save output as `tests/golden/*.json` — these become the parity baseline
- Pipeline remains fully operational via Node.js throughout migration

### Phase 1: Pydantic Models (~2 days)

- Define all pipeline data contracts as Pydantic v2 models
- Derive field names and types from actual JSON fixtures (read before modeling)
- These models will be used everywhere: function signatures, CLI validation, API schemas
- Key: field declaration order must match JS JSON key order for byte-identical serialization

### Phase 2: Utils (~1 day)

- Port `slugify`, `tokenizer`, `load_api_config`, `resolve_location`, `preflight`
- Add `math.py` with `js_round()` (`math.floor(x + 0.5)`) to match JS `Math.round()` behavior
- Copy static data files (`stopwords.json`, `location_codes.json`, etc.) into `seo_pipeline/data/`
- Test against golden outputs

### Phase 3: SERP + Extractor (~3 days)

- `process_serp.py` — largest pure transform (~387 LOC), port all extraction functions
- `assemble_competitors.py` — pure JSON transform
- `extract_page.py` — **highest risk**: replace jsdom+Readability with beautifulsoup4+readability-lxml
  - Structured fields (headings, link_count, html_signals) must match exactly
  - `main_content_text` / `word_count` may differ slightly — accept +/-2% tolerance for this module only
- `fetch_serp.py` — HTTP client with async polling, port to `httpx.AsyncClient`
- Update SERP-related skill files to call Python versions

### Phase 4: Keywords (~2 days)

- Port in dependency order: extract → merge → process → filter → prepare_strategist → fetch
- Jaccard clustering in `process_keywords.py` is order-dependent — maintain identical sort (volume desc, stable)
- `js_round()` needed in opportunity scoring
- Update keyword-related skill files

### Phase 5: Analysis (~4 days)

- Most complex phase: TF-IDF, n-gram extraction, IDF boosting, section weight analysis
- `analyze_content_topics.py` (~455 LOC) is the hardest port — multiple rounding-sensitive formulas
- `assemble_briefing_data.py` (~353 LOC) — consolidation with optional file loads, year normalization
- All other analysis scripts are straightforward transforms
- Every `Math.round()` call site must use `js_round()` — at least 12 locations across the codebase

### Phase 6: Typer CLI (~2 days)

- One subcommand per pipeline stage (e.g., `seo-pipeline process-serp input.json --output out.json`)
- One `run-pipeline` command that chains all stages end-to-end
- Pydantic models handle input validation automatically
- Register as entry point: `seo-pipeline = "seo_pipeline.cli.main:app"`

### Phase 7: FastAPI API (~2 days)

- Each pipeline stage becomes a POST endpoint
- Pydantic models auto-generate OpenAPI schemas
- Background tasks for long-running operations (fetch-serp with polling)
- Foundation for future web UI

### Phase 8: Finalization (~1 day)

- Verify all 8 skill files call Python (should already be done per-phase)
- **Remove Node.js source** (`src/`, `package.json`, `package-lock.json`, `node_modules/`)
- Remove Node.js test files (`test/scripts/`) — Python tests are the new source of truth
- Keep `test/fixtures/` (shared) and `tests/golden/` (parity baseline, useful for regression)
- Update CI/CD workflows for Python (pytest, ruff)
- Update README, CLAUDE.md for the Python project
- Archive the original Node.js repo on GitHub (read-only)

## Key Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| HTML parser differences in `extract_page` | Medium | Accept +/-2% tolerance for content text; require exact match for structured fields |
| JS vs Python rounding (`Math.round` vs `round`) | High | Use `js_round()` everywhere — `math.floor(x + 0.5)` |
| String sort locale differences | Low | Both use Unicode code point order for Latin; verify with German umlaut fixtures |
| Regex behavior differences (`/g`, `\b`) | Low | JS `/g` → Python `re.finditer()`; test each pattern against fixtures |
| Feature freeze during migration | Medium | Pipeline stays operational via Node.js; skill files switch per-phase |

## Total Effort

~18 working days across all phases.

## Verification Strategy

After each phase:
1. Run Python tests: `uv run pytest`
2. Compare output against golden JSON snapshots from Node.js
3. Run one full pipeline against a real keyword to verify end-to-end (Node.js for unmigrated stages, Python for migrated ones)
4. After Phase 8 (full migration): run `uv run seo-pipeline run-pipeline` end-to-end and diff against a Node.js baseline run

## Determinism Notes

The pipeline's core invariant is **same input → byte-identical output**. Python-specific concerns:

- **Rounding:** JS `Math.round(0.5) = 1` vs Python `round(0.5) = 0` (banker's rounding). Use `js_round()` (`math.floor(x + 0.5)`) at all ~12 rounding sites.
- **Dict ordering:** Guaranteed insertion-ordered since Python 3.7. Pydantic models serialize fields in declaration order. Declare fields in the same order as JS JSON keys.
- **Float precision:** Both JS and Python use IEEE 754 doubles. Intermediate calculations should match. Validate with golden outputs.
- **String sorting:** Both use Unicode code point order by default. `sorted()` in Python is stable (like `Array.sort()` in V8).
