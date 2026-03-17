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

## Phase 6: Skill Token Optimization

Branch: `feat/skill-token-optimization` — strict linear chain, all issues modify `.claude/skills/content-briefing/SKILL.md`.

| Issue | Title | Parallel | Notes |
|-------|-------|----------|-------|
| #60   | 1/4: Remove duplicated Phase 1 instructions from content-briefing skill | DONE (2026-03-17) | Commit 66fc919. Phase 1 section removed, pre-condition guard added, Inputs trimmed to Phase 2-only, frontmatter updated; 337 tests pass. |
| #61   | 2/4: Batch Phase 2 qualitative steps 2.1-2.5 into single read-compute-write | DONE (2026-03-17) | Commit 910c85c. Collapsed steps 2.1-2.5 into single batched Step 2.1 (subsections 2.1A-2.1E); single Read + Write cycle; Step 2.6 renumbered to 2.2; 337 tests pass. |
| #62   | 3/4: Replace repeated output path pattern with single placeholder definition | DONE (2026-03-17) | Commit fd5518d. `$OUT` defined once near top of both skill files; all subsequent uses replaced; full path appears only in definition line; 337 tests pass. |
| #63   | 4/4: Consolidate redundant data integrity rules in content-briefing skill | DONE (2026-03-17) | Commit 77d04ed. Removed standalone "Data Integrity Rules" section; CRITICAL INSTRUCTION block and inline "copy exactly" annotations intact; 337 tests pass. |

### Task Checklists

**#60 — Remove duplicated Phase 1 instructions** ✓ DONE (2026-03-17)
- [x] Delete the entire "Phase 1: Deterministic Pipeline" section (lines 20-67) from `content-briefing/SKILL.md`
- [x] Add a pre-condition guard before Phase 2: check for `briefing-data.json`; STOP with a message if missing
- [x] Update frontmatter `description` to reflect Phase 2-only scope
- [x] Update the Inputs section: remove seed keyword and domain; keep template, tone-of-voice, requirements, output directory
- [x] Verify `seo-content-pipeline/SKILL.md` is unchanged
- [x] `npm test` passes

**#61 — Batch Phase 2 qualitative steps 2.1-2.5** DONE (2026-03-17)
- [x] Replace the "Protocol for all steps" section and steps 2.1-2.5 with a single batched step
- [x] New step: read `briefing-data.json` once, check which qualitative fields are null, compute all remaining fields in reasoning, write back once
- [x] Preserve all 5 field task descriptions and output format specs under labeled subsections
- [x] Preserve the critical instruction block about not modifying deterministic data
- [x] Keep Step 2.6 (briefing assembly) as a separate step (renumber to 2.2 or 2B)
- [x] Preserve per-field skip-if-non-null guard (applied within the single read)
- [x] `npm test` passes

**#62 — Replace repeated output path pattern with `$OUT`** DONE (2026-03-17)
- [x] Add `$OUT` definition near the top of `seo-content-pipeline/SKILL.md` (convert existing line 32 definition)
- [x] Add `$OUT` definition near the top of `content-briefing/SKILL.md`
- [x] Replace all subsequent occurrences of `output/YYYY-MM-DD_<slug>/` and variants with `$OUT` in both files
- [x] Full path pattern appears only in the definition line in each file
- [x] Bash code blocks remain syntactically valid with `$OUT`
- [x] `npm test` passes

**#63 — Consolidate redundant data integrity rules** DONE (2026-03-17)
- [x] Remove the standalone "Data Integrity Rules" section from `content-briefing/SKILL.md`
- [x] Verify the horizontal-rule-delimited critical instruction block is still present
- [x] Verify "copy exactly" / "do NOT re-rank" inline annotations in Step 2.6 are still present
- [x] No new duplicate text introduced
- [x] `npm test` passes

---

## Dependency Graph

- #14 -> #16 (entity prominence needs full page text from extract-page.mjs)
- #14 -> #19 (page structure analysis needs `main_content_text` and `html_signals`)
- #14 + #19 -> #20 (content topic analysis needs page text and section-level structure)
- #17 -> #21 (keyword filtering uses enriched PAA data for FAQ prioritization)
- #14, #15, #16, #17, #19, #20, #21 -> #22 (consolidation reads all pipeline outputs)
- #22 -> #23 (briefing skill consumes consolidated `briefing-data.json`)
- #23 -> #60 (Phase 1 removal builds on the skill structure established in #23)
- #60 -> #61 (batching restructures the section that Phase 1 removal exposes)
- #61 -> #62 (path placeholder replacement works on the post-batch file structure)
- #62 -> #63 (integrity-rule consolidation avoids merge conflicts after #62 edits both files)

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
