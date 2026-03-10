---
name: seo-content-pipeline
description: Run the full SEO content pipeline end-to-end from keyword research through competitor analysis, content strategy, content briefing, and optional article draft. Use when the user wants to run the complete pipeline for a topic.
---

# SEO Content Pipeline

Run the full SEO content pipeline end-to-end: keyword research → competitor analysis → content strategy → content briefing → article draft.

## Overview

This skill orchestrates all four pipeline steps in sequence. Each step builds on the output of the previous one. All intermediate data is saved to `output/YYYY-MM-DD_<seed-keyword-slug>/`.

## Inputs

Ask the user for:
1. **Seed keyword or topic** (required)
2. **Your domain** (optional — excluded from competitor analysis)
3. **Business context** — what do you sell/offer? who is your audience?
4. **Content goals** — traffic, leads, authority, conversions?
5. **Brand voice / tone** (optional — for the final brief) — scan `templates/` for files matching `*ToneOfVoice*` or `*tov*` (case-insensitive) and offer matches as options; let the user pick one, provide their own, or skip.

## Pipeline

Run each step sequentially, passing outputs forward:

### Step 1: Keyword Research

Follow the instructions in the `seo-keyword-research` skill:
- Use the seed keyword
- Retrieve and cluster keywords
- Save to `output/YYYY-MM-DD_<seed-keyword-slug>/keywords-<slug>.json`

Confirm results with the user before proceeding. They may want to adjust the keyword focus.

### Step 2: Competitor Analysis

Follow the instructions in the `competitor-analysis` skill:
- Use the primary keywords from Step 1
- SERP data is fetched via `src/serp/fetch-serp.mjs` (async task_post/task_get workflow -- cheaper than live/advanced)
- Analyze top-ranking pages
- Save to `output/YYYY-MM-DD_<seed-keyword-slug>/competitors-<slug>.json`

Show the competitive landscape and ask if the user wants to analyze additional competitors or adjust focus.

### Step 3: Content Strategy

Follow the instructions in the `content-strategy` skill:
- Read keyword and competitor data from Steps 1-2
- Rank opportunities and recommend content pieces
- Save to `output/YYYY-MM-DD_<seed-keyword-slug>/strategy-<slug>.json`

Present the prioritized content recommendations. Ask the user which piece(s) they want briefed.

### Step 4: Content Briefing

Follow the instructions in the `content-briefing` skill:
- Show available content templates from `templates/` and let the user pick one (or none)
- Generate a detailed brief for the selected content piece(s), structured according to the chosen template
- Save to `output/YYYY-MM-DD_<seed-keyword-slug>/brief-<slug>.md`

Present the final brief for review.

### Step 5: Content Draft (optional)

Ask the user if they want to generate a full article draft from the brief now.

If yes, follow the instructions in the `content-draft` skill:
- Use the brief from Step 4 as input
- Load keyword and competitor data for SEO and differentiation
- Write the complete article
- Save to `output/YYYY-MM-DD_<seed-keyword-slug>/draft-<slug>.md`

Present the finished draft for review.

## Output

At the end of the pipeline, the user has:
- `keywords-<slug>.json` — full keyword research with clusters
- `competitors-<slug>.json` — competitive landscape analysis
- `strategy-<slug>.json` — prioritized content strategy
- `brief-<slug>.md` — ready-to-write content brief
- `draft-<slug>.md` — publish-ready article draft (if requested)

All files in `output/YYYY-MM-DD_<seed-keyword-slug>/`.
