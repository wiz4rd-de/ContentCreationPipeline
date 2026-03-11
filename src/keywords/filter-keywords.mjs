#!/usr/bin/env node
// Deterministic keyword filter: applies blocklist, brand, and foreign-language
// filtering to processed keyword data. Keywords are tagged with filter_status
// and filter_reason (not deleted) to preserve the audit trail.
//
// Also computes FAQ prioritization by scoring PAA questions against keyword
// overlaps.
//
// Usage:
//   node filter-keywords.mjs \
//     --keywords <keywords-processed.json> \
//     --serp <serp-processed.json> \
//     --seed <keyword> \
//     [--blocklist <blocklist.json>] \
//     [--brands "brand1,brand2,brand3"]

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- Parse arguments --------------------------------------------------------

const args = process.argv.slice(2);

function flagValue(name) {
  const idx = args.indexOf(name);
  if (idx === -1) return undefined;
  return args[idx + 1];
}

const keywordsFile = flagValue('--keywords');
const serpFile = flagValue('--serp');
const seedKeyword = flagValue('--seed');
const blocklistFile = flagValue('--blocklist');
const brandsRaw = flagValue('--brands');

if (keywordsFile === undefined || serpFile === undefined || seedKeyword === undefined) {
  console.error(
    'Usage: node filter-keywords.mjs --keywords <file> --serp <file> --seed <keyword> ' +
    '[--blocklist <file>] [--brands "brand1,brand2,brand3"]',
  );
  process.exit(1);
}

// --- Helpers ----------------------------------------------------------------

function readJSON(path) {
  return JSON.parse(readFileSync(path, 'utf-8'));
}

