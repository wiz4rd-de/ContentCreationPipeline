# Rules

## Data Access

- Never guess at a file's structure (property names, nesting). Always read the file first to inspect the actual structure before writing code that accesses specific fields.

## Shell

- Never use `!` in `node -e` commands. Zsh escapes `!` to `\!` even inside quotes, breaking JS syntax. Use `=== null`, `=== undefined`, or negate with `!(x == null)` style workarounds. For complex scripts, write to a temp `.mjs` file instead.
