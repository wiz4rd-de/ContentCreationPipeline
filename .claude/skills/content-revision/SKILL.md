---
name: content-revision
description: Revise an existing content draft by incorporating structured SME input while preserving original content and briefing compliance.
---

# Content Revision

Revise an existing content draft by incorporating additional requirements from a structured input file, while preserving the original content and maintaining briefing compliance. Produces a marked revision draft, a clean revision draft, and a revision report.

## Inputs

Ask the user for:
1. **Which draft to revise** -- pick from available `draft-*.md` files in the output folder structure, or provide a path
2. **Which briefing to use** -- pick from available `brief-*.md` files in the same output folder, or provide a path
3. **Which input file to use** -- pick from available `*-input.md` files (check `docs/` and project root), or provide a path
4. **Special instructions** (optional) -- e.g. "focus on family content", "skip Azoren section", "add more detail to Geheimtipps"
5. **Tone of Voice** (optional) -- scan `templates/` for files matching `*ToV*` or `*tov*` and offer matches

## Steps

### 1. Load all source documents

Read the three source files:
- The draft (`draft-<slug>.md`)
- The briefing (`brief-<slug>.md`)
- The input file (`*-input.md`)

Extract the **slug** from the draft filename: `draft-<slug>.md` yields `<slug>`. This slug is used for all output filenames.

Determine the **output directory**: use the same directory that contains the draft file.

### 2. Inventory the draft

Parse the draft to build a structural map:
- **Meta table**: extract all field values (Haupt-Keyword, Neben-Keywords, Title Tag, Meta Description, URL-Slug, Suchintention, Ziel-Wortanzahl, Zielgruppe)
- **Section outline**: list every heading (H1, H2, H3) with its line range and approximate word count
- **Content inventory**: for each section, note the key topics, entities, facts, and tips already covered
- **Existing markers**: catalog all `> **[TODO]**`, `> **[VERIFY]**`, `> **[Bild]**`, `> **[CMS: ...]**` blockquote markers and their locations

This inventory is critical for preventing content loss (Step 7) and self-review (Step 8).

### 3. Analyze the input file and identify relevant content

Read the input file structure. Input files typically contain prioritized regions or topics, each with subsections. Do NOT hardcode assumptions about which subsections exist -- the input structure varies by subject. Parse whatever structure is present.

**Relevance filtering:** The input file may cover many regions/topics, but the draft may only address one or a subset. Determine relevance by:

1. Match the draft's Haupt-Keyword and topic against the input's priority regions/themes
2. Check for entity overlap: compare place names, activity names, and topic keywords between the draft and each input section
3. A region/theme is **directly relevant** if the draft has a dedicated section about it or if the draft's primary topic matches it
4. A region/theme is **tangentially relevant** if the draft mentions it briefly (e.g., as a comparison or cross-reference) -- these get lighter treatment
5. A region/theme is **not relevant** if it has no connection to the draft's topic at all

Produce a relevance assessment listing each input section with its classification and rationale. This assessment feeds into the revision report.

### 4. Plan the revision

For each piece of relevant input content, decide:

**Where does it belong?**
- Which existing section covers the same topic or subtopic?
- If no existing section fits, can the information be woven into an adjacent section organically?
- Only create a new subsection if the briefing structure permits it

**Is it already covered?**
- If the draft already covers this information adequately: mark as "already present" and skip
- If the draft covers it partially: plan an expansion
- If the draft does not cover it at all: plan an addition

**How to integrate it?**
- Additions: draft new sentences or paragraphs that fit the existing tone, style, and flow
- Expansions: extend existing paragraphs with additional detail from the input
- Never replace existing correct content -- only augment

**Revision rules (mandatory):**
- The briefing's SEO structure, keywords, and outline are authoritative -- do not deviate
- Do NOT change the draft fundamentally (no restructuring, no rewriting of passages that are not being revised)
- Always allowed to edit and expand content organically to place additionally required information
- Shortening is only acceptable if already-present information remains intact as much as possible
- Must NOT leave out any already-present information
- Preserve all existing blockquote markers (`> **[TODO]**`, `> **[VERIFY]**`, `> **[Bild]**`, `> **[CMS: ...]**`)
- Preserve the meta table header exactly as-is (unless the briefing explicitly requires a change)

**ToV-Guard for revisions (mandatory -- ToV takes precedence on conflicts):**
- No new or changed sentence may exceed 40 words (ToV Schicht 2.2)
- Apply the Adjektiv-Test to every new sentence: Can the adjective be removed without the statement losing its meaning? Yes -> remove it (ToV Schicht 2.1)
- No forbidden patterns A1-A7 in new text:
  - No filler phrases ("fuer jeden etwas zu bieten", "kommt auf seine Kosten")
  - No unqualified superlatives
  - No triad enumerations (Dreier-Aufzaehlungen)
  - No imperative cascades in consecutive sentences
  - No pseudo-personal promises
  - No vague quality claims
- Brand rules B1-B8 must be respected in new text:
  - DERTOUR always in capitals, no hyphen in brand combinations
  - Never "Sterne" for hotels -- use "Hotelkategorie", "Kategorie", or "Rauten"
  - "kostenfrei" instead of "kostenlos"/"gratis"/"inklusive"
  - No competitor or third-party names
  - No animal attractions in unnatural settings
  - No guarantees or performance promises

### 5. Write the marked revision draft

Write the revised draft with inline revision markers around every changed or added passage:

