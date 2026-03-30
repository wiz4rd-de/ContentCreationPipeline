# Golden Output Snapshots

This directory contains golden JSON output files from running every deterministic
Node.js pipeline script against its test fixtures. These files serve as the
ground truth for Python parity tests during the migration.

## Regeneration

To regenerate all golden files:

```bash
bash scripts/generate-golden.sh
```

The script is idempotent: re-running produces byte-identical output.

## Naming Convention

Each golden file follows the pattern `<script-name>--<fixture-name>.json`.
For multi-input scripts, `<fixture-name>` reflects the primary input or directory name.

## Included Scripts (10)

| Script | Fixture Directory |
|--------|------------------|
| `src/serp/process-serp.mjs` | `test/fixtures/process-serp/` |
| `src/serp/assemble-competitors.mjs` | `test/fixtures/assemble-briefing-data/` |
| `src/keywords/extract-keywords.mjs` | `test/fixtures/keyword-expansion/` |
| `src/keywords/process-keywords.mjs` | `test/fixtures/process-keywords/` |
| `src/keywords/filter-keywords.mjs` | `test/fixtures/filter-keywords/` |
| `src/keywords/prepare-strategist-data.mjs` | `test/fixtures/prepare-strategist-data/` |
| `src/analysis/analyze-content-topics.mjs` | `test/fixtures/analyze-content-topics/` |
| `src/analysis/analyze-page-structure.mjs` | `test/fixtures/analyze-page-structure/` |
| `src/analysis/compute-entity-prominence.mjs` | `test/fixtures/compute-entity-prominence/` |
| `src/analysis/assemble-briefing-data.mjs` | `test/fixtures/assemble-briefing-data/` |

## Excluded Scripts

| Script | Reason |
|--------|--------|
| `src/serp/fetch-serp.mjs` | Requires live DataForSEO API calls; cannot produce deterministic output offline. |
| `src/keywords/fetch-keywords.mjs` | Requires live DataForSEO API calls; cannot produce deterministic output offline. |
| `src/extractor/extract-page.mjs` | Requires live HTTP requests to crawl pages; cannot produce deterministic output offline. Existing page fixture JSONs serve as static snapshots instead. |
| `src/analysis/extract-claims.mjs` | No dedicated fixture directory exists for this script. |
| `src/analysis/score-draft-wdfidf.mjs` | Not part of the core 10-script deterministic pipeline scope for Phase 0 golden snapshots. |

## Non-Deterministic Field Handling

The `assemble-briefing-data` output contains two non-deterministic fields that are
frozen to fixed sentinel values during golden file generation:

- `meta.phase1_completed_at` is frozen to `"2026-01-01T00:00:00.000Z"`
- `meta.current_year` is frozen to `2026`

This is done by `scripts/freeze-briefing-fields.mjs` as a post-processing step.
