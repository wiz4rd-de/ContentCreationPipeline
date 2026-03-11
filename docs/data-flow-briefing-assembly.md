# Data Flow: Briefing Assembly (`/content-briefing`)

How `briefing-data.json` + template + tone-of-voice become `brief-<slug>.md`.

For the upstream pipeline that produces `briefing-data.json`, see [data-flow-content-briefing.md](./data-flow-content-briefing.md).

---

## Three Inputs

```
briefing-data.json          template-urlaubsseite.md       DT_ToneOfVoice.md
(deterministic data          (page blueprint:               (brand voice:
 + 6 null qualitative         mandatory sections,            3 audience segments,
 fields)                      char limits, rules)            style rules, no-gos)
        \                         |                         /
         \                        |                        /
          --------- Single LLM Call ---------
                          |
               brief-<slug>.md  +  updated briefing-data.json
```

---

## Input 1: `briefing-data.json`

The deterministic skeleton. All quantitative fields are read-only for the LLM.

**Read-only sections used during assembly:**

| Field Path | Used In Briefing Section |
|---|---|
| `keyword_data.clusters` (all) | 2 (top 5 table), 7 (template mapping), 9 (full reference) |
| `keyword_data.clusters[0]` | A (Meta-Daten: HKW) |
| `serp_data.competitors` | A (Wettbewerber-URLs), 1 (competitive positioning) |
| `serp_data.aio` | 5 (AIO status table) |
| `serp_data.serp_features` | 5 (SERP features table) |
| `content_analysis.proof_keywords` | 2 (proof keywords table) |
| `content_analysis.entity_candidates` | Input for qualitative field 1 |
| `content_analysis.section_weights` | 3 (section weight table), 7 (template mapping) |
| `content_analysis.content_format_signals` | Input for qualitative field 3 |
| `competitor_analysis.common_modules` | 3 (common modules list) |
| `competitor_analysis.rare_modules` | 3 (rare modules list), 4 (differentiation) |
| `competitor_analysis.avg_word_count` | 3 (word count benchmark) |
| `competitor_analysis.page_structures` | Input for qualitative field 3 |
| `faq_data.questions` | 6 (FAQ table in priority order) |

**Qualitative fields (null on input, filled by LLM):**

| Field | Task | Used In Briefing Section |
|---|---|---|
| `entity_clusters` | Group entity candidates into 3-5 semantic categories + synonyms | 2 (entity categories), 7 (template mapping) |
| `geo_audit` | Must-haves, hidden gems, hallucination risks, info gaps | 4 (differentiation), 8 (info gaps) |
| `content_format_recommendation` | Ratgeber / Listicle / Hybrid + rationale | 1 (strategic direction) |
| `unique_angles` | 3-5 differentiation opportunities | 4 (differentiation) |
| `aio_strategy` | 3-5 snippetable quote patterns with target sections | 5 (AIO optimization) |
| `briefing` | Short summary string (NOT the full markdown) | Stored in JSON only |

---

## Input 2: `template-urlaubsseite.md`

Provides the **page structure blueprint**. The template defines mandatory sections, character limits, and formatting rules that constrain the briefing output.

**Mandatory sections defined by template:**

| Section | Key Constraints |
|---|---|
| A. Meta-Daten & Steuerung | Table with title, slug, HKW, char target, audiences, competitors |
| B. Meta-Title & Description | HKW at start, suffix `\| DERTOUR` auto-appended, ~140 chars for description |
| C. H1 + Subline + Keyvisual | Max 50 chars, keyword in H1 |
| D. Gute Gruende | 3 bullet points, max 120 chars each, referenced later in text |
| E. Intro | 300-500 chars, HKW early, ends with CTA |
| F.1 Schoenste Orte | Region teasers + image wall with links |
| F.2 Schoenste Straende | Optional, beach-specific |
| F.3 Beliebte Sehenswuerdigkeiten | Attractions |
| F.4 Optionales Thema | Relevance-based (e.g., culinary) |
| F.5 Zielgruppenabschnitte | Families 0-5, 6-12, young couples, older couples + max 2 custom |
| F.6 Klima | Climate, best time, infobox, optional table |
| G. FAQ | 3-7 questions, 150-250 char answers, snippet-ready |
| H. Outro | 3-4 sentences, summary, no repetition |
| I. SEO & AIO Checklist | Keyword placement, linking, images, AIO rules |