// Foreign-language heuristic: detect non-Latin characters.
// Allows basic Latin, extended Latin, Latin Extended Additional, whitespace,
// hyphens, apostrophes, digits, and common punctuation.
const FOREIGN_RE = /[^\x20-\u024F\u1E00-\u1EFF\s\-'0-9.,;:?&()/"]/;

function isForeignLanguage(keyword) {
  return FOREIGN_RE.test(keyword);
}

// --- Read inputs ------------------------------------------------------------

const keywordsData = readJSON(keywordsFile);
const serpData = readJSON(serpFile);
const seed = seedKeyword.trim();

// Load blocklist: custom or default
const defaultBlocklistPath = join(__dirname, 'blocklist-default.json');
const blocklist = readJSON(blocklistFile || defaultBlocklistPath);

// Parse brands list
const brandList = brandsRaw
  ? brandsRaw.split(',').map(b => b.trim().toLowerCase()).filter(Boolean)
  : [];

// --- Build flat blocklist lookup --------------------------------------------
// Map each term to its category for efficient lookup and reason tagging.

const blocklistEntries = []; // { term: string, category: string }
for (const [category, terms] of Object.entries(blocklist)) {
  if (Array.isArray(terms)) {
    for (const term of terms) {
      blocklistEntries.push({ term: term.toLowerCase(), category });
    }
  }
}

// Sort blocklist entries for deterministic first-match behavior
blocklistEntries.sort((a, b) => {
  if (a.category < b.category) return -1;
  if (a.category > b.category) return 1;
  if (a.term < b.term) return -1;
  if (a.term > b.term) return 1;
  return 0;
});

// --- Map blocklist categories to filter_reason ------------------------------
// "ethics" -> "ethics", "booking_portals" -> "off_topic", "spam_patterns" -> "off_topic"

function categoryToReason(category) {
  if (category === 'ethics') return 'ethics';
  return 'off_topic';
}

// --- Filter keywords in clusters --------------------------------------------

const removalSummary = { ethics: 0, brand: 0, off_topic: 0, foreign_language: 0 };

function filterKeyword(kw) {
  const kwLower = kw.keyword.toLowerCase();

  // 1. Check blocklist (case-insensitive substring match)
  for (const entry of blocklistEntries) {
    if (kwLower.includes(entry.term)) {
      const reason = categoryToReason(entry.category);
      removalSummary[reason]++;
      return { filter_status: 'removed', filter_reason: reason };
    }
  }

  // 2. Check brands (case-insensitive substring match)
  for (const brand of brandList) {
    if (kwLower.includes(brand)) {
      removalSummary.brand++;
      return { filter_status: 'removed', filter_reason: 'brand' };
    }
  }

  // 3. Foreign-language heuristic
  if (isForeignLanguage(kw.keyword)) {
    removalSummary.foreign_language++;
    return { filter_status: 'removed', filter_reason: 'foreign_language' };
  }

  return { filter_status: 'keep', filter_reason: null };
}

// Deep-clone clusters and tag each keyword
const clusters = [];
let totalKeywords = 0;
let removedCount = 0;

if (Array.isArray(keywordsData.clusters)) {
  for (const cluster of keywordsData.clusters) {
    const taggedKeywords = [];
    if (Array.isArray(cluster.keywords)) {
      for (const kw of cluster.keywords) {
        totalKeywords++;
        const { filter_status, filter_reason } = filterKeyword(kw);
        if (filter_status === 'removed') removedCount++;
        taggedKeywords.push({
          ...kw,
          filter_status,
          filter_reason,
        });
      }
    }
    clusters.push({
      cluster_keyword: cluster.cluster_keyword,
      cluster_label: cluster.cluster_label ?? null,
      strategic_notes: cluster.strategic_notes ?? null,
      keyword_count: cluster.keyword_count ?? taggedKeywords.length,
      keywords: taggedKeywords,
      cluster_opportunity: cluster.cluster_opportunity ?? null,
    });
  }
}

const filteredKeywords = totalKeywords - removedCount;

// --- FAQ prioritization -----------------------------------------------------
// Score PAA questions by counting keyword overlaps (case-insensitive).
// Only consider "keep" keywords for scoring.

const keepKeywords = [];
for (const cluster of clusters) {
  for (const kw of cluster.keywords) {
    if (kw.filter_status === 'keep') {
      keepKeywords.push(kw.keyword.toLowerCase());
    }
  }
}

// Tokenize keywords into individual words for overlap matching
const keepTokens = new Set();
for (const kw of keepKeywords) {
  for (const token of kw.split(/\s+/)) {
    if (token.length > 0) keepTokens.add(token);
  }
}

// Extract PAA questions from serp data
const paaRaw = serpData.serp_features?.people_also_ask;
const paaQuestions = [];
if (Array.isArray(paaRaw)) {
  for (const q of paaRaw) {
    if (typeof q === 'string' && q.length > 0) {
      paaQuestions.push({ question: q, answer: null, url: null, domain: null });
    } else if (q && typeof q === 'object' && typeof q.question === 'string' && q.question.length > 0) {
      paaQuestions.push({
        question: q.question,
        answer: q.answer || null,
        url: q.url || null,
        domain: q.domain || null,
      });
    }
  }
}

// Score each question by keyword token overlaps
const scoredFaqs = paaQuestions.map(paa => {
  const questionLower = paa.question.toLowerCase();
  // Strip punctuation from tokens for matching (e.g. "Thailand?" -> "thailand")
  const questionTokens = questionLower.split(/\s+/)
    .map(t => t.replace(/[^a-z\u00e0-\u024f\u1e00-\u1eff0-9\-]/g, ''))
    .filter(t => t.length > 0);
  let score = 0;
  for (const token of questionTokens) {
    if (keepTokens.has(token)) score++;
  }
  return { question: paa.question, relevance_score: score };
});

// Sort by relevance_score descending, then alphabetical for determinism
scoredFaqs.sort((a, b) => {
  if (b.relevance_score !== a.relevance_score) return b.relevance_score - a.relevance_score;
  return a.question.localeCompare(b.question);
});

// Assign priority tiers: top 30% = pflicht, 30-70% = empfohlen, bottom 30% = optional
function assignPriority(index, total) {
  if (total === 0) return 'optional';
  const position = index / total;
  if (position < 0.3) return 'pflicht';
  if (position < 0.7) return 'empfohlen';
  return 'optional';
}

const faqSelection = scoredFaqs.map((faq, idx) => ({
  question: faq.question,
  priority: assignPriority(idx, scoredFaqs.length),
  relevance_score: faq.relevance_score,
}));

// --- Build output -----------------------------------------------------------

const output = {
  seed_keyword: seed,
  total_keywords: totalKeywords,
  filtered_keywords: filteredKeywords,
  removed_count: removedCount,
  removal_summary: {
    ethics: removalSummary.ethics,
    brand: removalSummary.brand,
    off_topic: removalSummary.off_topic,
    foreign_language: removalSummary.foreign_language,
  },
  clusters,
  faq_selection: faqSelection,
};

console.log(JSON.stringify(output, null, 2));
