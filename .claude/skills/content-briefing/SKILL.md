---
name: content-briefing
description: Generate a detailed content brief from pre-computed pipeline data. The deterministic pipeline produces briefing-data.json; this skill adds qualitative analysis in six sequential LLM steps and assembles the final briefing document.
---

# Content Briefing

Generate a detailed content brief from deterministic pipeline data (`briefing-data.json`) plus six sequential LLM steps for qualitative interpretation.

## Inputs

Ask the user for:
1. **Seed keyword or topic** (required)
2. **Content template** -- scan the `templates/` directory for available `template-*.md` files and present them as options. Also offer "Kein Template (generisches Briefing)" as a fallback. Show each template with its name and the content type definition from its first lines.
3. **Your domain** (optional -- excluded from competitor analysis)
4. **Target audience** (if not already defined in strategy)
5. **Brand voice / tone guidelines** (optional) -- scan `templates/` for files matching `*ToneOfVoice*` or `*tov*` (case-insensitive) and offer matches as options; let the user pick one, provide their own, or skip.
6. **Any specific requirements** -- word count, CTA, internal links, etc.

## Phase 1: Deterministic Pipeline

Check if `briefing-data.json` already exists in the output directory (`output/YYYY-MM-DD_<seed-keyword-slug>/`).

### If `briefing-data.json` does NOT exist, run the pipeline:

Execute each script in order. All scripts are deterministic -- same inputs produce byte-identical output.

```bash
# 1. SERP processing
# Input: raw SERP JSON from DataForSEO. Output: stdout JSON, redirect to serp-processed.json.
node src/serp/process-serp.mjs output/YYYY-MM-DD_<slug>/serp-raw.json --top 10 > output/YYYY-MM-DD_<slug>/serp-processed.json

# 2. Extract each competitor page
# Read competitors from serp-processed.json, then for each URL:
# Input: positional URL arg. Output: stdout JSON, redirect to pages/<slug>.json.
node src/extractor/extract-page.mjs "<competitor-url>" > output/YYYY-MM-DD_<slug>/pages/<competitor-slug>.json

# 3. Process keywords (clustering, difficulty, opportunity scores)
# Input: raw DataForSEO response files. Output: stdout JSON, redirect to keywords-processed.json.
node src/keywords/process-keywords.mjs \
  --related output/YYYY-MM-DD_<slug>/keywords-related-raw.json \
  --suggestions output/YYYY-MM-DD_<slug>/keywords-suggestions-raw.json \
  --seed "<seed-keyword>" \
  [--volume output/YYYY-MM-DD_<slug>/keywords-volume-raw.json] \
  [--brands "brand1,brand2"] \
  > output/YYYY-MM-DD_<slug>/keywords-processed.json

# 4. Filter keywords (ethics, brand, off-topic filtering + FAQ prioritization)
node src/keywords/filter-keywords.mjs \
  --keywords output/YYYY-MM-DD_<slug>/keywords-processed.json \
  --serp output/YYYY-MM-DD_<slug>/serp-processed.json \
  --seed "<seed-keyword>" \
  [--blocklist blocklist.json] \
  [--brands "brand1,brand2"] \
  > output/YYYY-MM-DD_<slug>/keywords-filtered.json

# 5. Analyze page structure (module detection, content depth)
node src/analysis/analyze-page-structure.mjs --pages-dir output/YYYY-MM-DD_<slug>/pages/ > output/YYYY-MM-DD_<slug>/page-structure.json

# 6. Analyze content topics (TF-IDF entity extraction, section weights)
node src/analysis/analyze-content-topics.mjs --pages-dir output/YYYY-MM-DD_<slug>/pages/ --seed "<seed-keyword>" > output/YYYY-MM-DD_<slug>/content-topics.json

# 7. Assemble briefing data (consolidate all outputs)
node src/analysis/assemble-briefing-data.mjs --dir output/YYYY-MM-DD_<slug>/
```

### If `briefing-data.json` already exists, skip to Phase 2.

## Phase 2: Qualitative Analysis (6 Sequential Steps)

### Protocol for all steps

Each step follows the same protocol:

1. **Read** `output/YYYY-MM-DD_<slug>/briefing-data.json` from disk
2. **Check** if `qualitative.<field>` is already non-null → if so, print `"Step N: <field> already complete — skipping."` and move to the next step
3. **Perform** the analysis described for this step
4. **Write** the updated JSON back to disk (`JSON.stringify(data, null, 2)` + trailing newline)
5. **Print** one-line confirmation: `"Step N: <field> complete — saved to briefing-data.json."`

