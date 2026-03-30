#!/usr/bin/env bash
# Generates golden output snapshots from Node.js scripts.
# Each golden file is written to tests/golden/<script-name>--<fixture-name>.json.
#
# Uses --output flags (no shell redirections) per project conventions.
# Idempotent: re-running produces byte-identical output.
#
# Usage: bash scripts/generate-golden.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GOLDEN="$ROOT/tests/golden"
FIXTURES="$ROOT/test/fixtures"

mkdir -p "$GOLDEN"

echo "=== Generating golden output snapshots ==="

# ---------------------------------------------------------------------------
# 1. process-serp (5 fixtures, single input each)
# ---------------------------------------------------------------------------
echo "[1/10] process-serp"
for fixture in serp-with-aio serp-no-aio-no-paa serp-aio-encoding-artifacts serp-aio-no-text serp-paa-no-expanded; do
  node "$ROOT/src/serp/process-serp.mjs" \
    "$FIXTURES/process-serp/${fixture}.json" \
    --output "$GOLDEN/process-serp--${fixture}.json"
done

# ---------------------------------------------------------------------------
# 2. assemble-competitors (serp-processed + empty pages dir, --date for determinism)
# ---------------------------------------------------------------------------
echo "[2/10] assemble-competitors"
node "$ROOT/src/serp/assemble-competitors.mjs" \
  "$FIXTURES/assemble-briefing-data/2026-03-09_test-keyword/serp-processed.json" \
  "$FIXTURES/assemble-briefing-data/2026-03-09_test-keyword" \
  --date 2026-03-09 \
  --output "$GOLDEN/assemble-competitors--2026-03-09_test-keyword.json"

# ---------------------------------------------------------------------------
# 3. extract-keywords (5 fixtures via CLI wrapper)
# ---------------------------------------------------------------------------
echo "[3/10] extract-keywords"
for fixture in related-raw suggestions-raw suggestions-raw-flat related-empty suggestions-empty; do
  node "$ROOT/scripts/run-extract-keywords.mjs" \
    "$FIXTURES/keyword-expansion/${fixture}.json" \
    --output "$GOLDEN/extract-keywords--${fixture}.json"
done

# ---------------------------------------------------------------------------
# 4. process-keywords (3 fixture combinations)
# ---------------------------------------------------------------------------
echo "[4/10] process-keywords"

# Default: related-raw + suggestions-raw
node "$ROOT/src/keywords/process-keywords.mjs" \
  --related "$FIXTURES/process-keywords/related-raw.json" \
  --suggestions "$FIXTURES/process-keywords/suggestions-raw.json" \
  --seed "keyword recherche" \
  --output "$GOLDEN/process-keywords--default.json"

# Single related keyword
node "$ROOT/src/keywords/process-keywords.mjs" \
  --related "$FIXTURES/process-keywords/related-single.json" \
  --suggestions "$FIXTURES/process-keywords/suggestions-empty.json" \
  --seed "single keyword" \
  --output "$GOLDEN/process-keywords--related-single.json"

# Empty inputs
node "$ROOT/src/keywords/process-keywords.mjs" \
  --related "$FIXTURES/process-keywords/related-empty.json" \
  --suggestions "$FIXTURES/process-keywords/suggestions-empty.json" \
  --seed "empty test" \
  --output "$GOLDEN/process-keywords--empty.json"

# ---------------------------------------------------------------------------
# 5. filter-keywords (paired input: keywords-processed + serp-processed)
# ---------------------------------------------------------------------------
echo "[5/10] filter-keywords"
node "$ROOT/src/keywords/filter-keywords.mjs" \
  --keywords "$FIXTURES/filter-keywords/keywords-processed.json" \
  --serp "$FIXTURES/filter-keywords/serp-processed.json" \
  --seed "thailand urlaub" \
  --output "$GOLDEN/filter-keywords--default.json"

# Empty inputs
node "$ROOT/src/keywords/filter-keywords.mjs" \
  --keywords "$FIXTURES/filter-keywords/keywords-processed-empty.json" \
  --serp "$FIXTURES/filter-keywords/serp-processed-empty.json" \
  --seed "empty test" \
  --output "$GOLDEN/filter-keywords--empty.json"

