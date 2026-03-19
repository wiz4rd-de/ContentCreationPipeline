#!/usr/bin/env node
// WDF*IDF content draft scoring script.
// Compares a draft's term profile against the competitor average using WDF*IDF.
//
// Usage:
//   node score-draft-wdfidf.mjs --draft <path/to/draft.txt> --pages-dir <pages/>
//     [--language de] [--threshold 0.1]
// Outputs JSON to stdout. Same inputs always produce byte-identical output.

import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tokenize, removeStopwords, loadStopwordSet } from '../utils/tokenizer.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- CLI parsing ---
const args = process.argv.slice(2);
function flag(name) {
  const idx = args.indexOf(name);
  if (idx === -1 || idx + 1 >= args.length) return undefined;
  return args[idx + 1];
}

const draftPath = flag('--draft');
const pagesDir = flag('--pages-dir');
const language = flag('--language') || 'de';
const thresholdRaw = flag('--threshold');
const THRESHOLD = thresholdRaw === undefined ? 0.1 : parseFloat(thresholdRaw);

if (draftPath === undefined || pagesDir === undefined) {
  console.error(
    'Usage: node score-draft-wdfidf.mjs --draft <path> --pages-dir <pages/> [--language de] [--threshold 0.1]'
  );
  process.exit(1);
}

// --- IDF reference table ---
// Loads idf-de.json for German; returns null for other languages or on failure.
// Falls back to corpus-local IDF when null is returned.
function loadIdfTable(lang) {
  if (lang !== 'de') return null;
  try {
    const raw = JSON.parse(readFileSync(join(__dirname, '../utils/idf-de.json'), 'utf-8'));
    return raw.idf || null;
  } catch {
    return null;
  }
}

// --- WDF formula ---
// wdf(t, d) = log2(tf(t, d) + 1) / log2(wordCount(d))
// Returns 0 when wordCount(d) <= 1 (log2(1) = 0; avoids division by zero).
function computeWdf(tf, wordCount) {
  if (wordCount <= 1) return 0;
  return Math.log2(tf + 1) / Math.log2(wordCount);
}

// --- Term extraction ---
// Unigrams: stopwords removed. Bigrams/trigrams: all-stopword n-grams removed.
function isAllStopwords(ngram, stopwordSet) {
  return ngram.split(' ').every(w => stopwordSet.has(w));
}

function extractNgrams(tokens, n) {
  const result = [];
  for (let i = 0; i <= tokens.length - n; i++) {
    result.push(tokens.slice(i, i + n).join(' '));
  }
  return result;
}

function countTerms(termList) {
  const counts = new Map();
  for (const t of termList) {
    counts.set(t, (counts.get(t) || 0) + 1);
  }
  return counts;
}

// Returns { termCounts: Map<term, count>, wordCount: number }
function extractTermsFromText(text, stopwordSet) {
  const allTokens = tokenize(text);
  const wordCount = allTokens.length;
  const filteredTokens = removeStopwords(allTokens, stopwordSet);
  const allTerms = [
    ...extractNgrams(filteredTokens, 1),
    ...extractNgrams(allTokens, 2).filter(ng => isAllStopwords(ng, stopwordSet) === false),
    ...extractNgrams(allTokens, 3).filter(ng => isAllStopwords(ng, stopwordSet) === false),
  ];
  return { termCounts: countTerms(allTerms), wordCount };
}

// --- Rounding helper ---
function round6(v) {
  return Math.round(v * 1000000) / 1000000;
}

// --- Main ---
const stopwordSet = loadStopwordSet(language);
const idfTable = loadIdfTable(language);

// Load draft
const draftText = readFileSync(draftPath, 'utf-8');
const { termCounts: draftCounts, wordCount: draftWordCount } = extractTermsFromText(draftText, stopwordSet);

// Load competitor pages (sorted for determinism)
const pageFiles = readdirSync(pagesDir)
  .filter(f => f.endsWith('.json'))
  .sort();

