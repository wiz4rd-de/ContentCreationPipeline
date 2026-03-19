# Release Process

This document describes the step-by-step process for releasing a new version of the Claude Content Creation Pipeline.

## Pre-Release Checklist

Before releasing, ensure:

1. All tests pass: `npm test`
2. All changes are committed to the feature branch
3. Code review is complete
4. Feature branch is merged to `main` via pull request

## Release Steps

### 1. Update CHANGELOG.md

Move items from the `[Unreleased]` section to a new version section with today's date.

**Format:** Follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions:
- Use semantic versioning: `[X.Y.Z]`
- Include date in ISO 8601 format: `YYYY-MM-DD`
- Group changes into categories: Added, Changed, Fixed, Removed, etc.

**Example:**

```markdown
## [0.3.0] - 2026-03-20

### Added
- New feature A
- New feature B

### Fixed
- Bug fix X
- Bug fix Y
```

### 2. Update Version in package.json

Use npm to bump the version:

```bash
npm version <major|minor|patch> --no-git-tag-version
```

This updates the `version` field in `package.json` without creating a git tag or commit (we do those manually).

**Example:**

```bash
npm version minor --no-git-tag-version
# Updates package.json from 0.2.0 to 0.3.0
```

### 3. Update PIPELINE_VERSION

Update the `PIPELINE_VERSION` constant in `src/analysis/assemble-briefing-data.mjs` (line 12) to match the new version.

This constant is embedded in the `briefing-data.json` output and serves as an audit trail for pipeline runs.

**Example:**

```javascript
const PIPELINE_VERSION = '0.3.0';
```

### 4. Verify Version Consistency

Ensure all version references match:
- `package.json` → version field
- `src/analysis/assemble-briefing-data.mjs` → PIPELINE_VERSION constant

Run tests to ensure nothing is broken:

```bash
npm test
```

### 5. Commit the Version Bump

Create a single commit with the version update:

```bash
git commit -am "chore: bump version to X.Y.Z"
```

### 6. Create Git Tag

Tag the release:

```bash
git tag vX.Y.Z
```

**Example:**

```bash
git tag v0.3.0
```

### 7. Push to Remote

Push both the commit and the tag:

```bash
git push origin main
git push origin vX.Y.Z
```

Or push all tags at once:

```bash
git push origin main --tags
```

### 8. Create GitHub Release (Optional)

Create a release on GitHub with release notes:

```bash
gh release create vX.Y.Z --title "vX.Y.Z" --notes-from-tag
```

Or manually paste the CHANGELOG section:

```bash
gh release create vX.Y.Z --title "vX.Y.Z" --notes "$(cat <<'EOF'
## [0.3.0] - 2026-03-20

### Added
- ...

### Fixed
- ...
EOF
)"
```

## Important Notes

- **PIPELINE_VERSION must be kept in sync.** The `PIPELINE_VERSION` constant in `src/analysis/assemble-briefing-data.mjs` is embedded in every `briefing-data.json` output. If it falls out of sync with `package.json`, pipeline runs will have mismatched version metadata.
- **One version per commit.** Use a dedicated `chore: bump version to X.Y.Z` commit so the release can be easily identified in git history.
- **Tags are immutable.** Do not delete or recreate tags; if a release needs revision, create a new patch version instead.

## Automating the Release Process

The steps above can be automated with a shell script or Node.js tool. A future enhancement could add `npm run release` to automate the mechanical steps (CHANGELOG → package.json → PIPELINE_VERSION → commit → tag → push → GitHub release).
