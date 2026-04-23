# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- _items for the next release go here_

## [0.9.0] - 2026-04-23

The pipeline runs unattended on a Python-only `main`. Three version sources (`pyproject.toml`, `seo_pipeline/__init__.py`, `PIPELINE_VERSION`) reconciled at 0.9.0.

### Added
- Keywords-for-Keywords (KFK) as a third keyword source via DataForSEO `keywords_data/google_ads/keywords_for_keywords` async endpoint (#174–#177, epic #178). Adds ~222 POI-specific / activity keywords per run that the two Labs endpoints miss.
- Three-way keyword merge in `merge_keywords` with deduplication (#176).

### Changed
- `main` is now Python-only. Entire legacy Node.js tree deleted: `src/` (23 `.mjs` modules), `test/scripts/`, `package.json`, `package-lock.json`, `scripts/*.mjs`, `REWRITE_PLAN.md`, `ROADMAP.md` (epic #167, PR #183).
- README, CLAUDE.md, and RELEASING.md rewritten for Python/uv (#169, #170, #185).
- CI moved from `setup-node` + `npm test` to `setup-python@v5` + `setup-uv@v4` + `uv run pytest` (#181).
- Test fixtures migrated from `test/fixtures/` + `test/golden/` to `tests/fixtures/` + `tests/golden_fixtures/`; 22 Python test files updated (#171).

### Removed
- Entire Node.js pipeline implementation and its tooling (23 `.mjs` modules, `package.json`, `package-lock.json`, `src/extractor/`, shell + `.mjs` scripts).

### Known limitations
- No end-of-pipeline DOCX export yet (tracked in Hosted MVP #146 — `pandoc` md-to-docx helper).
- No Google Docs / SharePoint delivery yet (tracked in #161 for SharePoint, #162 optional for Google Docs).

## [0.8.0] - 2026-04-20

### Added
- Phase 12: Tone-of-Voice compliance audit skill (#112) — post-draft lint against brand guidelines.
- Phase 11: Fact-check batching optimization (#102) — batched web searches for claim verification.

### Fixed
- Fact-check throughput on long drafts (batching reduces per-claim latency).

## [0.7.0] - 2026-04-13

### Added
- Phase 10: Typed qualitative sub-models (#96) — structured Pydantic schemas for each qualitative field (insights, target audience, etc.) replace free-form text.
- Selective prompt serialization for deterministic cache keys (#101).
- Token-usage logging per LLM call (#93).
- Full LLM call logging for debugging (#99).

### Fixed
- LLM client reliability: retry/backoff hardening (#91).

## [0.6.0] - 2026-04-02

### Added
- Phase 6.5: Fact-check pipeline (#71) — web-search-backed claim verification over the drafted article.
- Phase 6.6: Verbose logging (#84) — structured progress output for every pipeline stage.

## [0.5.0] - 2026-04-01

### Added
- Phase 5b: LLM integration (#63) — LiteLLM abstraction, qualitative-field runner, draft runner. Opus / Sonnet / Haiku model selection per task.
- Phase 6: Typer CLI (#7) — unified `seo-pipeline <subcommand>` entrypoint replacing the old argparse-per-script pattern.

## [0.4.0] - 2026-03-31

### Added
- Phase 4: Keyword pipeline ported to Python (#5) — fetch, merge, process, expand, filter; all DataForSEO endpoints preserved.
- Phase 5: Analysis and scoring (#6) — WDF\*IDF, entity prominence, content-topic analysis, page-structure analysis, briefing-data assembly.

### Changed
- Pre-Phase 5 Pythonic cleanup (#51) — stdlib / pathlib adoption, `__all__` declarations, replaced hand-rolled `sys.argv` parsing with `argparse` across Phase 3 CLIs.

## [0.3.0] - 2026-03-30

The Python rewrite begins. Phases 1–3 land on the same day.

### Added
- Phase 1: Pydantic models (#2) — typed models for keywords, SERP entries, page extractions, briefing sections.
- Phase 2: Shared utilities (#3) — tokenizer, stopwords (German + English), math helpers (including the JS-faithful `js_round`), path / slug utilities.
- Phase 3: SERP and page extraction (#4) — async SERP fetch / process via DataForSEO `task_post` / `task_get`, `trafilatura`-based page extraction (parity fix later in #85).

### Changed
- Node.js pipeline moves into parallel maintenance-only mode; all new stages are built in Python.

## [0.2.0] - 2026-03-11

### Added
- SERP cache with keyword validation and `--force` bypass
- Auto-derived `--outdir` from keyword slug
- Static SERP fixture support
- Full deterministic briefing pipeline (9-step chain)
- Content briefing skill with Phase 1/Phase 2 architecture
- SEO content pipeline skill (end-to-end orchestration)
- Shared slugify utility for directory name generation
- Keyword retry logic with exponential backoff
- TTL validation to SERP cache
- Pre-flight validation script for pipeline runs
- Stderr progress output to silent pipeline scripts
- Briefing-data.json metadata with input params and timestamps
- Shared tokenizer module with unit tests
- IDF computation script (build-idf-table.mjs)
- Production idf-de.json from Leipzig Wikipedia 1M corpus
- WDF*IDF content draft scoring script
- Cleanup script for old output directories

### Fixed
- fetch-difficulty 404 endpoint fix
- merge-keywords response shape handling
- Test fixture mutation by copying to tmp directory
- Stopwords umlaut variants and missing entries
- Page structure filtering for blocked/error pages
- AIO text encoding artifacts in SERP processing

## [0.1.0] - 2026-03-05

### Added
- Initial keyword research pipeline (fetch, merge, process, expand)
- DataForSEO integration (related_keywords, keyword_suggestions)
- Keyword difficulty endpoint and opportunity score formula
- Page extractor with Readability + jsdom
- Location code resolver
- Entity prominence computation
- SERP enrichment with AIO text/citations and PAA answers
- Page structure analyzer with module detection and content depth
- TF-IDF content topic analyzer with section weight analysis
- Keyword filtering (ethics, brand, off-topic)
- Briefing data assembly from pipeline outputs
- Content briefing and SEO content pipeline skills
- Async SERP fetching with task_post/task_get workflow
- SERP cache checking
- Test scaffolding with Node.js built-in test runner
- Data flow documentation
