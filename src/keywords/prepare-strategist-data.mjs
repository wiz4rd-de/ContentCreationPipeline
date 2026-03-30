#!/usr/bin/env node
// Deterministic data preparation for the content strategist LLM step.
// Reads serp-processed.json and keywords-processed.json, deduplicates keywords
// with year normalization, filters foreign-language entries, extracts PAA
// questions and SERP snippets, and outputs a structured JSON skeleton to stdout.
//
// Usage:
//   node prepare-strategist-data.mjs \
//     --serp <serp-processed.json> \
//     --keywords <keywords-processed.json> \
//     [--competitor-kws <file>] \
//     --seed <keyword>

import { readFileSync, writeFileSync } from 'node:fs';

// --- Parse arguments --------------------------------------------------------

const args = process.argv.slice(2);

function flagValue(name) {
  const idx = args.indexOf(name);
  return idx !== -1 ? args[idx + 1] : undefined;
}

const serpFile = flagValue('--serp');
const keywordsFile = flagValue('--keywords');
const competitorKwsFile = flagValue('--competitor-kws');
const seedKeyword = flagValue('--seed');
const outputPath = flagValue('--output') || null;

if (serpFile === undefined || keywordsFile === undefined || seedKeyword === undefined) {
  console.error(
    'Usage: node prepare-strategist-data.mjs --serp <file> --keywords <file> --seed <keyword> ' +
    '[--competitor-kws <file>] [--output <file>]',
  );
  process.exit(1);
}

// --- Helpers ----------------------------------------------------------------

function readJSON(path) {
  return JSON.parse(readFileSync(path, 'utf-8'));
}

