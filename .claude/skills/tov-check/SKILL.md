---
name: tov-check
description: Run a ToV (Tone of Voice) compliance audit on a content draft. Use after the draft is written to catch style and brand guideline violations before publication.
---

# ToV Compliance Check

Audit a content draft against the DERTOUR Tone of Voice guidelines. Produces structured reports (JSON + Markdown) listing violations with line numbers, rule references, and correction suggestions.

## Inputs

Ask the user for:
1. **Which draft to check** -- pick from available `draft-*.md` files in the current output folder, or provide a path
2. **ToV file** (optional) -- scan `templates/` for files matching `*ToV*` or `*tov*` (case-insensitive) and offer matches as options; default is `templates/DT_ToV_v3.md`
3. **Output directory** (optional) -- defaults to the draft's parent directory

## Steps

### 1. Run the ToV compliance check

```bash
uv run seo-pipeline tov-check --draft <path-to-draft> --tov <path-to-tov>
```

If the user specified an output directory, add `--dir <path>`.

### 2. Read and summarize the report

Read `tov-check-report.json` from the output directory using the Read tool.

Print a concise summary to the conversation:
- Compliance status (compliant / non-compliant)
- Count by severity (critical / warning)
- List of critical violations with their rule references and suggestions
- Count of warnings (list only if few)
- File paths to the generated report files

Do NOT print the full report to the conversation -- the user can open the files directly.

### 3. Recommended next steps

If violations were found:
- Suggest fixing critical violations first (Constraint-Gruppe A and B)
- Suggest using `/content-revision` to apply corrections
- Suggest re-running `/tov-check` after revisions to verify compliance

If compliant:
- Suggest proceeding to `/fact-check` if not already done
