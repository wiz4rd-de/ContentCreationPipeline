# Data Flow into `/content-briefing`

---

## High-Level Flow

```
DataForSEO API (3 endpoints)
       ↓
   Raw JSON files (serp-raw.json, keywords-*-raw.json)
       ↓
   7 deterministic scripts (no LLM)
       ↓
   7 intermediate JSON files
       ↓
   assemble-briefing-data.mjs
       ↓
   briefing-data.json  ←── THIS is the single input to /content-briefing
       ↓
   /content-briefing skill (1 LLM call fills qualitative section)
       ↓
   brief-<slug>.md  +  updated briefing-data.json
```

---

## The 7 Intermediate Files & Scripts That Produce Them

### 1. `serp-processed.json` — from `src/serp/process-serp.mjs`

**Input:** `serp-raw.json` (DataForSEO SERP API response)

**Produces:**
- Top-10 organic competitors (rank, URL, domain, title, description, rating, AI overview citation flag)
- AI Overview extraction (cited domains/URLs/sources, full text)
- Featured Snippet detection
- People Also Ask questions + answers
- People Also Search queries
- Knowledge Graph data
- SERP feature presence flags (commercial signals, local signals, etc.)

### 2. `keywords-processed.json` — from `src/keywords/process-keywords.mjs`

**Input:** `keywords-related-raw.json` + `keywords-suggestions-raw.json` (DataForSEO Labs)

**Produces:**
- Deduplicated keyword list (case-insensitive merge)
- Intent classification per keyword (transactional/commercial/informational/navigational)
- N-gram clusters (Jaccard similarity ≥0.5, highest-volume keyword as representative)
- Opportunity score per keyword: `search_volume / (difficulty + 1)`
- Clusters ranked by total volume desc

### 3. `keywords-filtered.json` — from `src/keywords/filter-keywords.mjs`

**Input:** `keywords-processed.json` + `serp-processed.json` + `blocklist-default.json`

**Produces:**
- Filtered clusters (removes ethics violations, brands, foreign language, off-topic)
- Removal summary with counts per category
- **FAQ selection:** PAA questions scored by token overlap with kept keywords, assigned priority tiers (pflicht/empfohlen/optional)

### 4. `pages/<domain>.json` (per competitor) — from `src/extractor/extract-page.mjs`

**Input:** Live HTTP fetch of each competitor URL

**Produces per page:**
- Title, meta description, canonical, H1, all headings (H2-H4)
- Main content text (jsdom + Readability)
- Word count, sentence count
- HTML signals: tables, lists, FAQ sections, video embeds, forms, images
- Internal vs external link counts

### 5. `page-structure.json` — from `src/analysis/analyze-page-structure.mjs`

**Input:** All `pages/<domain>.json` files

**Produces:**
- Per-competitor section breakdown (heading, level, word count, sentence count, depth score)
- Module detection per page (FAQ, table, list, video, image_gallery, form)
- Cross-competitor aggregation: common modules (≥70%), rare modules (≤20%), avg word count

### 6. `content-topics.json` — from `src/analysis/analyze-content-topics.mjs`

**Input:** All `pages/<domain>.json` files + seed keyword

**Produces:**
- **Proof keywords:** Terms appearing in ≥2 competitor pages (top 50 by document frequency)
- **Entity candidates:** Single-word terms with DF ≥2, ≥3 chars (top 30)
- **Section weights:** Heading clusters with occurrence, avg word count, content percentage, weight tier
- **Content format signals:** Pages with numbered lists/FAQ/tables, avg H2 count

### 7. `entity-prominence.json` — from `src/analysis/compute-entity-prominence.mjs`

**Input:** Entity candidates + all `pages/<domain>.json` files

**Produces:**
- Prominence score per entity ("N/M" = appears in N of M pages)
- Word-boundary matching for short entities, substring for longer ones

### 8. `competitors-data.json` — from `src/serp/assemble-competitors.mjs`

**Input:** `serp-processed.json` + `pages/<domain>.json` files

**Produces:**
- Merged competitor profiles: SERP fields + extracted page data (word count, headings, links)
- Null qualitative placeholders (format, topics, strengths, weaknesses)

---

## Final Assembly: `assemble-briefing-data.mjs`

**Input:** All 7 intermediate files above (missing ones → null)

**Processing:**
1. Extracts metadata (date from directory name, current_year, pipeline version)
2. Resolves seed keyword from first available source
3. **Year normalization:** Replaces 2024/2025 with current_year in all strings
4. Builds cluster summary (rank, volume, opportunity — sorted by volume desc)
5. Merges entity prominence into entity candidates
6. Assembles FAQ data from filtered keywords
7. Computes SERP feature boolean summary
8. Creates `qualitative` section with 6 null placeholders for the LLM

---

## `briefing-data.json` — Final Structure

```
briefing-data.json
├── meta
│   ├── seed_keyword
│   ├── date
│   ├── current_year
│   └── pipeline_version
├── keyword_data
│   ├── clusters[] — {rank, cluster_keyword, total_search_volume, cluster_opportunity, keyword_count}
│   ├── total_keywords
│   ├── filtered_count
│   └── removal_summary — {ethics, brand, off_topic, foreign_language}
├── serp_data
│   ├── competitors[] — {rank, url, domain, title, description, word_count, headings, ...}
│   ├── serp_features — {ai_overview, featured_snippet, people_also_ask, ...} (booleans)
│   └── aio — {present, title, text, references[], references_count}
├── content_analysis
│   ├── proof_keywords[] — {term, document_frequency, total_pages, avg_tf}
│   ├── entity_candidates[] — {term, document_frequency, pages[], prominence}
│   ├── section_weights[] — {heading_cluster, sample_headings, occurrence, weight}
│   └── content_format_signals — {pages_with_faq, pages_with_tables, avg_h2_count, ...}
├── competitor_analysis
│   ├── page_structures[] — {url, domain, total_word_count, sections[], detected_modules[]}
│   ├── common_modules[]
│   ├── rare_modules[]
│   └── avg_word_count
├── faq_data
│   ├── questions[] — {question, priority, relevance_score}
│   └── paa_source: "serp"
└── qualitative (all null — filled by LLM in /content-briefing)
    ├── entity_clusters — LLM groups entities into 3-5 semantic categories
    ├── unique_angles — 3-5 content differentiation opportunities
    ├── content_format_recommendation — Ratgeber/Listicle/Hybrid + rationale
    ├── geo_audit — must-haves, hidden gems, hallucination risks, info gaps
    ├── aio_strategy — quotable snippet patterns for AI Overview optimization
    └── briefing — summary string
```

---

## What `/content-briefing` Does With This Data

1. **Reads** `briefing-data.json` (if missing, runs the full pipeline first)
2. **Optionally reads** a template file (`templates/template-*.md`) and tone-of-voice file (`templates/DT_ToneOfVoice.md`)
3. **Single LLM call** fills the 6 `qualitative` fields — everything else is copied verbatim
4. **Assembles** a 9-section markdown briefing where all quantitative data appears unchanged
5. **Saves** both the updated `briefing-data.json` and `brief-<slug>.md`

**Data integrity rule:** The LLM may not re-count, re-rank, or modify any numeric value. All quantitative data is authoritative from the deterministic pipeline. The LLM's role is strictly qualitative interpretation.
