# SEO Content Creation Pipeline — Project Roadmap

*From LLM Skills to Automated Content Platform*

Project Roadmap — March 2026

---

## The Problem

- Creating SEO-optimized content requires keyword research, competitor analysis, SERP evaluation, content briefing, and drafting
- Each step traditionally involves manual research, multiple tools, and heavy LLM guesswork
- Results are non-reproducible — running the same query twice yields different data
- No audit trail, no caching, no pipeline structure

---

## The Journey — Where We Started

**v0.0 — Orchestrated LLM Skills** (early March 2026)

- A handful of Claude Code skills calling SEO APIs and LLMs interactively
- Skills: `seo-keyword-research`, `competitor-analysis`, `content-briefing`, `content-draft`
- Every step required manual approval in the Claude Code CLI
- The LLM decided *what data to extract* and *how to interpret it*
- No tests, no caching, no reproducibility

---

## The Core Insight

**"Determinism is the primary goal."**

The LLM should guess, infer, and interpret as little as possible.

Data extraction must produce **byte-identical output** for the same input.
The LLM's role is constrained to **qualitative analysis only**, operating on a pre-built data skeleton with `null` placeholders.

This principle drove every architectural decision that followed.

---

## The Journey — Building the Pipeline

**v0.1 → v0.9** — 80+ issues closed across 6 phases

| Phase | Focus | Key Issues |
|-------|-------|-----------|
| **Keyword Pipeline** | Replace LLM inference with DataForSEO API calls, deterministic scoring | #3–#9 |
| **Briefing Pipeline** | SERP processing, page extraction, TF-IDF analysis, entity prominence, page structure analysis | #14–#23 |
| **SERP Infrastructure** | Async fetch with caching, TTL validation, keyword mismatch detection | #25–#42 |
| **Token Optimization** | Reduce LLM input by ~35KB — patch-write, stopword filtering, blocked page removal | #60–#69 |
| **Reliability** | Retry logic, pre-flight validation, progress logging, shared utilities, CI | #46–#56 |
| **Docs & Testing** | E2E integration tests, `--output` flag standardization, release process | #45, #54, #55, #57–#59 |

---

## Architecture Today

```
     DataForSEO API                        Target URLs
          │                                     │
    ┌─────┴─────┐                         ┌─────┴─────┐
    │ Keywords   │                         │   SERP    │
    │  Branch    │                         │  Branch   │
    ├────────────┤                         ├───────────┤
    │ fetch      │                         │ fetch     │
    │ process    │                         │ process   │
    │ filter     │                         │ extract   │
    └─────┬──────┘                         └─────┬─────┘
          │                                      │
          └──────────────┬───────────────────────┘
                         │
              ┌──────────┴──────────┐
              │ Page Structure      │
              │ Content Topics      │
              │ Entity Prominence   │
              │ Assemble Briefing   │
              └──────────┬──────────┘
                         │
                  briefing-data.json
                  (null placeholders)
                         │
              ┌──────────┴──────────┐
              │   LLM (qualitative  │
              │   analysis only)    │
              └──────────┬──────────┘
                         │
                 ┌───────┴───────┐
                 │   Briefing    │
                 │   Draft       │
                 └───────────────┘
```

**10 deterministic Node.js scripts** — zero LLM involvement in data extraction.
**LLM enters only at the end** — filling `null` qualitative fields + writing prose.

---

## What We Have Today (v0.2.0)

| Capability | Detail |
|------------|--------|
| **6 Claude Code Skills** | keyword-research, competitor-analysis, content-briefing, content-draft, content-strategy, seo-content-pipeline |
| **10+ Deterministic Scripts** | Keyword fetch/process/filter, SERP fetch/process, page extraction (jsdom+Readability), page structure, content topics (TF-IDF), entity prominence, briefing assembly |
| **German IDF Corpus** | Built from Leipzig Wikipedia 1M — powers WDF*IDF scoring and proof keyword filtering |
| **SERP Caching** | TTL-aware cache with `--force` override and keyword mismatch detection |
| **CI/CD** | GitHub Actions, Node.js built-in test runner, E2E integration test |
| **Output** | Per-run directories: `output/YYYY-MM-DD_<slug>/` with full audit trail |

---

## Near-Term — Unattended Pipeline Runner

**Goal:** `node src/run-pipeline.mjs "keyword" --market de`

One command. No interaction. Full pipeline.

| Feature | Why |
|---------|-----|
| **Single CLI entry point** | No more manual step-by-step approval |
| **Parallel branch execution** | SERP and keyword branches run concurrently — cuts wall time |
| **`--resume` checkpointing** | Skip completed steps after partial failure |
| **`--dry-run`** | Print execution plan without running |
| **Multi-provider LLM** | Anthropic, OpenAI, Google — native `fetch`, zero deps |
| **JSON validation** | Schema-check LLM output before merging into deterministic data |

Skills remain as **interactive dev/debug tools and documentation** — the runner becomes the production path.

---

## Mid-Term — Local Web UI

**Goal:** Make the pipeline accessible to non-technical content team members.

| Component | Tech |
|-----------|------|
| Server | `node:http` (zero dependencies) |
| Progress | Server-Sent Events (real-time step tracking) |
| Frontend | Static HTML + vanilla JS + Pico CSS |
| Markdown | `marked.js` from CDN for briefing/draft preview |

**Key Views:**
1. **New Run** — keyword, market, template, provider selection
2. **Live Progress** — step-by-step progress bar with SSE
3. **Run History** — browse past runs, view outputs
4. **Output Viewer** — rendered briefings and drafts
5. **Settings** — API key management (masked)

---

## Long-Term Vision — Content Platform

**From local tool to hosted multi-user platform.**

```
v1 (Local CLI)          v2 (Local Web UI)        v3 (Cloud Platform)
─────────────           ─────────────────        ───────────────────
node run-pipeline       localhost:3000           pipeline.example.com
api.env on disk         api.env on disk          Secret Manager
Single user             Single user              Multi-user + IAP auth
CLI output              Browser UI               Browser UI + API
No persistence          File-based history       Database-backed
```

**Platform capabilities (v3):**
- **Google Cloud Run** deployment — scales to zero, HTTPS out of the box
- **Google IAP / token auth** — team access control
- **Secret Manager** — secure API key storage
- **Persistent storage** — run history, analytics, content library
- **Team workflows** — assignment, review, approval stages
- **Scheduling** — automated content refresh and monitoring
- **Multi-language** — extend beyond German market

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Issues closed | **80+** |
| Deterministic scripts | **10+** |
| LLM calls per pipeline run | **2–3** (down from ~20+ in v0.0) |
| External dependencies | **2** (jsdom, linkedom) |
| Token savings from optimization | **~35KB per run** |
| Test coverage | Unit + integration + E2E |
| Time from first commit to v0.2 | **~2 weeks** |

---

## Guiding Principles

1. **Determinism first** — The LLM fills `null` placeholders, nothing more
2. **Zero-dep bias** — Node.js built-ins over npm packages wherever possible
3. **Scripts as standalone CLIs** — Every script is independently testable and composable
4. **Audit trail by default** — Every run produces a full output directory
5. **Evolve, don't rewrite** — Skills → CLI runner → Web UI → Cloud — each layer wraps the previous one
