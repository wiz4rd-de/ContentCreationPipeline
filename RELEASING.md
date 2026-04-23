# Release Process

This document describes how to cut a new version of the Claude Content Creation Pipeline.

## Scope

The pipeline is **internal-only**. It is not published to PyPI, nor is a Docker image built today. A "release" here means:

1. Updating `CHANGELOG.md` and version constants in the repo.
2. Committing the version bump to `main`.
3. Creating an annotated git tag so the commit is easy to find later.

If a public artifact (PyPI package, Docker image, hosted service build) is added in the future, update this document accordingly.

## Pre-Release Checklist

Before releasing, ensure:

1. All tests pass: `uv run pytest`
2. All changes are committed to their feature branches
3. Code review is complete
4. Feature branches are merged to `main` via pull request

## Version Sources

Three places hold a version string today. A release must update all three to the same value:

- `pyproject.toml` → `[project].version`
- `seo_pipeline/__init__.py` → `__version__`
- `seo_pipeline/analysis/assemble_briefing_data.py` → `PIPELINE_VERSION`

`PIPELINE_VERSION` is embedded in every `briefing-data.json` output under `meta.pipeline_version` and serves as an audit trail for pipeline runs. It must match the package version.

## Release Steps

### 1. Update CHANGELOG.md

Move items from the `[Unreleased]` section to a new version section with today's date.

**Format:** Follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions:

- Use semantic versioning: `[X.Y.Z]`
- Include date in ISO 8601 format: `YYYY-MM-DD`
- Group changes into categories: Added, Changed, Fixed, Removed, etc.

**Example:**

```markdown
## [0.3.0] - 2026-05-01

### Added
- New feature A
- New feature B

### Fixed
- Bug fix X
```

### 2. Bump the Version in All Three Sources

Update the version string to the new `X.Y.Z`:

- `pyproject.toml` — `version = "X.Y.Z"`
- `seo_pipeline/__init__.py` — `__version__ = "X.Y.Z"`
- `seo_pipeline/analysis/assemble_briefing_data.py` — `PIPELINE_VERSION = "X.Y.Z"`

Note: some golden-test fixtures pin `pipeline_version` to a specific value (e.g. `tests/golden/assemble-briefing-data--2026-03-09_test-keyword.json`, `tests/test_analysis/test_assemble_briefing_data.py`, `tests/test_analysis/test_models_analysis.py`). If bumping `PIPELINE_VERSION` breaks those fixtures, update them in the same commit.

### 3. Verify Tests Still Pass

```bash
uv run pytest
```

All tests must pass before tagging.

### 4. Commit the Version Bump

One dedicated commit for the release:

```bash
git commit -am "chore: bump version to X.Y.Z"
```

### 5. Create the Git Tag

Annotated tag pointing at the bump commit:

```bash
git tag -a vX.Y.Z -m "Release X.Y.Z"
```

**Example:**

```bash
git tag -a v0.3.0 -m "Release 0.3.0"
```

### 6. Push Commit and Tag

```bash
git push origin main
git push origin vX.Y.Z
```

Or push both at once:

```bash
git push origin main --follow-tags
```

### 7. Create a GitHub Release (Optional)

If you want the release visible in the GitHub Releases UI:

```bash
gh release create vX.Y.Z --title "vX.Y.Z" --notes-from-tag
```

Or paste the CHANGELOG section explicitly using a body file (see `CLAUDE.md` for the `--body-file` convention).

## Important Notes

- **All three version sources must agree.** If `pyproject.toml`, `__version__`, and `PIPELINE_VERSION` drift apart, `briefing-data.json` outputs will carry misleading audit metadata. Keep them in sync every release.
- **One version per commit.** Use a dedicated `chore: bump version to X.Y.Z` commit so the release can be easily identified in git history.
- **Tags are immutable.** Do not delete or recreate tags. If a release needs revision, cut a new patch version instead.

## Future Work

Once the project gains a public distribution channel (PyPI, Docker Hub, internal artifact registry), extend this document with:

- The build command (`uv build`, `docker build`, etc.)
- The publish command and auth setup
- Any release automation (GitHub Actions workflow triggered by tag push)

Until then, the steps above are the release process.