---

**CRITICAL INSTRUCTION: All quantitative data in `briefing-data.json` is pre-computed by deterministic scripts and is authoritative. Do NOT re-count keywords, re-rank clusters, re-compute volumes, or modify any numeric values. Your role is strictly qualitative interpretation and strategic recommendation. Every number, ranking, and classification in the data skeleton must appear unchanged in the final output.**

---

### Step 2.1: Entity Categorization → `qualitative.entity_clusters`

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

### Step 2.2: GEO Audit → `qualitative.geo_audit`

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

### Step 2.3: Content Format Recommendation → `qualitative.content_format_recommendation`

Input: `content_analysis.content_format_signals` + `competitor_analysis.page_structures`

Task: Given the format signals (list counts, heading patterns, avg word count), recommend one of: Ratgeber, Listicle, or Hybrid. Provide a brief rationale.

Output format — set `qualitative.content_format_recommendation` to:
```json
{
  "format": "Hybrid",
  "rationale": "..."
}
```

### Step 2.4: Unique Angles → `qualitative.unique_angles`

Input: All data from `briefing-data.json` (especially `competitor_analysis`, `content_analysis`, `faq_data`)

Task: Identify 3-5 differentiation opportunities beyond what the deterministic data shows. What can this article offer that competitors do not?

Output format — set `qualitative.unique_angles` to:
```json
[
  { "angle": "...", "rationale": "..." }
]
```

### Step 2.5: AIO Optimization Strategy → `qualitative.aio_strategy`

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

### Step 2.6: Final Briefing Assembly → `qualitative.briefing`

**Pre-condition:** Before starting, verify that all 5 prior qualitative fields (`entity_clusters`, `geo_audit`, `content_format_recommendation`, `unique_angles`, `aio_strategy`) are non-null. If any are still null, STOP and report which fields are missing — do not proceed.

**Additional inputs:** Read the selected template from `templates/` (if any) and the tone-of-voice file (if selected). These files are only needed for this step.

Input: Entire `briefing-data.json` with all filled qualitative fields + the selected template

Task: Assemble the final content briefing as a structured markdown document. The briefing MUST follow this structure:

#### Briefing Output Structure

**1. Strategische Ausrichtung**
- Content format recommendation (from step 2.3)
- Target audience and search intent
- Competitive positioning summary

**2. Keywords & Semantik**
- Primary keyword cluster (from `keyword_data.clusters[0]`)
- Top 5 keyword clusters with volumes (from deterministic data -- copy exactly, do NOT re-rank)
- Entity categories with synonyms (from step 2.1)
- Proof keywords (from `content_analysis.proof_keywords` -- copy exactly)

**3. Seitenaufbau & Pflicht-Module**
- Common modules that ALL competitors use (from `competitor_analysis.common_modules` -- copy exactly)
- Rare modules used by few competitors (from `competitor_analysis.rare_modules` -- copy exactly)
- Average word count benchmark (from `competitor_analysis.avg_word_count`)
- Section weight distribution (from `content_analysis.section_weights` -- copy exactly)

**4. Differenzierungs-Chancen**
- Rare modules as opportunities (from deterministic data)
- Unique angles (from step 2.4)
- Information gaps (from step 2.2 GEO audit)

**5. AI-Overview-Optimierung**
- Current AIO status (from `serp_data.aio` -- present/absent, cited domains)
- Quotable snippet recommendations (from step 2.5)
- AIO-relevant FAQ questions (cross-reference with `faq_data`)

**6. FAQ-Sektion**
- FAQ questions in deterministic priority order (from `faq_data.questions` -- copy ranking exactly)
- For each question: the priority score and source (PAA/keyword-derived)
- Answer guidelines per question (qualitative: what the answer should cover)

**7. Content-Struktur**
- If a template was selected: map template sections to keyword clusters and section weights
- If no template: propose a section outline based on competitor section weights and keyword clusters

**8. Informationsluecken**
- GEO audit must-haves not covered by competitors (from step 2.2)
- Hidden gems (from step 2.2)
- Hallucination risks to avoid (from step 2.2)

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

1. **Save `brief-<seed-keyword-slug>.md`** -- The complete briefing markdown document assembled in Step 2.6.
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
