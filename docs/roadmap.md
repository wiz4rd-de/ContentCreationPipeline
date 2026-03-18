# DERTOUR Content Creation Pipeline — Project Roadmap

## Executive Summary

The DERTOUR Content Creation Pipeline is a systematic approach to SEO content production that replaces manual, inconsistent processes with a reproducible, auditable workflow. The core insight driving this project: by separating quantitative data extraction (deterministic scripts that produce byte-identical output) from qualitative analysis (a constrained LLM operating on pre-built data), we achieve content creation at scale without sacrificing accuracy or traceability. Built as a CLI-first tool by a power user, the long-term vision is a content management platform with a full pipeline workflow — Research, Strategy, Brief, Draft, QA, Publish — accessible to the broader content and SEO team through a Web UI.

## Where We Came From

### The Problem

Manual SEO content creation does not scale. Keyword research, competitor analysis, SERP evaluation, and briefing assembly are repetitive tasks that demand consistency — yet when done by hand, they produce varying results depending on who does them, when, and how thoroughly. The process is slow, error-prone, and impossible to audit after the fact.

### The Approach

Instead of throwing an LLM at the entire problem, the pipeline decomposes content creation into two distinct phases:

1. **Deterministic phase** — Scripts that fetch, process, filter, and structure data. Given the same input, they produce byte-identical output. No randomness, no interpretation, no LLM involvement.
2. **Qualitative phase** — The LLM operates on a pre-built data skeleton with null placeholders, filling in only the fields that require human-like judgment: tone analysis, content gap identification, strategic recommendations.

This separation means every quantitative claim in a brief can be traced back to source data, and every qualitative assessment is clearly marked as LLM-generated.

### What Was Built

**Phase 1–3: Deterministic Keyword Pipeline**
Eleven scripts forming a complete keyword research chain: fetch raw keyword data from the SEO API, extract and deduplicate, merge multi-source results, process into structured format, filter by relevance and volume, cluster by topic, and prepare data for strategic analysis. Covered by 355 tests — every script has unit tests, zero external dependencies beyond Node.js built-ins.

**Phase 4: Async SERP Workflow**
SERP fetching with local file caching, result processing (including AI Overview extraction), competitor page assembly, and full page extraction via headless browser (jsdom + Readability). The cache layer avoids redundant API calls across runs.

**Phase 5: Content Briefing Skill**
First LLM integration point. Qualitative analysis of competitor content (tone, structure, gaps) merged with deterministic data into a comprehensive content brief. Two-step LLM process: batched qualitative field generation, then final briefing assembly.

**Phase 6–7: Token Optimization**
Systematic reduction of prompt sizes — approximately 35 KB savings per pipeline run through smarter data assembly, deduplication, and compact formatting.

### Key Stats Today

| Metric | Count |
|--------|-------|
| Deterministic scripts | 13 |
| Pipeline skills | 6 |
| Agent | 1 (content quality inspector) |
| Content templates | 2 (Urlaubsseite, Reisemagazin) |
| Tests | 355 (all passing) |
| External dependencies | 0 (except page extractor) |

## Where We Are Now

### What Works End-to-End

A single seed keyword triggers the full pipeline:

```
Seed keyword
  → Keyword research (fetch → extract → merge → process → filter)
    → SERP analysis (fetch → process → assemble competitors)
      → Page extraction (headless fetch → content parsing)
        → Content analysis (structure, topics, entities)
          → Content briefing (deterministic data + LLM qualitative layer)
            → Content draft (briefing → publish-ready article)
```

### Architecture: Two-Phase Pipeline

```
┌─────────────────────────────────────────────────────────┐
│  DETERMINISTIC PHASE (scripts, byte-identical output)   │
│                                                         │
│  fetch-keywords → process-keywords → filter-keywords    │
│  fetch-serp → process-serp → assemble-competitors       │
│  extract-page → analyze-page-structure                  │
│  analyze-content-topics → compute-entity-prominence     │
│  assemble-briefing-data                                 │
└──────────────────────┬──────────────────────────────────┘
                       │ briefing-data.json
                       │ (structured data with null placeholders)
                       ▼
┌─────────────────────────────────────────────────────────┐
│  QUALITATIVE PHASE (LLM, constrained to analysis)       │
│                                                         │
│  Content briefing skill (qualitative fields only)       │
│  Content strategy skill                                 │
│  Content draft skill                                    │
└─────────────────────────────────────────────────────────┘
```

### Current Limitations

- **CLI-only** — requires a technical user comfortable with terminal and Claude Code
- **Single-market focus** — currently optimized for the German market (DE)
- **No content lifecycle tracking** — each pipeline run is independent; no history or status management
- **No IDF-based keyword scoring** — proof keyword quality relies on frequency heuristics, not statistical significance
- **Agent/skill sync drift** — the orchestrator agent partially duplicates skill logic inline (known issue, tracked)

### Current Version

v0.2.0 — functional end-to-end pipeline, targeting v0.9.0 then v1.0.0.

## Near-Term: Road to v1.0

### v0.9.0 — Must-Do (Blocking) — Milestone 2

These issues must be completed before we can consider a 1.0 release. The IDF chain introduces proper statistical keyword scoring, replacing the current frequency-based heuristics.

