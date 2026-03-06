#!/usr/bin/env node
// Deterministic keyword processor: merges raw DataForSEO responses into a
// structured JSON skeleton with intent tags, n-gram clusters, and null
// placeholders for LLM-only fields. Same input always produces byte-identical
// output.
//
// Keyword difficulty is extracted directly from the related_keywords and
// keyword_suggestions responses (keyword_data.keyword_properties.keyword_difficulty),
// eliminating the need for a separate keyword_difficulty/live API call.
//
// Usage:
//   node process-keywords.mjs \
//     --related keywords-related-raw.json \
//     --suggestions keywords-suggestions-raw.json \
//     --seed "keyword recherche" \
//     [--volume keywords-volume-raw.json] \
//     [--brands "brand1,brand2"]

import { readFileSync } from 'node:fs';
import { extractKeywords } from './extract-keywords.mjs';

// --- Parse arguments --------------------------------------------------------

const args = process.argv.slice(2);

function flagValue(name) {
  const idx = args.indexOf(name);
  return idx !== -1 ? args[idx + 1] : undefined;
}

const relatedFile = flagValue('--related');
const suggestionsFile = flagValue('--suggestions');
const volumeFile = flagValue('--volume');
const seedKeyword = flagValue('--seed');
const brandsRaw = flagValue('--brands');

if (!relatedFile || !suggestionsFile || !seedKeyword) {
  console.error(
    'Usage: node process-keywords.mjs --related <file> --suggestions <file> --seed <keyword> ' +
    '[--volume <file>] [--brands "brand1,brand2"]',
  );
  process.exit(1);
}

// --- Intent patterns --------------------------------------------------------
// Word-boundary regex patterns for DE + EN intent classification.
// Order matters: first match wins (transactional > commercial > informational).

const INTENT_PATTERNS = {
  transactional: /\b(kaufen|buy|price|preis|bestellen|coupon|gutschein|discount|rabatt)\b/i,
  commercial: /\b(best|beste|bester|bestes|top|review|vergleich|vs|test|erfahrung|empfehlung)\b/i,
  informational: /\b(how|wie|what|was ist|guide|anleitung|tutorial|tipps|lernen)\b/i,
};

const brandList = brandsRaw
  ? brandsRaw.split(',').map(b => b.trim().toLowerCase()).filter(Boolean)
  : [];

// --- Helpers ----------------------------------------------------------------

function readJSON(path) {
  return JSON.parse(readFileSync(path, 'utf-8'));
}

// extractKeywords is imported from ./extract-keywords.mjs
// It handles both related_keywords and keyword_suggestions response shapes
// and extracts keyword_difficulty from keyword_properties.

// Build a case-insensitive lookup from a separate volume response (optional).
// Expected shape: tasks[0].result[] with keyword, search_volume, cpc.
function buildVolumeMap(raw) {
  const map = new Map();
  const results = raw?.tasks?.[0]?.result;
  if (!Array.isArray(results)) return map;
  for (const item of results) {
    if (item?.keyword != null) {
      map.set(item.keyword.toLowerCase().trim(), {
        search_volume: item.search_volume ?? null,
        cpc: item.cpc ?? null,
      });
    }
  }
  return map;
}

// Classify search intent deterministically.
function classifyIntent(keyword) {
  const lower = keyword.toLowerCase();

  // Check navigational first (brand list)
  if (brandList.length > 0) {
    for (const brand of brandList) {
      if (lower.includes(brand)) return 'navigational';
    }
  }

  // Check patterns in priority order
  if (INTENT_PATTERNS.transactional.test(lower)) return 'transactional';
  if (INTENT_PATTERNS.commercial.test(lower)) return 'commercial';
  if (INTENT_PATTERNS.informational.test(lower)) return 'informational';

  return null;
}

// Tokenize a keyword into lowercase word n-grams (unigrams).
function tokenize(keyword) {
  return keyword.toLowerCase().split(/\s+/).filter(Boolean);
}

// Jaccard similarity between two token sets.
function jaccard(setA, setB) {
  let intersection = 0;
  for (const token of setA) {
    if (setB.has(token)) intersection++;
  }
  const union = setA.size + setB.size - intersection;
  if (union === 0) return 0;
  return intersection / union;
}

// --- Pipeline ---------------------------------------------------------------

// 1. Read all raw JSON files
const relatedRaw = readJSON(relatedFile);
const suggestionsRaw = readJSON(suggestionsFile);
const volumeMap = volumeFile ? buildVolumeMap(readJSON(volumeFile)) : new Map();

// 2. Extract and deduplicate (case-insensitive, trimmed)
const relatedKeywords = extractKeywords(relatedRaw, { includeDifficulty: true });
const suggestionsKeywords = extractKeywords(suggestionsRaw, { includeDifficulty: true });

const seen = new Map(); // lowercase key -> record

for (const kw of relatedKeywords) {
  const key = kw.keyword.toLowerCase().trim();
  if (!seen.has(key)) seen.set(key, kw);
}
for (const kw of suggestionsKeywords) {
  const key = kw.keyword.toLowerCase().trim();
  if (!seen.has(key)) seen.set(key, kw);
}

