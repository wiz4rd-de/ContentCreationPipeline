#!/usr/bin/env node
// Deterministic content topic analyzer.
// Extracts n-gram term frequencies (TF-IDF proxy), computes section weight
// analysis, and clusters similar headings using Jaccard overlap.
//
// Usage: node analyze-content-topics.mjs --pages-dir <pages/> --seed <keyword> [--language de]
// Outputs JSON to stdout. Same inputs always produce byte-identical output.

import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- CLI parsing ---
const args = process.argv.slice(2);
function flag(name) {
  const idx = args.indexOf(name);
  if (idx === -1 || idx + 1 >= args.length) return undefined;
  return args[idx + 1];
}

const pagesDir = flag('--pages-dir');
const seed = flag('--seed');
const language = flag('--language') || 'de';

if (pagesDir === undefined || seed === undefined) {
  console.error('Usage: node analyze-content-topics.mjs --pages-dir <pages/> --seed <keyword> [--language de]');
  process.exit(1);
}

// --- Load stopwords ---
const stopwordsPath = join(__dirname, '..', 'utils', 'stopwords.json');
const stopwordsData = JSON.parse(readFileSync(stopwordsPath, 'utf-8'));
const stopwordSet = new Set([
  ...(stopwordsData[language] || []),
  ...(language === 'de' ? (stopwordsData.en || []) : []),
]);

// --- Load page files (sorted for determinism) ---
const pageFiles = readdirSync(pagesDir)
  .filter(f => f.endsWith('.json'))
  .sort();

if (pageFiles.length === 0) {
  const emptyOutput = {
    proof_keywords: [],
    entity_candidates: [],
    section_weights: [],
    content_format_signals: {
      pages_with_numbered_lists: 0,
      pages_with_faq: 0,
      pages_with_tables: 0,
      avg_h2_count: 0,
      dominant_pattern: null,
    },
  };
  console.log(JSON.stringify(emptyOutput, null, 2));
  process.exit(0);
}

// --- Page quality filter ---
// Exclude blocked/error/thin pages from all analysis to prevent noise in proof keywords,
// section weights, and content format signals.
const BLOCK_HEADING_RE_ACT = /why have i been blocked|access denied|403 forbidden|please verify|checking your browser|just a moment|enable javascript and cookies|attention required/i;
const MIN_WORD_COUNT_ACT = 200;

function countWordsRaw(text) {
  return text.split(/\s+/).filter(Boolean).length;
}

function isBlockedPage(mainText, headings) {
  if (mainText.length === 0) return 'missing main_content_text';
  const wc = countWordsRaw(mainText);
  if (wc < MIN_WORD_COUNT_ACT) return `too few words (${wc} < ${MIN_WORD_COUNT_ACT})`;
  const blocked = headings.find(h => BLOCK_HEADING_RE_ACT.test(h.text || ''));
  if (blocked) return `block/error heading: "${blocked.text}"`;
  return null;
}

// --- Load all pages ---
const pages = pageFiles.map(f => {
  const raw = JSON.parse(readFileSync(join(pagesDir, f), 'utf-8'));
  let domain = '';
  try { domain = new URL(raw.url).hostname; } catch { /* skip */ }
  return {
    file: f,
    url: raw.url || '',
    domain,
    mainText: raw.main_content_text || '',
    headings: raw.headings || [],
    signals: raw.html_signals || {},
  };
}).filter(page => {
  const reason = isBlockedPage(page.mainText, page.headings);
  if (reason !== null) {
    process.stderr.write(`Skipping ${page.domain || page.file}: ${reason}\n`);
    return false;
  }
  return true;
});

const totalPages = pages.length;

// --- Tokenizer ---
// Lowercase, remove punctuation (keep umlauts and word chars), split on whitespace.
function tokenize(text) {
  // Replace punctuation with spaces, keeping letters (including umlauts), digits
  const cleaned = text
    .toLowerCase()
    .replace(/[^a-z0-9\u00e4\u00f6\u00fc\u00df\u00e0-\u00ff]+/g, ' ')
    .trim();
  if (cleaned.length === 0) return [];
  return cleaned.split(/\s+/).filter(w => w.length > 1);
}

function removeStopwords(tokens) {
  return tokens.filter(t => stopwordSet.has(t) === false);
}

// --- N-gram extraction ---
function extractNgrams(tokens, n) {
  const ngrams = [];
  for (let i = 0; i <= tokens.length - n; i++) {
    ngrams.push(tokens.slice(i, i + n).join(' '));
  }
  return ngrams;
}

function countTerms(termList) {
  const counts = new Map();
  for (const t of termList) {
    counts.set(t, (counts.get(t) || 0) + 1);
  }
  return counts;
}