// Regex to detect non-Latin characters (foreign language heuristic).
// Allows basic Latin, extended Latin, Latin Extended Additional, whitespace,
// hyphens, apostrophes, digits, and common punctuation.
const FOREIGN_RE = /[^\x20-\u024F\u1E00-\u1EFF\s\-'0-9.,;:?&()/"]/;

function isForeignLanguage(keyword) {
  return FOREIGN_RE.test(keyword);
}

// Year normalization for dedup: replace 2024-2029 with YYYY.
function yearNormalizedKey(keyword) {
  return keyword.toLowerCase().trim().replace(/\b(202[4-9])\b/g, 'YYYY');
}

// --- Read input files -------------------------------------------------------

const serp = readJSON(serpFile);
const keywordsData = readJSON(keywordsFile);
const competitorKwsRaw = competitorKwsFile ? readJSON(competitorKwsFile) : [];

// --- Extract all keywords from clusters -------------------------------------

function flattenKeywords(data) {
  if (data.clusters === undefined || data.clusters === null) return [];
  const result = [];
  for (const cluster of data.clusters) {
    if (cluster.keywords === undefined || cluster.keywords === null) continue;
    for (const kw of cluster.keywords) {
      result.push(kw);
    }
  }
  return result;
}

const allRawKeywords = flattenKeywords(keywordsData);

// --- Deduplicate with year normalization ------------------------------------
// For keywords that differ only by year (e.g. "seo reporting 2025" vs
// "seo reporting 2026"), keep the one with the highest search volume.

const dedupMap = new Map(); // yearNormalizedKey -> keyword record

for (const kw of allRawKeywords) {
  const normKey = yearNormalizedKey(kw.keyword);
  const existing = dedupMap.get(normKey);
  if (existing === undefined) {
    dedupMap.set(normKey, kw);
  } else {
    // Keep the one with higher search volume
    const existingVol = existing.search_volume ?? -1;
    const currentVol = kw.search_volume ?? -1;
    if (currentVol > existingVol) {
      dedupMap.set(normKey, kw);
    } else if (currentVol === existingVol) {
      // Alphabetical tie-break for determinism
      if (kw.keyword.toLowerCase() < existing.keyword.toLowerCase()) {
        dedupMap.set(normKey, kw);
      }
    }
  }
}

const deduped = [...dedupMap.values()];

// --- Filter foreign-language keywords ---------------------------------------

const latinKeywords = deduped.filter(kw => {
  return (isForeignLanguage(kw.keyword) === false);
});

// --- Classify keywords by type ----------------------------------------------
// Top keywords: sorted by search_volume desc, take top 20
// All keywords: full deduped+filtered list sorted by volume desc

function sortByVolumeDesc(arr) {
  return arr.slice().sort((a, b) => {
    const volA = a.search_volume ?? -1;
    const volB = b.search_volume ?? -1;
    if (volB !== volA) return volB - volA;
    return a.keyword.toLowerCase().localeCompare(b.keyword.toLowerCase());
  });
}

const sortedKeywords = sortByVolumeDesc(latinKeywords);
const topKeywords = sortedKeywords.slice(0, 20).map(kw => ({
  keyword: kw.keyword,
  search_volume: kw.search_volume ?? null,
  difficulty: kw.difficulty ?? null,
  intent: kw.intent ?? null,
  opportunity_score: kw.opportunity_score ?? null,
}));

const allKeywords = sortedKeywords.map(kw => ({
  keyword: kw.keyword,
  search_volume: kw.search_volume ?? null,
  difficulty: kw.difficulty ?? null,
  intent: kw.intent ?? null,
  opportunity_score: kw.opportunity_score ?? null,
}));

// --- Autocomplete / content ideas -------------------------------------------
// Keywords that contain the seed as a phrase are autocomplete-style;
// remaining non-seed keywords are content ideas.

const seedLower = seedKeyword.toLowerCase().trim();

const autocomplete = [];
const contentIdeas = [];

for (const kw of sortedKeywords) {
  const kwLower = kw.keyword.toLowerCase().trim();
  if (kwLower === seedLower) continue;
  if (kwLower.includes(seedLower)) {
    autocomplete.push(kw.keyword);
  } else {
    contentIdeas.push(kw.keyword);
  }
}

// --- PAA questions from SERP data -------------------------------------------

const paaQuestions = [];
const paaRaw = serp.serp_features?.people_also_ask;
if (Array.isArray(paaRaw)) {
  for (const q of paaRaw) {
    // Support both new object format and legacy string format
    if (typeof q === 'string' && q.length > 0) {
      paaQuestions.push({ question: q, answer: null });
    } else if (q && typeof q === 'object' && typeof q.question === 'string' && q.question.length > 0) {
      paaQuestions.push({ question: q.question, answer: q.answer || null });
    }
  }
}

// --- SERP snippets from competitor data -------------------------------------

const serpSnippets = [];
const competitors = serp.competitors;
if (Array.isArray(competitors)) {
  for (const comp of competitors) {
    if (comp.title === undefined && comp.description === undefined) continue;
    serpSnippets.push({
      rank: comp.rank ?? null,
      title: comp.title ?? null,
      description: comp.description ?? null,
      url: comp.url ?? null,
      domain: comp.domain ?? null,
    });
  }
}

// --- Competitor keywords (optional) -----------------------------------------

const competitorKeywords = [];
if (Array.isArray(competitorKwsRaw)) {
  for (const kw of competitorKwsRaw) {
    if (kw.keyword === undefined && kw.search_volume === undefined) continue;
    competitorKeywords.push({
      keyword: kw.keyword ?? null,
      search_volume: kw.search_volume ?? null,
      difficulty: kw.difficulty ?? null,
    });
  }
}
// Sort for determinism
competitorKeywords.sort((a, b) => {
  const volA = a.search_volume ?? -1;
  const volB = b.search_volume ?? -1;
  if (volB !== volA) return volB - volA;
  return (a.keyword ?? '').toLowerCase().localeCompare((b.keyword ?? '').toLowerCase());
});

// --- Stats ------------------------------------------------------------------

const volumeValues = latinKeywords
  .map(kw => kw.search_volume)
  .filter(v => v != null && v > 0);

const totalVolume = volumeValues.reduce((sum, v) => sum + v, 0);
const avgVolume = volumeValues.length > 0
  ? Math.round(totalVolume / volumeValues.length)
  : 0;

const difficultyValues = latinKeywords
  .map(kw => kw.difficulty)
  .filter(v => v != null);

const avgDifficulty = difficultyValues.length > 0
  ? Math.round(difficultyValues.reduce((sum, v) => sum + v, 0) / difficultyValues.length * 100) / 100
  : null;

const stats = {
  total_keywords: allKeywords.length,
  keywords_with_volume: volumeValues.length,
  total_search_volume: totalVolume,
  avg_search_volume: avgVolume,
  avg_difficulty: avgDifficulty,
  paa_count: paaQuestions.length,
  serp_snippet_count: serpSnippets.length,
  competitor_keyword_count: competitorKeywords.length,
  foreign_filtered_count: deduped.length - latinKeywords.length,
  year_dedup_count: allRawKeywords.length - deduped.length,
};

// --- Build output -----------------------------------------------------------

const output = {
  seed_keyword: seedKeyword.trim(),
  top_keywords: topKeywords,
  all_keywords: allKeywords,
  autocomplete,
  content_ideas: contentIdeas,
  paa_questions: paaQuestions,
  serp_snippets: serpSnippets,
  competitor_keywords: competitorKeywords,
  stats,
};

const json = JSON.stringify(output, null, 2);
if (outputPath) {
  writeFileSync(outputPath, json);
} else {
  console.log(json);
}
