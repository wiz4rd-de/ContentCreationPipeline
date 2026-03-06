#!/usr/bin/env node
// Deterministic merger: adds keyword_difficulty values from the DataForSEO
// keyword_difficulty/live response into the expanded keyword records.
// Keywords without KD data get difficulty: null (never 0, never guessed).
// Same input always produces byte-identical output.
//
// Usage: node merge-difficulty.mjs --expanded <file> --difficulty <file>
// Outputs JSON to stdout.

import { readFileSync } from 'node:fs';

// --- Parse arguments ---
const args = process.argv.slice(2);

function flagValue(name) {
  const idx = args.indexOf(name);
  return idx !== -1 ? args[idx + 1] : undefined;
}

const expandedFile = flagValue('--expanded');
const difficultyFile = flagValue('--difficulty');

if (!expandedFile || !difficultyFile) {
  console.error('Usage: node merge-difficulty.mjs --expanded <file> --difficulty <file>');
  process.exit(1);
}

// --- Load inputs ---
const expanded = JSON.parse(readFileSync(expandedFile, 'utf-8'));
const difficultyRaw = JSON.parse(readFileSync(difficultyFile, 'utf-8'));

// --- Build KD lookup (case-insensitive) ---
const kdMap = new Map();
const results = difficultyRaw?.tasks?.[0]?.result;
if (Array.isArray(results)) {
  for (const item of results) {
    if (item?.keyword != null && item?.keyword_difficulty != null) {
      const kd = Math.round(item.keyword_difficulty);
      // Clamp to 0-100 range
      const clamped = Math.max(0, Math.min(100, kd));
      kdMap.set(item.keyword.toLowerCase().trim(), clamped);
    }
  }
}

// --- Merge difficulty into keyword records ---
const keywords = expanded.keywords.map(kw => {
  const key = kw.keyword.toLowerCase().trim();
  const difficulty = kdMap.has(key) ? kdMap.get(key) : null;
  return { ...kw, difficulty };
});

// --- Output (preserves original sort order) ---
const output = {
  ...expanded,
  keywords,
};

console.log(JSON.stringify(output, null, 2));
