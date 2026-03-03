---
name: content-briefing
description: Generate a detailed content brief that a writer (human or AI) can use to produce a complete article. Use when the user wants to create a writing brief or content outline.
---

# Content Briefing

Generate a detailed content brief that a writer (human or AI) can use to produce a complete article.

## Inputs

Ask the user for:
1. **Which content piece** to brief — pick from the strategy file, or specify a keyword/topic directly
2. **Content template** — scan the `templates/` directory for available `template-*.md` files and present them as options. Also offer "Kein Template (generisches Briefing)" as a fallback. Show each template with its name and the content type definition from its first lines.
3. **Target audience** (if not already defined in strategy)
4. **Brand voice / tone guidelines** (optional) — scan `templates/` for files matching `*ToneOfVoice*` or `*tov*` (case-insensitive). If found, list them and suggest the first match as default. The user can pick one, provide their own, or skip.
5. **Any specific requirements** — word count, CTA, internal links, etc.

## Steps

### 1. Load prior pipeline data

Read from the current run's `output/YYYY-MM-DD_<SEED_KEYWORD_SLUG>/` subfolder:
- `strategy-*.json` — to get the recommended piece details
- `keywords-*.json` — for keyword data
- `competitors-*.json` — for competitive context

If a strategy file exists and the user picks a piece from it, pre-fill most of the brief automatically.

### 2. Load the selected template (if any)

If the user selected a template, read the full template file from `templates/`. The template defines:
- The required sections and their order
- Character/word limits per section
- CMS-specific elements (Infoboxen, Image Walls, Teaserreihen, etc.)
- SEO/AIO checklists specific to this content type
- Formatting and style rules

The template structure **overrides** the generic briefing schema below. Every section, character limit, and structural requirement from the template must be reflected in the briefing.

### 3. Build the content brief

#### A) With template

Follow the template's structure section by section. For each template section, produce the briefing equivalent:
- Fill in all placeholder fields with data from the pipeline (keywords, competitors, strategy)
- Preserve all character/word limits from the template
- Include all CMS-specific elements (Keyvisual specs, Image Walls, Infoboxen, Experten-Tipps, etc.)
- Use the template's SEO/AIO checklist instead of the generic one
- Add competitive intelligence and content gap analysis where the template has content sections

The briefing must be specific enough that a writer can produce the final text without needing to consult the template themselves.

#### B) Without template (generic fallback)

Create a comprehensive brief as a markdown file with these sections:

---

**CONTENT BRIEF: [Working Title]**

**Meta:**
- Primary keyword: ...
- Secondary keywords: ...
- Search intent: ...
- Target word count: ...
- Content type: ...
- Funnel stage: ...

**Target Audience:**
- Who they are
- What they need
- Where they are in their journey

**Search Intent Analysis:**
- What the searcher is really looking for
- What questions they need answered
- What outcome they expect

**Suggested Title Options:**
1. ...
2. ...
3. ...

**Recommended Outline:**
- H1: ...
  - H2: ...
    - Key points to cover
    - H3s if needed
  - H2: ...
  - ...

**Key Points to Cover:**
- Must-include topics (table stakes from competitor analysis)
- Differentiating topics (content gaps to fill)
- Data/stats to reference

**Competitor Reference:**
- What top competitors do well (don't copy, beat)
- What they miss (your opportunity)

**Internal Linking Suggestions:**
- Link to: [page] with anchor text: [text]

**Call to Action:**
- Primary CTA
- Secondary CTA (if applicable)

**SEO Checklist:**
- [ ] Primary keyword in title, H1, first 100 words
- [ ] Secondary keywords distributed naturally
- [ ] Meta description (draft included below)
- [ ] Image alt text suggestions

**Draft Meta Description:**
> ~155 characters summarizing the page for SERP display

---

### 4. Save output

Write the brief to:
```
output/YYYY-MM-DD_<SEED_KEYWORD_SLUG>/brief-<KEYWORD_SLUG>.md
```

This is the final handoff document. Print it to the conversation as well so the user can review immediately.