// Check if an n-gram is all stopwords (should be filtered out)
function isAllStopwords(ngram) {
  const words = ngram.split(' ');
  return words.every(w => stopwordSet.has(w));
}

// --- Term extraction per page ---
// Returns { termCounts: Map<term, count>, domain: string }
// Unigrams: remove stopwords. Bigrams/trigrams: keep stopwords within phrases
// but filter out n-grams where ALL tokens are stopwords.
function extractPageTerms(page) {
  const allTokens = tokenize(page.mainText);
  const filteredTokens = removeStopwords(allTokens);
  const allTerms = [
    ...extractNgrams(filteredTokens, 1),
    ...extractNgrams(allTokens, 2).filter(ng => isAllStopwords(ng) === false),
    ...extractNgrams(allTokens, 3).filter(ng => isAllStopwords(ng) === false),
  ];
  return { termCounts: countTerms(allTerms), domain: page.domain };
}

const pageTermData = pages.map(p => extractPageTerms(p));

// --- Document frequency ---
// df[term] = number of pages containing the term
// termTotalTf[term] = sum of tf across all pages
const dfMap = new Map();
const tfSumMap = new Map();
const termPagesMap = new Map(); // term -> sorted list of domains

for (const ptd of pageTermData) {
  for (const [term, count] of ptd.termCounts) {
    dfMap.set(term, (dfMap.get(term) || 0) + 1);
    tfSumMap.set(term, (tfSumMap.get(term) || 0) + count);
    if (termPagesMap.has(term) === false) {
      termPagesMap.set(term, []);
    }
    termPagesMap.get(term).push(ptd.domain);
  }
}

// --- Proof keywords: ranked by DF (most common across pages) ---
// Filter: DF >= 2 (appears in at least 2 pages), exclude the seed keyword itself
const seedLower = seed.toLowerCase();
const proofCandidates = [];
for (const [term, df] of dfMap) {
  if (df < 2) continue;
  if (term === seedLower) continue;
  const avgTf = Math.round((tfSumMap.get(term) / df) * 10) / 10;
  proofCandidates.push({
    term,
    document_frequency: df,
    total_pages: totalPages,
    avg_tf: avgTf,
  });
}

// Sort by DF desc, then by avg_tf desc, then alphabetically for determinism
proofCandidates.sort((a, b) => {
  if (b.document_frequency === a.document_frequency) {
    if (b.avg_tf === a.avg_tf) {
      return a.term.localeCompare(b.term);
    }
    return b.avg_tf - a.avg_tf;
  }
  return b.document_frequency - a.document_frequency;
});

// Top 50 proof keywords
const proof_keywords = proofCandidates.slice(0, 50);

// --- Entity candidates: single-word terms with high DF ---
// Entities are typically proper nouns or specific terms (1-grams) that appear in many pages
const entityCandidates = [];
for (const [term, df] of dfMap) {
  if (df < 2) continue;
  if (term === seedLower) continue;
  // Only 1-grams for entity candidates (no spaces)
  if (term.includes(' ')) continue;
  // Must be at least 3 chars to be meaningful
  if (term.length < 3) continue;

  const pageDomains = [...termPagesMap.get(term)].sort();
  entityCandidates.push({
    term,
    document_frequency: df,
    pages: pageDomains,
  });
}

// Sort by DF desc, then alphabetically
entityCandidates.sort((a, b) => {
  if (b.document_frequency === a.document_frequency) {
    return a.term.localeCompare(b.term);
  }
  return b.document_frequency - a.document_frequency;
});

// Top 30 entity candidates
const entity_candidates = entityCandidates.slice(0, 30);

// --- Section weight analysis ---
// Split main_content_text into sections by heading positions (same approach as analyze-page-structure)
function splitSections(mainText, headings) {
  if (headings.length === 0) {
    return [{ heading: '', level: 0, text: mainText }];
  }

  const sections = [];
  const positions = [];
  for (const h of headings) {
    const idx = mainText.indexOf(h.text);
    if (idx >= 0) {
      positions.push({ heading: h.text, level: h.level, pos: idx });
    }
  }
  positions.sort((a, b) => a.pos - b.pos);

  // Intro
  if (positions.length > 0 && positions[0].pos > 0) {
    const introText = mainText.slice(0, positions[0].pos).trim();
    if (introText.length > 0) {
      sections.push({ heading: '', level: 0, text: introText });
    }
  }

  for (let i = 0; i < positions.length; i++) {
    const start = positions[i].pos + positions[i].heading.length;
    const end = (i + 1 < positions.length) ? positions[i + 1].pos : mainText.length;
    const sectionText = mainText.slice(start, end).trim();
    sections.push({
      heading: positions[i].heading,
      level: positions[i].level,
      text: sectionText,
    });
  }

  return sections;
}