**Global constraints from template:**
- 11.000-15.000 characters total
- H2s max 50 chars, must contain keyword
- No AI-floskeln ("fuer jeden was dabei", "du wirst lieben")
- Timeless writing (no prices, year references normalized to current year)
- DERTOUR brand rules (all caps, no hyphens, "kostenfrei" not "kostenlos")

---

## Input 3: `DT_ToneOfVoice.md`

Defines **brand voice** across three audience segments. The LLM applies these rules throughout the briefing's qualitative text and answer guidelines.

**Audience segments:**

| Segment | Share | Age | Key Traits |
|---|---|---|---|
| Young adults | 20% | 20-35 | Instagram/TikTok, inspiration, authenticity |
| Older couples | 40% | 40+ | Quality, premium comfort, safety, wordplay |
| Families | 40% | 25-45 | Security, flexibility, school holidays, child activities |

**Style rules applied during assembly:**
- Dynamic, vivid, image-rich but premium (not flappy or flowery)
- Active voice preferred ("Die Reiseleiter versorgen dich" not "Du wirst versorgt")
- Reason every claim ("...weil...")
- Numbers 1-11 spelled out, 12+ as digits; distances/times always digits + unit spelled out
- No bracketed asides (use em dashes or split sentences)

**Hard no-gos checked in checklist (section I):**
- SEO floskeln ("hat fuer jeden was", "ausgezeichnete Wahl")
- Unbacked superlatives ("garantiert", "perfekt")
- Animal cruelty references (elephant rides, aquariums)
- Competitor mentions
- "Sterne" for hotels (use "Hotelkategorie" or "Rauten")

---

## Assembly: Section-by-Section Source Mapping

Each section of `brief-<slug>.md` draws from specific sources. **D** = deterministic (copied verbatim), **Q** = qualitative (LLM-generated), **T** = template-defined structure, **V** = tone-of-voice rules.

### A. Meta-Daten & Steuerung

| Field | Source |
|---|---|
| Arbeitstitel | **Q** — LLM derives from seed keyword |
| URL-Slug | **Q** — LLM proposes based on seed keyword |
| HKW + volumes | **D** — `keyword_data.clusters[0]` |
| Neben-Keywords | **D** — top keywords from cluster 1 by volume |
| Ziel-Zeichenanzahl | **T** — template defines 11.000-15.000 |
| Zielgruppen | **Q** — LLM maps keyword intents to audience segments from **V** |
| Wettbewerber-URLs | **D** — `serp_data.competitors` top 3 |
| Interne Links | **Q** — LLM recommends based on keyword clusters + template linking rules |

### B. Meta-Title & Description

- **T** — template defines format rules (HKW at start, char limits, suffix)
- **Q** — LLM generates concrete proposals following template constraints
- **V** — tone-of-voice informs word choice

### 1. Strategische Ausrichtung

- **Q** — `content_format_recommendation` (format + rationale)
- **D** — keyword cluster volumes for audience sizing
- **D** — `serp_data.competitors` for competitive positioning (current DERTOUR rank, competitor word counts)

### 2. Keywords & Semantik

- **D** — top 5 clusters table copied verbatim from `keyword_data.clusters`
- **Q** — entity categories from `entity_clusters` (grouped + synonyms)
- **D** — proof keywords table copied verbatim from `content_analysis.proof_keywords`