# ---------------------------------------------------------------------------
# 6. prepare-strategist-data (multi-input: serp + keywords + competitor-kws)
# ---------------------------------------------------------------------------
echo "[6/10] prepare-strategist-data"
node "$ROOT/src/keywords/prepare-strategist-data.mjs" \
  --serp "$FIXTURES/prepare-strategist-data/serp-processed.json" \
  --keywords "$FIXTURES/prepare-strategist-data/keywords-processed.json" \
  --competitor-kws "$FIXTURES/prepare-strategist-data/competitor-kws.json" \
  --seed "seo reporting" \
  --output "$GOLDEN/prepare-strategist-data--default.json"

# Empty inputs
node "$ROOT/src/keywords/prepare-strategist-data.mjs" \
  --serp "$FIXTURES/prepare-strategist-data/serp-processed-empty.json" \
  --keywords "$FIXTURES/prepare-strategist-data/keywords-processed-empty.json" \
  --seed "empty test" \
  --output "$GOLDEN/prepare-strategist-data--empty.json"

# ---------------------------------------------------------------------------
# 7. analyze-content-topics (--pages-dir + --seed)
# ---------------------------------------------------------------------------
echo "[7/10] analyze-content-topics"
node "$ROOT/src/analysis/analyze-content-topics.mjs" \
  --pages-dir "$FIXTURES/analyze-content-topics/pages" \
  --seed "mallorca" \
  --output "$GOLDEN/analyze-content-topics--default.json"

# ---------------------------------------------------------------------------
# 8. analyze-page-structure (--pages-dir)
# ---------------------------------------------------------------------------
echo "[8/10] analyze-page-structure"
node "$ROOT/src/analysis/analyze-page-structure.mjs" \
  --pages-dir "$FIXTURES/analyze-page-structure/pages" \
  --output "$GOLDEN/analyze-page-structure--default.json"

# ---------------------------------------------------------------------------
# 9. compute-entity-prominence (--entities + --pages-dir)
# ---------------------------------------------------------------------------
echo "[9/10] compute-entity-prominence"
node "$ROOT/src/analysis/compute-entity-prominence.mjs" \
  --entities "$FIXTURES/compute-entity-prominence/entities.json" \
  --pages-dir "$FIXTURES/compute-entity-prominence/pages" \
  --output "$GOLDEN/compute-entity-prominence--default.json"

# ---------------------------------------------------------------------------
# 10. assemble-briefing-data (--dir, writes briefing-data.json into dir)
#     We run against a temporary copy to avoid modifying the fixture, then
#     copy the output to golden and freeze non-deterministic fields.
# ---------------------------------------------------------------------------
echo "[10/10] assemble-briefing-data"
TMPDIR_PARENT=$(mktemp -d)
TMPDIR_ABD="$TMPDIR_PARENT/2026-03-09_test-keyword"
mkdir -p "$TMPDIR_ABD"
cp -r "$FIXTURES/assemble-briefing-data/2026-03-09_test-keyword/." "$TMPDIR_ABD/"
# Remove any existing briefing-data.json so the script generates a fresh one
rm -f "$TMPDIR_ABD/briefing-data.json"
node "$ROOT/src/analysis/assemble-briefing-data.mjs" --dir "$TMPDIR_ABD"
cp "$TMPDIR_ABD/briefing-data.json" "$GOLDEN/assemble-briefing-data--2026-03-09_test-keyword.json"
rm -rf "$TMPDIR_PARENT"

# Post-process: freeze non-deterministic fields
node "$ROOT/scripts/freeze-briefing-fields.mjs" \
  "$GOLDEN/assemble-briefing-data--2026-03-09_test-keyword.json"

# ---------------------------------------------------------------------------
# Validation: check all golden files are valid JSON
# ---------------------------------------------------------------------------
echo ""
echo "=== Validating golden files ==="
ERRORS=0
for f in "$GOLDEN"/*.json; do
  if ! node -e "JSON.parse(require('fs').readFileSync('$f', 'utf-8'))" 2>/dev/null; then
    echo "INVALID JSON: $f"
    ERRORS=$((ERRORS + 1))
  fi
done

FILE_COUNT=$(ls -1 "$GOLDEN"/*.json 2>/dev/null | wc -l | tr -d ' ')
echo "Generated $FILE_COUNT golden files in tests/golden/"

if [ "$ERRORS" -gt 0 ]; then
  echo "ERROR: $ERRORS file(s) contain invalid JSON"
  exit 1
fi

echo "All golden files are valid JSON."
echo "=== Done ==="
