---
name: content-briefing
description: Generate a detailed content brief from pre-computed pipeline data. The deterministic pipeline produces briefing-data.json; this skill adds qualitative analysis in two LLM steps (one batched step for all 5 qualitative fields, one for final briefing assembly) and assembles the final briefing document.
---

# Content Briefing

Generate a detailed content brief from deterministic pipeline data (`briefing-data.json`) plus two LLM steps: one batched step for all 5 qualitative fields and one for final briefing assembly.

## Inputs

Ask the user for:
1. **Content template** -- scan the `templates/` directory for available `template-*.md` files and present them as options. Also offer "Kein Template (generisches Briefing)" as a fallback. Show each template with its name and the content type definition from its first lines.
2. **Brand voice / tone guidelines** (optional) -- scan `templates/` for files matching `*ToneOfVoice*` or `*tov*` (case-insensitive) and offer matches as options; let the user pick one, provide their own, or skip.
3. **Any specific requirements** -- word count, CTA, internal links, etc.
4. **Output directory** -- path to the `output/YYYY-MM-DD_<slug>/` directory containing `briefing-data.json`

## Pre-condition

Check that `briefing-data.json` exists in the specified output directory.

**If `briefing-data.json` does NOT exist:** STOP immediately and print:

> `briefing-data.json` not found in `<output-dir>`. Phase 1 (deterministic pipeline) has not been run yet. Please run the `seo-content-pipeline` skill first to generate the pipeline data, then re-invoke this skill.

Do not proceed further until the file exists.

## Phase 2: Qualitative Analysis (2 Steps)

---

**CRITICAL INSTRUCTION: All quantitative data in `briefing-data.json` is pre-computed by deterministic scripts and is authoritative. Do NOT re-count keywords, re-rank clusters, re-compute volumes, or modify any numeric values. Your role is strictly qualitative interpretation and strategic recommendation. Every number, ranking, and classification in the data skeleton must appear unchanged in the final output.**

---

### Step 2.1: Batched Qualitative Analysis (fields 2.1A–2.1E)

**Protocol:**

1. **Read** `output/YYYY-MM-DD_<slug>/briefing-data.json` once using the Read tool.
2. **Check** which of the 5 qualitative fields are still null. For each non-null field, print `"Step 2.1<X>: <field> already complete — skipping."` and skip that subsection.
3. **Perform** the analysis for all remaining null fields in your reasoning (not in a script).
4. **Write** the updated JSON back to disk once using the Write tool — update all computed fields in a single write. Do NOT create temp scripts in `/tmp/` or anywhere else. No Node scripts, no heredocs — just read JSON, update in your reasoning, write JSON.
5. **Print** one confirmation line per completed field: `"Step 2.1<X>: <field> complete."` followed by `"Step 2.1: all qualitative fields saved to briefing-data.json."`

#### 2.1A: Entity Categorization → `qualitative.entity_clusters`

Input: `content_analysis.entity_candidates` (list of terms with document_frequency, tf_idf_score, prominence)

Task: Group these entity candidates into 3-5 semantic categories (e.g., "Orte & Regionen", "Aktivitaeten & Erlebnisse", "Praktische Infos"). For each category, list the entities and generate a synonym list (useful for entity prominence correction in future runs).

Output format — set `qualitative.entity_clusters` to:
```json
[
  {
    "category": "Orte & Regionen",
    "entities": ["Palma", "Soller", "Valldemossa"],
    "synonyms": { "Palma": ["Palma de Mallorca", "Hauptstadt Mallorcas"] }
  }
]
```

#### 2.1B: GEO Audit → `qualitative.geo_audit`

Input: `meta.seed_keyword` + full `briefing-data.json` for context

Task: Based on your training data (not the pipeline data), assess:
- **Semantic must-haves:** Topics/entities the article MUST cover to be considered authoritative
- **Hidden gems:** Lesser-known aspects that could differentiate the content
- **Hallucination risks:** Facts that are commonly stated incorrectly about this topic
- **Information gaps:** Topics the competitor data does NOT cover but should

Output format — set `qualitative.geo_audit` to:
```json
{
  "must_haves": ["..."],
  "hidden_gems": ["..."],
  "hallucination_risks": ["..."],
  "information_gaps": ["..."]
}
```

#### 2.1C: Content Format Recommendation → `qualitative.content_format_recommendation`

Input: `content_analysis.content_format_signals` + `competitor_analysis.page_structures`

Task: Given the format signals (list counts, heading patterns, avg word count), recommend one of: Ratgeber, Listicle, or Hybrid. Provide a brief rationale.

Output format — set `qualitative.content_format_recommendation` to:
```json
{
  "format": "Hybrid",
  "rationale": "..."
}
```

#### 2.1D: Unique Angles → `qualitative.unique_angles`

Input: All data from `briefing-data.json` (especially `competitor_analysis`, `content_analysis`, `faq_data`)

Task: Identify 3-5 differentiation opportunities beyond what the deterministic data shows. What can this article offer that competitors do not?

