# Implementation Plan

_Generated: 2026-03-09_

## Previous Work (Completed)

The deterministic keyword pipeline (issues #3-#12) is complete and merged to `main`. 89 tests, 0 failures. See git history for details.

---

## Phase 1: Foundation -- Full Page Text Extraction

| Issue | Title | Parallel | Notes |
|-------|-------|----------|-------|
| #14   | 1/9: Extend extract-page.mjs to output full readable text and HTML signals | DONE (2026-03-09) | Commit 4821887. Adds `main_content_text`, `readability_title`; 93 tests pass. |

## Phase 2: Independent Data Preparation Scripts

| Issue | Title | Parallel | Notes |
|-------|-------|----------|-------|
| #15   | 2/9: Build deterministic prepare-strategist-data.mjs script | DONE (2026-03-09) | Commit 42f2084. Dedup with year normalization, foreign-language filter, PAA extraction, SERP snippets; 124 tests pass. |
| #16   | 3/9: Build deterministic compute-entity-prominence.mjs script | DONE (2026-03-09) | Commit 4b29f2d. Deterministic synonym matching with word-boundary for short synonyms, debug corrections for delta >= 2; 144 tests pass. |
| #17   | 4/9: Extend process-serp.mjs to extract detailed AIO text and PAA answers | DONE (2026-03-09) | Commit ca6e82b. Enriched AIO with title/text/citations; PAA as objects with answer/url/domain; backward compatible; 164 tests pass. |
| #19   | 5/9: Build deterministic analyze-page-structure.mjs for module detection and content depth | DONE (2026-03-09) | Commit aef7fe3. Detects 6 module types (FAQ, table, list, video, image_gallery, form), per-section depth scoring, cross-competitor frequency analysis; 191 tests pass. |

## Phase 3: Cross-Competitor Content Analysis

| Issue | Title | Parallel | Notes |
|-------|-------|----------|-------|
| #20   | 6/9: Build deterministic analyze-content-topics.mjs for TF-IDF entity extraction and section weight analysis | DONE (2026-03-09) | Commit 4934178. TF-IDF proxy with n-gram extraction, Jaccard heading clustering, section weight analysis, stopwords.json (456 DE + 196 EN); 214 tests pass. |
| #21   | 7/9: Build deterministic filter-keywords.mjs for ethics, brand, and off-topic filtering | DONE (2026-03-09) | Commit d2e52bb. Blocklist/brand/foreign-language filtering with audit trail tagging, FAQ prioritization with token overlap scoring; 247 tests pass. |

## Phase 4: Consolidation

| Issue | Title | Parallel | Notes |
|-------|-------|----------|-------|
| #22   | 8/9: Build deterministic assemble-briefing-data.mjs to consolidate all analysis outputs | DONE (2026-03-09) | Commit 5324a21. Auto-discovers 7 pipeline files, cluster ranking by volume, proof keywords/modules/sections consolidated, AIO/FAQ/entity assembly with prominence merge, year normalization, graceful null for missing inputs, qualitative section all null; 272 tests pass. |

## Phase 5: LLM Briefing Skill

| Issue | Title | Parallel | Notes |
|-------|-------|----------|-------|
| #23   | 9/9: Update content-briefing skill to consume briefing-data.json and minimize LLM inference | DONE (2026-03-09) | Skill reads briefing-data.json, single LLM call fills qualitative fields only, seo-content-pipeline updated |

---

## Dependency Graph

- #14 -> #16 (entity prominence needs full page text from extract-page.mjs)
- #14 -> #19 (page structure analysis needs `main_content_text` and `html_signals`)
- #14 + #19 -> #20 (content topic analysis needs page text and section-level structure)
- #17 -> #21 (keyword filtering uses enriched PAA data for FAQ prioritization)
- #14, #15, #16, #17, #19, #20, #21 -> #22 (consolidation reads all pipeline outputs)
- #22 -> #23 (briefing skill consumes consolidated `briefing-data.json`)

## Architecture Notes

All Phase 2-3 scripts follow the same pattern:
- CLI with `--flag` arguments, reads JSON files, writes JSON to stdout
- Deterministic: same inputs produce byte-identical output
- Tests with fixtures in `test/scripts/<name>.test.mjs`
- `qualitative` fields set to `null` -- LLM fills only in Phase 5 (#23)

Data flow:
```
extract-page.mjs (#14) ──────────┐
prepare-strategist-data.mjs (#15)┤
compute-entity-prominence (#16) ─┤
process-serp.mjs extended (#17) ─┤──> assemble-briefing-data.mjs (#22) ──> briefing-data.json
analyze-page-structure (#19) ────┤                                              |
analyze-content-topics (#20) ────┤                                              v
filter-keywords (#21) ───────────┘                                    content-briefing skill (#23)
                                                                      (single LLM call)
```
