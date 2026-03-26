---
name: migrate-comments
description: Convert HTML comments in legacy draft files to blockquote markers. Use on drafts created before the blockquote-marker convention was adopted.
---

# Migrate Comments

Convert HTML comments (`<!-- ... -->`) in a draft file to the `> **[...]**` blockquote marker format, in-place.

## Inputs

Ask the user for:
1. **Which draft file to migrate** -- use Glob to find `output/**/draft-*.md` files and present the list. Let the user pick one or provide a path directly.

## Steps

### 1. Read the draft

Read the selected file using the Read tool. Store the original content for comparison.

### 2. Check for existing blockquote markers

Count how many `> **[...]**` blockquote markers already exist in the file. If the file contains blockquote markers but no HTML comments (`<!-- ... -->`), inform the user that the file is already migrated and stop. This ensures idempotency.

### 3. Apply conversion rules

Process the file content line by line. For each line, apply the following regex-based replacements. All matching is case-sensitive unless noted.

Initialize a change counter (total conversions) and a type tally (e.g., `{ TODO: 3, VERIFY: 2, "CMS: Suchmaske": 1 }`).

#### 3a. Standalone comment lines

A standalone comment is a line where the ENTIRE trimmed content is an HTML comment (possibly with leading whitespace only). Apply these rules in order:

| HTML comment pattern | Blockquote marker |
|---|---|
| `<!-- Suchmaske: X -->` | `> **[CMS: Suchmaske]** X` |
| `<!-- Hotelkarussell: X -->` | `> **[CMS: Hotelkarussell]** X` |
| `<!-- Magazin-Teaser-Karussell: X -->` | `> **[CMS: Magazin-Teaser-Karussell]** X` |
| `<!-- Slider "Y": X -->` | `> **[CMS: Slider "Y"]** X` |
| `<!-- Bild: X -->` | `> **[Bild]** X` |
| `<!-- Bildunterschrift: X -->` | `> **[Bildunterschrift]** X` |
| `<!-- TODO: X -->` | `> **[TODO]** X` |
| `<!-- VERIFY: X -->` | `> **[VERIFY]** X` |
| `<!-- KI-ergaenzt -->` or `<!-- KI-ergänzt -->` | `> **[KI-ergaenzt]**` |

Where `X` is the captured content (trimmed) and `Y` is the quoted slider name.

**Regex details for each pattern:**

- **CMS elements** (Suchmaske, Hotelkarussell, Magazin-Teaser-Karussell):
  Pattern: `^\s*<!--\s*(Suchmaske|Hotelkarussell|Magazin-Teaser-Karussell):\s*(.+?)\s*-->\s*$`
  Replacement: `> **[CMS: $1]** $2`

- **Slider** (has a quoted name):
  Pattern: `^\s*<!--\s*Slider\s+"([^"]+)":\s*(.+?)\s*-->\s*$`
  Replacement: `> **[CMS: Slider "$1"]** $2`

- **Bild / Bildunterschrift**:
  Pattern: `^\s*<!--\s*(Bild|Bildunterschrift):\s*(.+?)\s*-->\s*$`
  Replacement: `> **[$1]** $2`

- **TODO / VERIFY**:
  Pattern: `^\s*<!--\s*(TODO|VERIFY):\s*(.+?)\s*-->\s*$`
  Replacement: `> **[$1]** $2`

- **KI-ergaenzt** (no payload):
  Pattern: `^\s*<!--\s*KI-erga(?:e|ä)nzt\s*-->\s*$`
  Replacement: `> **[KI-ergaenzt]**`

- **Unknown standalone** (catch-all for any remaining standalone comments):
  Pattern: `^\s*<!--\s*(.+?)\s*-->\s*$`
  Replacement: `> **[$1]**`
  Log these with type "unknown" in the tally so the user can review them.

Increment the change counter and tally for each conversion.

#### 3b. Inline comments

An inline comment is an HTML comment appended to a line that also contains non-comment text before it. For example:

```
Some paragraph text. <!-- VERIFY: check this fact -->
```

For inline comments:

1. Extract the text before the comment (trimmed of trailing whitespace).
2. Convert the comment portion using the same rules as standalone comments (step 3a).
3. Output the result as two lines separated by a blank line:

```
Some paragraph text.

> **[VERIFY]** check this fact
```

Pattern to detect inline comments: a line where `<!--` appears but the line does NOT start with optional whitespace followed by `<!--`.

Regex: `^(.+?)\s*<!--\s*(.+?)\s*-->(.*)$` where capture group 1 is non-empty after trimming.

Apply the same keyword detection on the comment body (group 2) to determine the marker type.

### 4. Write the updated file

Compare the processed content with the original. If no changes were made, inform the user that no HTML comments were found (file is already clean or already migrated).

If changes were made, write the updated content back to the same file path using the Write tool.

### 5. Show summary

Print a concise summary to the conversation:

- File path that was processed
- Total number of conversions made
- Breakdown by type (e.g., `TODO: 5, VERIFY: 3, CMS: Suchmaske: 1, unknown: 2`)
- If any "unknown" types were found, list them explicitly so the user can review
- Remind the user to review the file for correctness

Example output:

```
Migrated: output/2026-03-12_wandern-norwegen/draft-wandern-norwegen.md

Conversions: 11
  TODO:   8
  VERIFY: 3

No unknown comment types found. File is ready for review.
```

## Idempotency

This skill is idempotent. The blockquote marker format (`> **[...]**`) is never valid HTML comment syntax, so the conversion rules will not match already-converted lines. Running the skill a second time on the same file will produce zero changes.

## Constraints

- Do NOT modify any content outside of HTML comments. The surrounding text must remain byte-identical.
- Do NOT reformat, rewrap, or restructure the markdown in any way.
- Do NOT add or remove blank lines except where inline comment splitting requires inserting one blank line.
- Preserve the original line endings of the file.