// Ensure seed keyword is always present
const seedKey = seedKeyword.toLowerCase().trim();
if (!seen.has(seedKey)) {
  seen.set(seedKey, {
    keyword: seedKeyword.trim(),
    search_volume: null,
    cpc: null,
    monthly_searches: null,
  });
}

// 3. Merge volume (from separate endpoint, if provided); difficulty comes
//    from the extracted keyword records (keyword_properties.keyword_difficulty)
const merged = [...seen.values()].map(kw => {
  const key = kw.keyword.toLowerCase().trim();

  // Override volume/CPC from separate volume endpoint if available
  const vol = volumeMap.get(key);
  const search_volume = vol?.search_volume ?? kw.search_volume;
  const cpc = vol?.cpc ?? kw.cpc;

  return {
    keyword: kw.keyword,
    search_volume,
    cpc,
    monthly_searches: kw.monthly_searches,
    difficulty: kw.difficulty ?? null,
  };
});

// Stable sort: volume desc, then alphabetical tie-break
merged.sort((a, b) => {
  const volA = a.search_volume ?? -1;
  const volB = b.search_volume ?? -1;
  if (volB !== volA) return volB - volA;
  return a.keyword.toLowerCase().localeCompare(b.keyword.toLowerCase());
});

// 4. Tag intent
for (const kw of merged) {
  kw.intent = classifyIntent(kw.keyword);
}

// 5. Cluster via n-gram overlap (Jaccard >= 0.5, greedy to highest-volume keyword)
// Keywords are already sorted by volume desc, so first keyword in each cluster
// is the highest-volume one (the cluster representative).

const tokenSets = merged.map(kw => new Set(tokenize(kw.keyword)));
const clusterAssignment = new Array(merged.length).fill(-1);
let nextClusterId = 0;

for (let i = 0; i < merged.length; i++) {
  if (clusterAssignment[i] !== -1) continue;

  // Start a new cluster with this keyword as representative
  const clusterId = nextClusterId++;
  clusterAssignment[i] = clusterId;

  // Greedily assign unassigned keywords with Jaccard >= 0.5
  for (let j = i + 1; j < merged.length; j++) {
    if (clusterAssignment[j] !== -1) continue;
    if (jaccard(tokenSets[i], tokenSets[j]) >= 0.5) {
      clusterAssignment[j] = clusterId;
    }
  }
}

// Group into cluster objects
const clusterMap = new Map(); // clusterId -> { representative index, member indices }
for (let i = 0; i < merged.length; i++) {
  const cid = clusterAssignment[i];
  if (!clusterMap.has(cid)) {
    clusterMap.set(cid, { repIdx: i, members: [] });
  }
  clusterMap.get(cid).members.push(i);
}

// Build cluster array sorted by representative volume desc (already in order
// since we iterate merged in volume-desc order)
const clusters = [];
for (const [, { repIdx, members }] of clusterMap) {
  const representative = merged[repIdx];
  const keywords = members.map(idx => merged[idx]);

  clusters.push({
    cluster_keyword: representative.keyword,
    cluster_label: null, // LLM field
    strategic_notes: null, // LLM field
    keyword_count: keywords.length,
    keywords,
  });
}

// 6. Opportunity score per keyword + re-sort within clusters
// Formula: opportunity_score = search_volume / (keyword_difficulty + 1)
//   - volume null or 0 → score 0
//   - difficulty null → score null
//   - Round to 2 decimal places

function computeOpportunityScore(volume, difficulty) {
  if (difficulty == null) return null;
  if (volume == null || volume === 0) return 0;
  return Math.round((volume / (difficulty + 1)) * 100) / 100;
}

for (const cluster of clusters) {
  // Compute scores
  for (const kw of cluster.keywords) {
    kw.opportunity_score = computeOpportunityScore(kw.search_volume, kw.difficulty);
  }

  // Re-sort: score desc, then volume desc, then alphabetical tie-break
  cluster.keywords.sort((a, b) => {
    const scoreA = a.opportunity_score ?? -1;
    const scoreB = b.opportunity_score ?? -1;
    if (scoreB !== scoreA) return scoreB - scoreA;
    const volA = a.search_volume ?? -1;
    const volB = b.search_volume ?? -1;
    if (volB !== volA) return volB - volA;
    return a.keyword.toLowerCase().localeCompare(b.keyword.toLowerCase());
  });

  // Cluster-level aggregate: average of all scores (nulls count as 0 in sum, but
  // still count toward cluster_size for a fair average)
  const scoreSum = cluster.keywords.reduce(
    (sum, kw) => sum + (kw.opportunity_score ?? 0), 0,
  );
  cluster.cluster_opportunity = cluster.keywords.length > 0
    ? Math.round((scoreSum / cluster.keywords.length) * 100) / 100
    : 0;
}

// 7. Output JSON skeleton
const output = {
  seed_keyword: seedKeyword.trim(),
  total_keywords: merged.length,
  total_clusters: clusters.length,
  clusters,
};

console.log(JSON.stringify(output, null, 2));
