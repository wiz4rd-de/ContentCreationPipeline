---
name: refine-issues
description: Have junior-developer, senior-engineer, and quality-assurance review open issues for ambiguities, then dispatch plan-and-ticket to apply improvements. Use before implementation to harden ticket quality.
---

# Refine Issues

Three reviewer agents (junior-developer, senior-engineer, quality-assurance) independently review all open GitHub issues, then plan-and-ticket consolidates their feedback and edits the issues.

## Inputs

Ask the user for:
1. **Label filter** (optional, default: all open issues) -- e.g., `python-rewrite` to scope to a specific set of issues
2. **Issue range** (optional) -- specific issue numbers to review instead of all open issues

## Steps

### 1. Fetch open issues

Fetch all open issues matching the filter. For each issue, capture the full body (title, description, acceptance criteria, dependencies). Use `gh issue list` and `gh issue view`.

Store the issue data so it can be passed to the reviewer agents.

### 2. Launch three reviewer agents in parallel

Launch **junior-developer**, **senior-engineer**, and **quality-assurance** as subagents simultaneously using the Agent tool. Each agent receives the same set of issues and the same review prompt (below), but reviews from its own perspective.

**IMPORTANT:** All three Agent tool calls MUST be in a single message to run in parallel.

Each agent receives this prompt (with `{{ROLE}}` and `{{PERSPECTIVE}}` substituted):

```
You are reviewing GitHub issues as a {{ROLE}} — you are NOT implementing anything.
Do NOT write code, create files, run tests, close issues, or make any changes.
Your only job is to READ issues and the referenced source code, then produce a written review.

## Your perspective
{{PERSPECTIVE}}

## Issues to review
<paste the fetched issue data here>

## For each issue, evaluate

1. **Clarity & completeness of acceptance criteria**
   - Are the criteria specific and testable, or vague?
   - Are there implicit requirements that should be made explicit?
   - Would you know exactly when this issue is "done"?

2. **Scope assessment (suggest a size label: S / M / L / XL)**
   - S: < 100 LOC, single file, straightforward
   - M: 100-300 LOC, 2-3 files, some complexity
   - L: 300-500 LOC, multiple files, significant complexity
   - XL: > 500 LOC or high-risk (parser swap, rounding-sensitive, etc.)
   - Read the actual source files referenced in the issue to assess real complexity — do not guess from the description alone.

3. **Ambiguities or missing information**
   - What questions would you need answered before starting implementation?
   - Are dependencies on other issues correctly stated?
   - Are there edge cases, error scenarios, or platform differences not mentioned?

4. **Split or merge recommendations**
   - Is this issue too large for a single PR? Where would you split it?
   - Is this issue trivially small and should be merged with a sibling?

## Output format

Return a structured review as markdown. For each issue:

### Issue #<number>: <title>

**Size:** S / M / L / XL
**Clarity:** clear / needs work / unclear
**Verdict:** ready / needs refinement

**Feedback:**
- <bullet point per observation, question, or suggested change>

**Suggested acceptance criteria changes:**
- <add / remove / reword specific criteria, or "none">

**Split/merge recommendation:**
- <recommendation, or "none — scope is appropriate">
```

The perspective substitutions:

- **junior-developer**: "You are a junior developer who will implement these issues. Focus on whether the specs are clear enough for someone to pick up and implement without guessing. Flag anything where you'd be unsure what to do or where to start. Note missing file paths, unclear function signatures, or underspecified edge cases."

- **senior-engineer**: "You are a senior engineer responsible for code quality and architecture. Focus on cross-issue dependencies, risk assessment, and whether the implementation notes reflect the actual codebase complexity. Read the referenced Node.js source files to verify that the described scope matches reality. Flag issues where the acceptance criteria underestimate the work or miss architectural concerns (rounding, sort stability, parser differences)."

- **quality-assurance**: "You are a QA specialist who will verify these issues after implementation. Focus on whether the acceptance criteria are concrete and verifiable. Can each criterion be checked with evidence (a test, a file read, a diff)? Flag criteria that are subjective, unmeasurable, or missing. Suggest specific test scenarios or verification steps that should be added."

### 3. Collect and consolidate reviews

After all three agents return, combine their feedback into a single consolidated review document organized by issue number. For each issue, show all three perspectives side by side.

### 4. Dispatch plan-and-ticket to apply changes

Launch the **plan-and-ticket** agent with the consolidated review and this prompt:

```
You are receiving consolidated review feedback from three reviewers (junior-developer, senior-engineer, quality-assurance) on existing GitHub issues.

Your job is to EDIT the existing issues based on the feedback — not create new issues (unless a split is needed).

## Consolidated review
<paste the full consolidated review here>

## For each issue that has verdict "needs refinement" from ANY reviewer:

1. Read the current issue with `gh issue view #N`
2. Evaluate the feedback from all three reviewers
3. Apply improvements:
   - Sharpen vague acceptance criteria into specific, testable statements
   - Add missing edge cases, file paths, function signatures, or dependencies
   - Add a size label (S/M/L/XL) based on the consensus or most conservative estimate
   - Fix incorrect dependency references
4. Update the issue using `gh issue edit #N --body-file /tmp/gh-body.md`

## If a reviewer recommends splitting an issue:

1. Create the new child issues with `gh issue create`
2. Update the parent epic's task list to reference the new issues
3. Close the original oversized issue with a comment linking to the replacements
4. Add new issues to GitHub Project #6: `gh project item-add 6 --owner wiz4rd-de --url <issue-url>`
5. Label new issues with `python-rewrite`

## If a reviewer recommends merging issues:

1. Combine the acceptance criteria into the surviving issue
2. Close the redundant issue with a comment linking to the surviving one
3. Update the parent epic's task list

## Rules
- Do NOT create issues for items that all three reviewers marked as "ready"
- Preserve existing context and implementation notes — only add or sharpen, don't remove information
- When reviewers disagree, prefer the more conservative (more detailed) suggestion
- Save multi-line body text to /tmp/gh-body.md before passing to gh commands — never inline text with # characters
```

### 5. Summary output

Print a concise summary to the conversation:
- How many issues were reviewed
- How many were marked "ready" vs "needs refinement"
- What changes were made (issues edited, split, merged)
- Any unresolved disagreements between reviewers that need the user's input