### 3. Seitenaufbau & Pflicht-Module

Entirely **D** — all values copied verbatim:
- `competitor_analysis.common_modules`
- `competitor_analysis.rare_modules`
- `competitor_analysis.avg_word_count`
- `content_analysis.section_weights`

### 4. Differenzierungs-Chancen

- **D** — rare modules from `competitor_analysis.rare_modules` (with **Q** explanation of opportunity)
- **Q** — `unique_angles` (3-5 opportunities)
- **Q** — `geo_audit.information_gaps`

### 5. AI-Overview-Optimierung

- **D** — AIO status table from `serp_data.aio` (copied verbatim)
- **D** — SERP features table from `serp_data.serp_features` (copied verbatim)
- **Q** — `aio_strategy.snippets` (5 quotable patterns with target sections)

### 6. FAQ-Sektion

- **D** — questions table from `faq_data.questions` in exact priority order (priority + relevance_score copied)
- **Q** — answer guidelines per question (what to cover, tone, cross-references)
- **V** — tone rules shape answer guideline language

### 7. Content-Struktur (Template Mapping)

This is where **all three inputs converge**:

```
Template sections (F.1-H)
    ↓ mapped to ↓
Keyword clusters (D) — which cluster serves which section
    +
Section weights (D) — relative depth per section
    +
Entity clusters (Q) — which entities belong where
    +
Proof keywords (D) — distributed across sections
```

The LLM produces an ASCII tree showing each template section annotated with:
- Relevant keyword cluster(s) + rank + volume
- Mapped entities
- Section weight (from deterministic data)
- Special notes (quotable snippets, image walls, internal links)

### 8. Informationsluecken

Entirely **Q** from `geo_audit`:
- `must_haves` — topics required for authority
- `hidden_gems` — underserved angles competitors miss
- `hallucination_risks` — common factual errors to avoid

### 9. Keyword-Referenz

Entirely **D** — full dump of all clusters and all keywords from `keyword_data.clusters`. Every cluster listed with rank, total volume, keyword count, opportunity. Every keyword listed with search volume, KD, intent. No summarization, no re-ranking, no omissions.

### I. SEO- & AIO-Checkliste

- **T** — keyword integration rules, image alt-text rules, character count target
- **V** — brand-specific checks (DERTOUR caps, "kostenfrei", no "Sterne", no animal cruelty)
- **Q** — AIO-specific items (snippet count, FAQ markup)
- **D** — references to specific URLs for cannibalization checks

---

## Output Files

### 1. `brief-<slug>.md`

The complete briefing markdown. Sections A, B, 1-9, I as described above. Typically 400-600 lines.

### 2. `briefing-data.json` (updated)

The 5 structured qualitative fields are written back into the `qualitative` object:

```json
{
  "qualitative": {
    "entity_clusters": [...],
    "geo_audit": { "must_haves": [...], "hidden_gems": [...], "hallucination_risks": [...], "information_gaps": [...] },
    "content_format_recommendation": { "format": "...", "rationale": "..." },
    "unique_angles": [...],
    "aio_strategy": { "snippets": [...] },
    "briefing": "Short summary string (not the full markdown)"
  }
}
```

The `briefing` field stores a **short summary string**, not the full markdown document. The full briefing lives only in the `.md` file.

---

## Data Integrity Rules

Non-negotiable constraints enforced during assembly:

1. **Keyword clusters** — same order, volumes, opportunity scores as `keyword_data.clusters`
2. **FAQ questions** — same priority order as `faq_data.questions`
3. **Common/rare modules** — copied from `competitor_analysis` without modification
4. **Proof keywords** — copied from `content_analysis.proof_keywords` without modification
5. **Section weights** — copied from `content_analysis.section_weights` without modification
6. **AIO data** — copied from `serp_data.aio` without modification
7. **Null fields** — if any deterministic field is null, state "Daten nicht verfuegbar" (never invent values)
