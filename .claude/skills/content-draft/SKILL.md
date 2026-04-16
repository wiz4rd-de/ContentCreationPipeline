---
name: content-draft
description: Turn a content briefing into a publish-ready article draft. Use when the user wants to write the actual article text based on an existing content brief.
---

# Content Draft

Transform a content briefing into a complete, publish-ready article draft.

## Inputs

Ask the user for:
1. **Which brief to use** — pick from available `brief-*.md` files in the current output folder, or provide a path
2. **Tone / voice adjustments** (optional — override what the brief specifies) — scan `templates/` for files matching `*ToneOfVoice*` or `*tov*` (case-insensitive) and offer matches as options; let the user pick one, provide their own, or skip.
3. **Special instructions** — e.g. "use du instead of Sie", "include personal anecdotes", "keep paragraphs short"
4. **Target language** — default to the language used in the brief

## Steps

### 1. Load the content brief

Read the selected brief from the `output/YYYY-MM-DD_<SEED_KEYWORD_SLUG>/` subfolder.


### 2. Write the article draft

Produce a complete article in markdown following these guidelines:

**Structure:**
- Follow the outline from the brief exactly (H1, H2, H3 hierarchy)
- Include all sections and key points specified in the brief
- Respect the target word count from the brief

**SEO:**
- Place the primary keyword in the title, H1, first 100 words, and naturally throughout the text
- Distribute secondary keywords organically — never force them
- Write the meta description from the brief or improve it
- Suggest image alt texts where images are recommended

**Tone of Voice (PRIORITY):**
If a ToV file is loaded (Step 1.2), it is the authoritative style guide. When any other instruction contradicts the ToV, the ToV wins. Pay special attention to Constraint-Gruppe A (A1-A7: critical frequency patterns), Constraint-Gruppe B (B1-B8: brand and legal rules), and Constraint-Gruppe C (formatting rules).

**Quality:**
- Follow the Tone of Voice guidelines provided — they override any generic quality rules
- Write in the target language natively — no translation artifacts
- Include concrete examples, data points, or expert quotes where the brief suggests them

**Formatting:**
- Use markdown formatting: headers, bold, lists, blockquotes where appropriate
- Add `> **[TODO]** ...` blockquote markers for elements the writer must manually complete (e.g. internal links, proprietary data, images)
- Mark any facts or statistics that should be verified with `> **[VERIFY]** ...` blockquote markers

**Output format:**

The draft document must follow this structure exactly:

```markdown
# Draft: <Haupt-Keyword>

| Feld | Wert |
|------|------|
| **Haupt-Keyword** | primary keyword (search volume) |
| **Neben-Keywords** | secondary keywords, comma-separated (with SV each) |
| **Title Tag** | composed title tag |
| **Meta Description** | composed meta description (max 155 chars) |
| **URL-Slug** | from briefing section A |
| **Suchintention** | from briefing section A |
| **Ziel-Wortanzahl** | from briefing section A |
| **Zielgruppe** | from briefing section A |

---

# <H1 — actual article headline>

<article content follows>
```

Rules:
- The document title `# Draft: <Haupt-Keyword>` is the first line — no YAML frontmatter
- The meta table sits between the document title and the article's H1
- A `---` separator divides the meta block from the article content
- All field values are pulled from the briefing's "A. Meta-Daten & Steuerung" section, except **Title Tag** and **Meta Description** which are composed during drafting
- Do NOT put Title Tag or Meta Description into blockquote markers — the meta table replaces that pattern

### 3. Self-review

Before saving, review the draft against the brief's SEO checklist:
- [ ] Primary keyword in title, H1, and first 100 words
- [ ] All secondary keywords used at least once
- [ ] All outline sections covered
- [ ] Word count within ±10% of target
- [ ] CTA(s) included
- [ ] Meta info table present below document title with all required fields
- [ ] Title Tag and Meta Description in table match SEO guidelines
- [ ] No unverified facts stated as definitive (mark uncertain claims with `> **[VERIFY]** ...`)

If any item fails, fix it before proceeding.

### 4. Save output

Write the finished article to:
```
output/YYYY-MM-DD_<SEED_KEYWORD_SLUG>/draft-<KEYWORD_SLUG>.md
```

Inform the user of the saved file path. Do NOT print the full draft to the conversation — the user can open the file directly.

Provide a short summary at the end:
- Actual word count vs. target
- Primary keyword usage count
- Any `> **[TODO]**` or `> **[VERIFY]**` items that need attention

**Recommended next step:** Run `/fact-check` to verify factual claims in the draft before publication. The fact-check catches both LLM hallucinations and errors propagated from the briefing.
