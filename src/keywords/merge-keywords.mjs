#!/usr/bin/env node
// Deterministic keyword merger for DataForSEO related_keywords + keyword_suggestions responses.
// Deduplicates case-insensitively, ensures seed keyword is always included.
// Same input always produces byte-identical output.
//
// Usage: node merge-keywords.mjs --related <file> --suggestions <file> --seed <keyword>
// Outputs JSON to stdout.

import { readFileSync } from 'node:fs';

// --- Parse arguments ---
const args = process.argv.slice(2);

function flagValue(name) {
  const idx = args.indexOf(name);
  return idx !== -1 ? args[idx + 1] : undefined;
}

const relatedFile = flagValue('--related');
const suggestionsFile = flagValue('--suggestions');
const seedKeyword = flagValue('--seed');

if (!relatedFile || !suggestionsFile || !seedKeyword) {
  console.error('Usage: node merge-keywords.mjs --related <file> --suggestions <file> --seed <keyword>');
  process.exit(1);
}

// --- Extract keywords from a DataForSEO Labs response ---
// Both related_keywords and keyword_suggestions share the same response shape:
// tasks[0].result[0].items[] with keyword_data.keyword and keyword_data.keyword_info
function extractKeywords(raw) {
  const items = raw?.tasks?.[0]?.result?.[0]?.items;
  if (!Array.isArray(items)) return [];

  return items
    .filter(item => item?.keyword_data?.keyword)
    .map(item => {
      const kd = item.keyword_data;
      const info = kd.keyword_info || {};
      return {
        keyword: kd.keyword.trim(),
        search_volume: info.search_volume ?? null,
        cpc: info.cpc ?? null,
        monthly_searches: info.monthly_searches ?? null,
      };
    });
}

// --- Load and extract ---
const relatedRaw = JSON.parse(readFileSync(relatedFile, 'utf-8'));
const suggestionsRaw = JSON.parse(readFileSync(suggestionsFile, 'utf-8'));

const relatedKeywords = extractKeywords(relatedRaw);
const suggestionsKeywords = extractKeywords(suggestionsRaw);

// --- Deduplicate case-insensitively ---
// When a keyword appears in both sources, prefer the one from related_keywords
// (it appears first in the merge order).
const seen = new Map(); // lowercase keyword -> merged record

for (const kw of relatedKeywords) {
  const key = kw.keyword.toLowerCase().trim();
  if (!seen.has(key)) {
    seen.set(key, { ...kw, source: 'related' });
  }
}
for (const kw of suggestionsKeywords) {
  const key = kw.keyword.toLowerCase().trim();
  if (!seen.has(key)) {
    seen.set(key, { ...kw, source: 'suggestions' });
  }
}

// --- Ensure seed keyword is always included ---
const seedKey = seedKeyword.toLowerCase().trim();
if (!seen.has(seedKey)) {
  seen.set(seedKey, {
    keyword: seedKeyword.trim(),
    search_volume: null,
    cpc: null,
    monthly_searches: null,
    source: 'seed',
  });
}

// --- Stable sort: search_volume desc, then alphabetical tie-break ---
const merged = [...seen.values()].sort((a, b) => {
  const volA = a.search_volume ?? -1;
  const volB = b.search_volume ?? -1;
  if (volB !== volA) return volB - volA;
  return a.keyword.toLowerCase().localeCompare(b.keyword.toLowerCase());
});

// --- Output ---
const output = {
  seed_keyword: seedKeyword.trim(),
  total_keywords: merged.length,
  keywords: merged,
};

console.log(JSON.stringify(output, null, 2));