Output format — set `qualitative.unique_angles` to:
```json
[
  { "angle": "...", "rationale": "..." }
]
```

#### 2.1E: AIO Optimization Strategy → `qualitative.aio_strategy`

Input: `serp_data.aio` + `faq_data` + `content_analysis.proof_keywords`

Task: Given the AIO data (presence, citations, text), recommend 3-5 quotable snippet patterns the article should include to maximize AI Overview citation probability. Each snippet should be a concise, factual statement that an AI could cite directly.

Output format — set `qualitative.aio_strategy` to:
```json
{
  "snippets": [
    { "topic": "...", "pattern": "...", "target_section": "..." }
  ]
}
```

### Step 2.2: Final Briefing Assembly → `qualitative.briefing`

**Pre-condition:** Before starting, verify that all 5 qualitative fields from Step 2.1 (`entity_clusters`, `geo_audit`, `content_format_recommendation`, `unique_angles`, `aio_strategy`) are non-null. If any are still null, STOP and report which fields are missing — run Step 2.1 first to populate them.

**Additional inputs:** Read the selected template from `templates/` (if any) and the tone-of-voice file (if selected). These files are only needed for this step.

Input: Entire `briefing-data.json` with all filled qualitative fields + the selected template

Task: Assemble the final content briefing as a structured markdown document. The briefing MUST follow this structure:

#### Briefing Output Structure

**1. Strategische Ausrichtung**
- Content format recommendation (from step 2.1C)
- Target audience and search intent
- Competitive positioning summary

**2. Keywords & Semantik**
- Primary keyword cluster (from `keyword_data.clusters[0]`)
- Top 5 keyword clusters with volumes (from deterministic data -- copy exactly, do NOT re-rank)
- Entity categories with synonyms (from step 2.1A)
- Proof keywords (from `content_analysis.proof_keywords` -- copy exactly)

**3. Seitenaufbau & Pflicht-Module**
- Common modules that ALL competitors use (from `competitor_analysis.common_modules` -- copy exactly)
- Rare modules used by few competitors (from `competitor_analysis.rare_modules` -- copy exactly)
- Average word count benchmark (from `competitor_analysis.avg_word_count`)
- Section weight distribution (from `content_analysis.section_weights` -- copy exactly)

**4. Differenzierungs-Chancen**
- Rare modules as opportunities (from deterministic data)
- Unique angles (from step 2.1D)
- Information gaps (from step 2.1B GEO audit)

**5. AI-Overview-Optimierung**
- Current AIO status (from `serp_data.aio` -- present/absent, cited domains)
- Quotable snippet recommendations (from step 2.1E)
- AIO-relevant FAQ questions (cross-reference with `faq_data`)

**6. FAQ-Sektion**
- FAQ questions in deterministic priority order (from `faq_data.questions` -- copy ranking exactly)
- For each question: the priority score and source (PAA/keyword-derived)
- Answer guidelines per question (qualitative: what the answer should cover)

**7. Content-Struktur**
- If a template was selected: map template sections to keyword clusters and section weights
- If no template: propose a section outline based on competitor section weights and keyword clusters

**8. Informationsluecken**
- GEO audit must-haves not covered by competitors (from step 2.1B)
- Hidden gems (from step 2.1B)
- Hallucination risks to avoid (from step 2.1B)

**9. Keyword-Referenz**
This section is FULLY DETERMINISTIC. Copy directly from `keyword_data.clusters`. For each cluster:
- Cluster keyword
- Rank (by total search volume)
- Total search volume
- Keyword count
- Opportunity score (if available)
- List all individual keywords with: keyword, search_volume, keyword_difficulty, search_intent

Do NOT summarize, re-rank, or omit any clusters. This is a reference table, not an interpretation.

After assembling the briefing markdown, set `qualitative.briefing` to a short summary string (NOT the full markdown). The full markdown is saved as a separate file in Phase 3.

## Phase 3: Save Final Briefing

Since `briefing-data.json` is already updated incrementally during Phase 2 steps, Phase 3 only needs to:

1. **Save `brief-<seed-keyword-slug>.md`** -- The complete briefing markdown document assembled in Step 2.2.
2. **Print** the final briefing to the conversation so the user can review immediately.

## Data Integrity Rules

These rules are non-negotiable:

1. **Keyword clusters** appear in the briefing exactly as they appear in `keyword_data.clusters`. Same order, same volumes, same opportunity scores.
2. **FAQ questions** appear in the briefing in the same priority order as `faq_data.questions`. The priority scores are pre-computed and authoritative.
3. **Common/rare module classification** is copied from `competitor_analysis.common_modules` and `competitor_analysis.rare_modules` without modification.
4. **Proof keywords** are copied from `content_analysis.proof_keywords` without modification.
5. **Section weights** are copied from `content_analysis.section_weights` without modification.
6. **AIO data** (presence, citations, text) is copied from `serp_data.aio` without modification.
7. If any deterministic field is `null` (data was unavailable), state "Daten nicht verfuegbar" rather than inventing values.