const competitorPages = pageFiles.map(f => {
  const raw = JSON.parse(readFileSync(join(pagesDir, f), 'utf-8'));
  return raw.main_content_text || '';
});

const N = competitorPages.length; // number of competitor documents

// Extract term data from each competitor page
const competitorTermData = competitorPages.map(text =>
  extractTermsFromText(text, stopwordSet)
);

// Build union of all terms from draft and competitors
const allTerms = new Set(draftCounts.keys());
for (const { termCounts } of competitorTermData) {
  for (const term of termCounts.keys()) {
    allTerms.add(term);
  }
}

// For corpus-local IDF fallback: compute df per term across competitor pages
function buildCorpusDf(termDataList) {
  const dfMap = new Map();
  for (const { termCounts } of termDataList) {
    for (const term of termCounts.keys()) {
      dfMap.set(term, (dfMap.get(term) || 0) + 1);
    }
  }
  return dfMap;
}

const corpusDf = (idfTable === null && N > 0) ? buildCorpusDf(competitorTermData) : null;

// Resolve IDF for a term:
// 1. If reference table available and term present → use table value
// 2. Else if table available but term absent (n-gram, non-German) → neutral fallback
//    Use log2(N + 1) as neutral IDF (treats term as if df=1 relative to N+1 docs)
// 3. If no table → corpus-local IDF: log2(N / df); 0 when df=0 or N=0
function resolveIdf(term, df) {
  if (idfTable !== null) {
    const tableVal = idfTable[term];
    if (tableVal !== undefined) return tableVal;
    // Neutral IDF for terms not in the reference table (n-grams, non-German)
    // Use log2(N + 1) as a reasonable neutral value
    return N > 0 ? Math.log2(N + 1) : 0;
  }
  // Corpus-local fallback
  if (N === 0 || df === 0) return 0;
  return Math.log2(N / df);
}

// Build per-term scores
const results = [];
for (const term of allTerms) {
  // Draft WDF*IDF
  const draftTf = draftCounts.get(term) || 0;
  const draftWdf = computeWdf(draftTf, draftWordCount);

  // Competitor average WDF*IDF
  let competitorWdfSum = 0;
  for (const { termCounts, wordCount } of competitorTermData) {
    const tf = termCounts.get(term) || 0;
    competitorWdfSum += computeWdf(tf, wordCount);
  }
  const competitorAvgWdf = N > 0 ? competitorWdfSum / N : 0;

  // Document frequency across competitor pages (for corpus-local IDF)
  const df = corpusDf !== null ? (corpusDf.get(term) || 0) : 0;

  const idf = resolveIdf(term, df);
  const draftWdfidf = round6(draftWdf * idf);
  const competitorAvgWdfidf = round6(competitorAvgWdf * idf);
  const delta = round6(draftWdfidf - competitorAvgWdfidf);
  const absDelta = Math.abs(delta);

  let signal;
  if (absDelta < THRESHOLD) {
    signal = 'ok';
  } else if (delta < 0) {
    signal = 'increase';
  } else {
    signal = 'decrease';
  }

  results.push({ term, draft_wdfidf: draftWdfidf, competitor_avg_wdfidf: competitorAvgWdfidf, delta, signal });
}

// Sort by absolute delta descending; for equal deltas sort alphabetically for determinism
results.sort((a, b) => {
  const absDiff = Math.abs(b.delta) - Math.abs(a.delta);
  if (absDiff !== 0) return absDiff;
  return a.term.localeCompare(b.term);
});

const output = {
  meta: {
    draft: draftPath,
    pages_dir: pagesDir,
    language,
    threshold: THRESHOLD,
    competitor_count: N,
    idf_source: idfTable !== null ? 'reference' : 'corpus-local',
  },
  terms: results,
};

console.log(JSON.stringify(output, null, 2));
