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

Also load supporting pipeline data if available:
- `keywords-*.json` — for keyword placement and density guidance
- `competitors-*.json` — to ensure differentiation from competing content

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

**Quality:**
- Write in the target language natively — no translation artifacts
- Match the tone and brand voice specified in the brief
- Use short paragraphs (3-4 sentences max) for readability
- Vary sentence length and structure for a natural flow
- Include concrete examples, data points, or expert quotes where the brief suggests them
- Avoid filler phrases, generic statements, and unnecessary superlatives
- Write a compelling introduction that hooks the reader and addresses the search intent
- End with a clear conclusion and the CTA(s) from the brief

**Formatting:**
- Use markdown formatting: headers, bold, lists, blockquotes where appropriate
- Add `<!-- TODO: ... -->` comments for elements the writer must manually complete (e.g. internal links, proprietary data, images)
- Mark any facts or statistics that should be verified with `<!-- VERIFY: ... -->`

### 3. Self-review

Before saving, review the draft against the brief's SEO checklist:
- [ ] Primary keyword in title, H1, and first 100 words
- [ ] All secondary keywords used at least once
- [ ] All outline sections covered
- [ ] Word count within ±10% of target
- [ ] CTA(s) included
- [ ] Meta description present

If any item fails, fix it before proceeding.

### 4. Save output

Write the finished article to:
```
output/YYYY-MM-DD_<SEED_KEYWORD_SLUG>/draft-<KEYWORD_SLUG>.md
```

Print the full draft to the conversation so the user can review it immediately.

Provide a short summary at the end:
- Actual word count vs. target
- Primary keyword usage count
- Any `<!-- TODO -->` or `<!-- VERIFY -->` items that need attention