function countWords(text) {
  return text.split(/\s+/).filter(Boolean).length;
}

// Normalize heading: lowercase, strip numbers and punctuation, trim
function normalizeHeading(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z\u00e4\u00f6\u00fc\u00df\u00e0-\u00ff\s]+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// Jaccard similarity on word sets
function jaccardSimilarity(a, b) {
  const setA = new Set(a.split(/\s+/).filter(Boolean));
  const setB = new Set(b.split(/\s+/).filter(Boolean));
  if (setA.size === 0 && setB.size === 0) return 1;
  if (setA.size === 0 || setB.size === 0) return 0;
  let intersection = 0;
  for (const w of setA) {
    if (setB.has(w)) intersection++;
  }
  const union = setA.size + setB.size - intersection;
  return union === 0 ? 0 : intersection / union;
}

// Collect all sections across all pages with their word counts and total page word counts
const allSectionEntries = [];

for (const page of pages) {
  const totalWc = countWords(page.mainText);
  if (totalWc === 0) continue;
  const sections = splitSections(page.mainText, page.headings);
  for (const sec of sections) {
    // Skip intro sections (no heading)
    if (sec.heading === '') continue;
    // Only H2 headings for section weight analysis
    if (sec.level > 2) continue;
    const wc = countWords(sec.text);
    const pct = (wc / totalWc) * 100;
    allSectionEntries.push({
      heading: sec.heading,
      normalizedHeading: normalizeHeading(sec.heading),
      wordCount: wc,
      contentPercentage: pct,
      domain: page.domain,
    });
  }
}

// Cluster headings by Jaccard similarity >= 0.5
// Greedy clustering: assign each heading to the first matching cluster
const clusters = []; // { normalized: string, headings: Set<string>, entries: [] }

for (const entry of allSectionEntries) {
  let found = false;
  for (const cluster of clusters) {
    if (jaccardSimilarity(cluster.normalized, entry.normalizedHeading) >= 0.5) {
      cluster.headings.add(entry.heading);
      cluster.entries.push(entry);
      found = true;
      break;
    }
  }
  if (found === false) {
    clusters.push({
      normalized: entry.normalizedHeading,
      headings: new Set([entry.heading]),
      entries: [entry],
    });
  }
}

// Build section_weights from clusters
const section_weights = clusters.map(cluster => {
  const occurrence = cluster.entries.length;
  const totalWordCount = cluster.entries.reduce((s, e) => s + e.wordCount, 0);
  const avgWordCount = Math.round(totalWordCount / occurrence);
  const totalPct = cluster.entries.reduce((s, e) => s + e.contentPercentage, 0);
  const avgPct = Math.round((totalPct / occurrence) * 10) / 10;

  let weight = 'low';
  if (avgPct > 25) weight = 'high';
  else if (avgPct >= 10) weight = 'medium';

  // Sort sample headings for determinism
  const sampleHeadings = [...cluster.headings].sort();

  return {
    heading_cluster: cluster.normalized,
    sample_headings: sampleHeadings,
    occurrence,
    avg_word_count: avgWordCount,
    avg_content_percentage: avgPct,
    weight,
  };
});

// Sort section_weights by occurrence desc, then heading_cluster alphabetically
section_weights.sort((a, b) => {
  if (b.occurrence === a.occurrence) {
    return a.heading_cluster.localeCompare(b.heading_cluster);
  }
  return b.occurrence - a.occurrence;
});

// --- Content format signals ---
const FAQ_HEADING_RE = /\b(faq|fragen|haeufig|frequently\s+asked|h.ufig)\b/i;

let pagesWithNumberedLists = 0;
let pagesWithFaq = 0;
let pagesWithTables = 0;
let totalH2Count = 0;

for (const page of pages) {
  const signals = page.signals;
  if (signals.ordered_lists > 0) pagesWithNumberedLists++;
  if (signals.tables > 0) pagesWithTables++;

  // FAQ detection: heading match or html_signals
  const hasFaqHeading = page.headings.some(h => FAQ_HEADING_RE.test(h.text));
  if (hasFaqHeading || signals.faq_sections > 0) pagesWithFaq++;

  // Count H2 headings
  const h2Count = page.headings.filter(h => h.level === 2).length;
  totalH2Count += h2Count;
}

const avgH2Count = Math.round((totalH2Count / totalPages) * 10) / 10;

const content_format_signals = {
  pages_with_numbered_lists: pagesWithNumberedLists,
  pages_with_faq: pagesWithFaq,
  pages_with_tables: pagesWithTables,
  avg_h2_count: avgH2Count,
  dominant_pattern: null,
};

// --- Output ---
const output = {
  proof_keywords,
  entity_candidates,
  section_weights,
  content_format_signals,
};

console.log(JSON.stringify(output, null, 2));