**IDF Tokenizer Chain (#31–#35)**

| # | Issue | Purpose |
|---|-------|---------|
| #31 | Extract shared tokenizer module | Reusable tokenization for German text |
| #32 | Unit tests for tokenizer module | Ensure correctness of tokenization |
| #33 | Build IDF computation script | Generate IDF values from reference corpus |
| #34 | Tests for IDF builder with fixture corpus | Validate IDF computation logic |
| #35 | Generate production idf-de.json from Leipzig corpus | Ship a real German-language IDF table |

**IDF Integration**

| # | Issue | Purpose |
|---|-------|---------|
| #29 | Static IDF corpus for proof keyword filtering | Replace heuristic noise filtering with statistical significance |
| #30 | WDF*IDF content draft scoring | Score draft content against IDF reference for keyword coverage |

**Documentation**

| # | Issue | Purpose |
|---|-------|---------|
| #43 | Update competitor-analysis skill docs | Reflect optional --outdir in fetch-serp.mjs |

### v1.0.0 — Should-Do (Release Quality) — Milestone 3

Not architecturally blocking, but a 1.0 without these would feel incomplete.

**Infrastructure Hardening**

| # | Issue | Purpose |
|---|-------|---------|
| #46 | Retry logic with exponential backoff | Resilient API calls in fetch-keywords.mjs |
| #47 | Pre-flight validation script | Catch missing config/credentials before pipeline runs |
| #50 | SERP cache TTL validation | Prevent stale cached data from being used silently |

**Developer Experience**

| # | Issue | Purpose |
|---|-------|---------|
| #49 | GitHub Actions CI workflow | Automated test runs on every push/PR |
| #51 | Shared config module for api.env | DRY config loading across scripts |
| #52 | Progress logging for pipeline scripts | Visibility into long-running operations |

**Operations**

| # | Issue | Purpose |
|---|-------|---------|
| #54 | Cleanup script for old output directories | Manage disk usage from accumulated runs |
| #55 | Release process documentation and automation | Repeatable, documented release workflow |
| #56 | Expanded briefing-data.json metadata | Input parameters and timestamps for traceability |

**Quality**

| # | Issue | Purpose |
|---|-------|---------|
| #45 | Integration test: full end-to-end happy path | Confidence that the entire pipeline works together |
| #48 | Troubleshooting section in README | Self-service answers for common setup issues |

## Mid-Term: v1.x — Team Enablement

After v1.0 stabilizes the core pipeline, the focus shifts to making it accessible beyond a single power user.

**Web UI / Dashboard**
A lightweight web interface to trigger pipeline runs, view run history, and browse results. This is the single most important step toward team adoption — it removes the CLI barrier entirely.

**Multi-Template Support**
Expand beyond the current two templates (Urlaubsseite, Reisemagazin) to cover more DERTOUR content types: destination guides, hotel descriptions, activity pages, and seasonal campaigns.

**Google Docs Integration**
Direct export of briefs and drafts to Google Docs for editorial workflows. The foundation exists (md-to-gdoc skill); this extends it into a seamless one-click flow.

**Content Calendar Integration**
Connect pipeline output to editorial planning tools — map briefs to publication dates, track production status, and identify content gaps in the calendar.

**Batch Processing**
Run the pipeline for multiple keywords in a single invocation. Essential for quarterly content planning where dozens of topics need research simultaneously.

**Quality Feedback Loop**
Track which briefs and drafts required the most manual editing post-generation. Feed this data back into prompt tuning to continuously improve output quality.

## Far-Term: v2.0+ — Content Management Platform

The full vision: a self-service content operations platform for the DERTOUR content and SEO team.

**Full Workflow Orchestration**
Research → Strategy → Brief → Draft → QA → Publish — each stage with status tracking, approval gates, and handoff notifications. Content moves through the pipeline with clear ownership at every step.

**Role-Based Access**
Content strategist, writer, editor, approver — each role sees their relevant pipeline stage and actions. A strategist configures keyword research; a writer receives briefs and submits drafts; an editor reviews and approves.

**Content Portfolio Management**
A centralized view of all content pieces across the DERTOUR portfolio. Monitor content freshness, identify pages due for refresh, and schedule update cycles based on performance data.

**Performance Tracking**
Post-publication metrics — rankings, organic traffic, conversions — tied back to the original brief. Understand which content strategies actually drive results and feed those learnings into future briefs.

**Multi-Market / Multi-Language**
Extend the pipeline beyond the German market to other DERTOUR markets. Localized keyword research, language-specific IDF corpora, and market-appropriate content templates.

**API Layer**
Expose the pipeline as a service for integration with other internal tools — CMS plugins, editorial dashboards, reporting systems. The pipeline becomes infrastructure rather than a standalone tool.

## Architecture Evolution

```
NOW (v0.x)                    v1.x                         v2.0+
─────────────────────────────────────────────────────────────────────

CLI scripts                   Web UI wrapper               Full platform
+ Claude Code skills          + existing scripts            + persistence layer
                              + run history                 + auth & roles
Single user, local            + result viewer               + workflow engine
                                                            + API
                              Team access,                  + performance data
                              visual results
                                                            Self-service,
                              Same deterministic core       multi-team,
                                                            multi-market
```

Each evolution layer wraps the previous one. The deterministic core scripts remain unchanged — new capabilities are added around them, never by replacing them.

## Principles That Will Not Change

**Determinism first.** Quantitative data extraction is always reproducible. Given the same input, scripts produce byte-identical output. No randomness, no ambient state, no LLM involvement in data processing.

**LLM constrained to qualitative analysis.** The LLM never touches raw data extraction, filtering, or scoring. It receives a structured data skeleton and fills in only the fields that require judgment — tone, gaps, recommendations.

**Comprehensive test coverage.** Every deterministic script has unit tests. Every new script ships with tests. The test suite runs in under 3 seconds with zero external dependencies.

**Audit trail for every decision.** Pipeline output is traceable. Quantitative claims link to source data. Qualitative assessments are clearly marked as LLM-generated. Nothing is a black box.