```
==REVISION== revised or added text here ==END REVISION==
```

**Marker placement rules:**
- Markers wrap the **revised text itself**, not the surrounding unchanged content
- For an **added sentence** within an existing paragraph: wrap just the new sentence(s)
- For an **added paragraph**: wrap the entire new paragraph
- For an **expanded sentence** (existing sentence modified to include new info): wrap the entire modified sentence
- For a **new subsection**: wrap from the new heading through the end of the new content
- Markers are inline -- they appear on the same line as the text they wrap, not on separate lines
- Do NOT place markers around text that was not changed

**Example -- added sentence in existing paragraph:**
```markdown
Alfama ist das älteste Viertel Lissabons. Die verwinkelten Gassen laden zum Erkunden ein. ==REVISION== Besonders sehenswert sind die kleinen Azulejo-Werkstätten in den Seitenstraßen, wo traditionelle Fliesenkunst noch von Hand gefertigt wird. ==END REVISION== Vom Miradouro de Santa Luzia bietet sich ein Panoramablick über die roten Dächer.
```

**Example -- expanded sentence:**
```markdown
==REVISION== Besonders lohnenswert ist ein Besuch am Dienstag oder Samstag, wenn die Feira da Ladra – Lissabons bekanntester Flohmarkt – auf dem Campo de Santa Clara stattfindet, wobei die Marktstände mit Antiquitäten und Vintage-Fado-Schallplatten besonders für Paare reizvoll sind. ==END REVISION==
```

The document structure must be:
1. Full revised draft content (meta table, separator, article -- with markers)
2. A `---` separator
3. A `## Revision Summary` section at the very end

The **Revision Summary** must contain:
- Date of revision
- Input file used
- Number of revisions made (additions, expansions)
- Brief bullet list of the most significant changes
- Note on any input that was NOT incorporated and why

Save as: `marked-revision-draft-<slug>.md` in the output directory.

### 6. Write the clean revision draft

Create an identical copy of the marked revision draft but remove all `==REVISION==` and `==END REVISION==` markers. The text between the markers remains -- only the markers themselves are stripped.

The `## Revision Summary` section at the end is preserved.

Save as: `revision-draft-<slug>.md` in the output directory.

### 7. Write the revision report

Write a structured report:

```markdown
# Revision Report: <slug>

## Meta
- **Draft:** <path to original draft>
- **Briefing:** <path to briefing>
- **Input file:** <path to input file>
- **Revision date:** <YYYY-MM-DD>

## Input Relevance Assessment

| Input Section | Relevance | Rationale |
|---------------|-----------|-----------|
| ... | directly relevant / tangentially relevant / not relevant | ... |

## Changes Made

### Additions
| # | Section | Description | Input Source |
|---|---------|-------------|-------------|
| 1 | ... | ... | ... |

### Expansions
| # | Section | Description | Input Source |
|---|---------|-------------|-------------|
| 1 | ... | ... | ... |

### Unchanged Sections
| Section | Reason |
|---------|--------|
| ... | No relevant input for this section |

## Input NOT Incorporated

| Input Item | Source Section | Reason |
|------------|---------------|--------|
| ... | ... | Off-topic / already covered / would dilute focus / ... |

## Statistics
- Original word count: X
- Revised word count: Y (delta: +Z)
- Total revisions: N (A additions, E expansions)
- Input items incorporated: M of T relevant items
- Input items skipped: S (with reasons above)

## Briefing Compliance
- [ ] H1/H2/H3 structure matches briefing
- [ ] Primary keyword placement intact (title, H1, first 100 words)
- [ ] Secondary keywords distributed
- [ ] Word count within target range
- [ ] All original content preserved
- [ ] All original blockquote markers preserved
```

Save as: `revision-report.md` in the output directory.

### 8. Self-review

Before finalizing, perform these verification checks:

**Content preservation:**
- Compare the content inventory from Step 2 against both revision drafts
- Verify every heading from the original draft is still present
- Verify no facts, tips, entities, or descriptive passages from the original were removed
- Verify all original blockquote markers are still present
- Verify the meta table is unchanged

**Briefing compliance:**
- Verify the H1/H2/H3 hierarchy still matches the briefing outline
- Verify the primary keyword still appears in the title, H1, and first 100 words
- Verify secondary keywords are still distributed naturally
- Verify the word count has not decreased below the original

**Input incorporation:**
- Verify every directly relevant input item is either incorporated or listed in "Input NOT Incorporated" with a reason
- Verify new content flows naturally with existing text (no jarring transitions, no raw list dumps)

**ToV-Compliance of revisions:**
- Check every `==REVISION==...==END REVISION==` block against the ToV-Guard rules above (sentence length <= 40 words, Adjektiv-Test, no A1-A7 patterns, brand rules B1-B8)
- If a violation is found: rewrite the offending sentence before finalizing the revision

**Draft consistency:**
- Verify `revision-draft-<slug>.md` is identical to `marked-revision-draft-<slug>.md` minus the `==REVISION==` / `==END REVISION==` markers

If any check fails, fix the issue in both drafts before saving.

### 9. Summary output

Print a concise summary to the conversation:
- Paths to all three output files
- Number of revisions (additions + expansions)
- Word count change (original vs. revised)
- Count of input items incorporated vs. skipped
- Any items that require manual attention (e.g., new `> **[VERIFY]**` markers added during revision)

Do NOT print the full drafts to the conversation -- the user can open the files directly.
