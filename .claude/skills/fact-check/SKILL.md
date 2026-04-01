---
name: fact-check
description: Verify factual claims in a content draft against web sources. Use after the draft is written to catch hallucinations and briefing errors before publication.
---

# Fact-Check

Verify factual claims in a completed content draft by combining deterministic extraction with LLM-guided web search verification. Produces structured reports (JSON + Markdown) and optionally a corrected draft.

## Inputs

Ask the user for:
1. **Which draft to check** -- pick from available `draft-*.md` files in the current output folder, or provide a path
2. **Claim categories to check** (optional, default: all) -- allow limiting to specific categories (e.g., only prices_costs, only geographic)
3. **Output directory** -- path to the `$OUT` directory (auto-detect from draft path if possible)

## Steps

### 1. Deterministic claim extraction

Run the extractor:

```bash
uv run seo-pipeline extract-claims --draft $OUT/draft-<slug>.md --output $OUT/claims-extracted.json
```

Read `$OUT/claims-extracted.json` using the Read tool to get the initial claim list. This file contains:
- `meta.total_claims` -- number of claims found
- `claims[]` -- array of objects with `id`, `category`, `value`, `sentence`, `line`, `section`

The 6 deterministic categories are: `heights_distances`, `prices_costs`, `dates_years`, `counts`, `geographic`, `measurements`.

### 2. LLM claim supplementation

Read the draft markdown. Compare against the extracted claims from Step 1. Identify additional verifiable claims that the regex patterns missed:

- Named facts (e.g., "Galdhopiggen is the highest mountain in Scandinavia")
- Comparative claims (e.g., "Europe's largest plateau")
- Superlatives (e.g., "Norway's oldest national park")
- Legal/regulatory claims (e.g., "Jedermannsrecht allows camping anywhere")
- Specific named relationships (e.g., "Besseggen ridge between Gjende lake and Bessvatnet")

For each supplemented claim, assign the next sequential ID (continuing from the last deterministic ID, e.g., if the extractor produced c001–c018, start at c019) and a category. Add them to the claims list.

If the user specified claim categories to check, filter the combined list to only include those categories before proceeding.

### 3. Verify each claim via web search

**Claim cap:** Verify at most 40 claims. If there are more than 40, prioritize by category in this order (most error-prone first): `prices_costs`, `heights_distances`, `dates_years`, `counts`, `measurements`, `geographic`, then any LLM-supplemented claims. Within each category, preserve the original ordering.

For each claim in the (possibly filtered and capped) list:

1. Formulate a concise, targeted search query (e.g., "Galdhopiggen height meters" or "DNT membership price NOK 2025")
2. Use `WebSearch` to search the web
3. Analyze the top 3-5 results to determine a verdict:
   - **correct** -- at least 2 independent sources confirm the claim
   - **incorrect** -- at least 2 independent sources contradict the claim; record the correct value
   - **uncertain** -- sources are conflicting or insufficient
   - **unverifiable** -- no relevant sources found
4. Record the sources (URL + relevant snippet) for each claim

**Constraints:**
- Process claims sequentially -- do NOT use shell-level parallelism.
- Do not use WebFetch to read full pages unless the search snippet is genuinely insufficient to make a judgment.
- For each search, evaluate the top 3-5 results only.

### 4. Produce the fact-check report

#### JSON report (`$OUT/fact-check-report.json`)

Write the JSON report using the Write tool. Structure:

```json
{
  "meta": {
    "draft": "<path to checked draft>",
    "checked_at": "<ISO 8601 timestamp>",
    "total_claims": 24,
    "correct": 18,
    "incorrect": 3,
    "uncertain": 2,
    "unverifiable": 1
  },
  "claims": [
    {
      "id": "c001",
      "category": "heights_distances",
      "value": "2.469 Metern",
      "sentence": "...den Galdhopiggen mit 2.469 Metern.",
      "line": 32,
      "section": "Jotunheimen Nationalpark",
      "verdict": "correct",
      "corrected_value": null,
      "sources": [
        { "url": "https://...", "snippet": "Galdhopiggen, 2,469 m..." }
      ],
      "notes": "Confirmed by multiple sources."
    }
  ]
}
```

Field rules:
- `corrected_value` is non-null only when `verdict` is `"incorrect"`
- `sources` contains 1-3 source objects per claim
- `notes` is a brief explanation of the verdict reasoning

#### Markdown report (`$OUT/fact-check-report.md`)

Write the Markdown report using the Write tool. Structure:

```markdown
## Fact-Check Report: <draft title>

### Summary
- X claims checked
- Y correct, Z incorrect, W uncertain, V unverifiable

### Errors Found

| Claim | Section | Current Value | Correct Value | Sources |
|-------|---------|--------------|---------------|---------|
| c003  | ...     | ...          | ...           | [1],[2] |

### Uncertain Claims

| Claim | Section | Value | Notes | Sources |
|-------|---------|-------|-------|---------|
| c012  | ...     | ...   | ...   | [1]     |

### All Claims Detail

#### heights_distances
(full detail per claim in this category)

#### prices_costs
(full detail per claim in this category)

(... repeat for each category that has claims ...)

### Sources
1. <url>
2. <url>
(numbered list of all unique sources referenced above)
```

### 5. Apply corrections to draft

If the report contains claims with verdict `incorrect` and a non-null `corrected_value`:

1. For each incorrect claim, use the Edit tool to replace the erroneous value in the original draft with the `corrected_value`. Do NOT change anything else in the draft — no rewording, no restructuring, no additions.
2. After all corrections are applied, note the changes in the summary output.

If there are no incorrect claims, skip this step.

### 6. Summary output

Print a concise summary to the conversation:
- Total claims checked
- Count by verdict (correct / incorrect / uncertain / unverifiable)
- List of errors found with their corrected values (and confirmation that corrections were applied to the draft)
- List of uncertain claims requiring manual review
- File paths to the generated report files

Do NOT print the full report to the conversation -- the user can open the files directly.
