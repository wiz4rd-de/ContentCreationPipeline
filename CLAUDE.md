# Rules

## CRITICAL: GitHub CLI Multi-line Text

When passing multi-line text to `gh` commands, **ALWAYS** use the Write tool to save the text to `/tmp/gh-body.md` first, then use `--body-file`:

```bash
gh issue create --title "Title" --body-file /tmp/gh-body.md
gh pr create --title "Title" --body-file /tmp/gh-body.md
gh issue comment 32 --body-file /tmp/gh-body.md
```

For closing with a comment, use two commands (since `gh issue close --comment` has no `--body-file`):

```bash
gh issue comment 32 --body-file /tmp/gh-body.md && gh issue close 32
```

**NEVER** inline multi-line text containing `#` characters directly in the command string. The security hook will block it.

## Data Access

- Never guess at a file's structure (property names, nesting). Always read the file first to inspect the actual structure before writing code that accesses specific fields.

## Tool Usage

- **Use built-in tools instead of Bash for file operations.** Glob instead of `ls`/`find`, Grep instead of `grep`/`rg`, Read instead of `cat`/`head`/`tail`. This avoids shell security hook false positives (e.g., `2>/dev/null` triggers "quoted characters in flag names").
- **Never create temp scripts to read/modify JSON files.** Use the Read tool to load JSON, update values in your reasoning, and write back with the Write tool. No temp scripts, no heredocs, no `python -c` / `uv run python -c` one-liners.
- **Reserve Bash exclusively for running project scripts** (`uv run seo-pipeline ...`) and git commands. Everything else should use dedicated tools.
- **Cap verbose Bash output.** When a script may print large JSON or verbose progress to stdout, pipe through `| head -20` to avoid bloating the context window. Most pipeline scripts use `--output` flags and produce minimal stdout, but always cap when unsure. Do not suppress stderr (errors/stack traces are useful).

## Skill Files

- **Never use `>` redirections in `.claude/skills/` files.** Always use `--output <path>` flags instead. Shell redirections with variables (e.g. `> $OUT/file.json`) trigger Claude Code's security hook. This rule must be preserved when refactoring — introducing `$OUT` shorthand or any other change must not revert `--output` back to `>`.

## Shell

- **No shell-level parallelism.** Never use `&`, `wait`, or `2>&1` to run commands concurrently. Use multiple parallel Bash tool calls in a single message instead — Claude Code handles concurrency natively. This avoids security hook prompts and is simpler.
