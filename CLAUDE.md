# Rules

## CRITICAL: GitHub CLI Multi-line Text

When passing multi-line text to `gh` commands (e.g., `--comment`, `--body`), **ALWAYS** use the Write tool to save the text to `/tmp/gh-body.md` first, then reference it:

```bash
gh issue close 32 --comment "$(cat /tmp/gh-body.md)"
gh pr create --title "Title" --body "$(cat /tmp/gh-body.md)"
```

**NEVER** inline multi-line text containing `#` characters directly in the command string. The security hook will block it.

## Data Access

- Never guess at a file's structure (property names, nesting). Always read the file first to inspect the actual structure before writing code that accesses specific fields.

## Tool Usage

- **Use built-in tools instead of Bash for file operations.** Glob instead of `ls`/`find`, Grep instead of `grep`/`rg`, Read instead of `cat`/`head`/`tail`. This avoids shell security hook false positives (e.g., `2>/dev/null` triggers "quoted characters in flag names").
- **Never create temp scripts to read/modify JSON files.** Use the Read tool to load JSON, update values in your reasoning, and write back with the Write tool. No `/tmp/*.mjs` files, no heredocs, no `node -e`.
- **Reserve Bash exclusively for running project scripts** (`node src/...`) and git commands. Everything else should use dedicated tools.

## Skill Files

- **Never use `>` redirections in `.claude/skills/` files.** Always use `--output <path>` flags instead. Shell redirections with variables (e.g. `> $OUT/file.json`) trigger Claude Code's security hook. This rule must be preserved when refactoring — introducing `$OUT` shorthand or any other change must not revert `--output` back to `>`.

## Shell

- Never use `!` in `node -e` commands. Zsh escapes `!` to `\!` even inside quotes, breaking JS syntax. Use `=== null`, `=== undefined`, or negate with `!(x == null)` style workarounds. For complex scripts, write to a temp `.mjs` file instead.
