#!/usr/bin/env node
// Deterministic claim extraction from draft markdown files.
// Extracts verifiable factual claims using regex/heuristic patterns across
// 6 categories: heights_distances, prices_costs, dates_years, counts,
// geographic, measurements.
//
// Usage:
//   node extract-claims.mjs --draft <path/to/draft.md> [--output path]
// Outputs JSON to stdout (or file via --output). Same inputs always produce
// byte-identical output.

import { readFileSync, writeFileSync } from 'node:fs';

// --- CLI parsing ---
const args = process.argv.slice(2);
function flag(name) {
  const idx = args.indexOf(name);
  if (idx === -1 || idx + 1 >= args.length) return undefined;
  return args[idx + 1];
}

const draftPath = flag('--draft');
const outputPath = flag('--output');

if (draftPath === undefined) {
  console.error(
    'Usage: node extract-claims.mjs --draft <path/to/draft.md> [--output path]'
  );
  process.exit(1);
}

// --- Patterns ---
// German number: 1.700 or 6.500,5 or plain 604 or 2.469
const NUM = '(?:\\d{1,3}(?:\\.\\d{3})*(?:,\\d+)?|\\d+(?:,\\d+)?)';

const CATEGORIES = [
  {
    name: 'heights_distances',
    // e.g. 2.469 Metern, 8 km, 604 Meter, 1.700 Kilometer
    pattern: new RegExp(`${NUM}\\s*(?:Metern?|Kilometern?|km|Meter[n]?|Hoehendifferenz|Hoehenmetern?)`, 'g'),
  },
  {
    name: 'prices_costs',
    // e.g. 790 NOK, 150 EUR, ab 49 Euro
    pattern: new RegExp(`(?:(?:ab|etwa|rund|ca\\.?)\\s+)?${NUM}\\s*(?:NOK|EUR|Euro|CHF|USD|Kronen)`, 'g'),
  },
  {
    name: 'dates_years',
    // e.g. gegruendet 1962, seit 2015, im Jahr 1884
    pattern: new RegExp(`(?:(?:im\\s+Jahr|seit|gegruendet|eroeffnet|gebaut|entstanden)\\s+)(\\d{4})`, 'gi'),
  },
  {
    name: 'counts',
    // e.g. ueber 550 Huetten, 28 Nationalparks, rund 500 Routen
    pattern: new RegExp(`(?:(?:ueber|rund|etwa|ca\\.?|mehr\\s+als|insgesamt)\\s+)?${NUM}\\s+(?:[A-ZÄÖÜ][a-zäöüß]+(?:en|er|e|n|s|parks?)?)`, 'g'),
  },
  {
    name: 'geographic',
    // keyword triggers + capitalized proper nouns
    pattern: /(?:zwischen|noerdlich|suedlich|oestlich|westlich|nordoestlich|nordwestlich|suedoestlich|suedwestlich)\s+(?:des\s+|der\s+|dem\s+)?(?:[A-ZÄÖÜ][a-zäöüß]+)(?:\s+(?:und|bis)\s+[A-ZÄÖÜ][a-zäöüß]+)*/g,
  },
  {
    name: 'measurements',
    // e.g. 6.500 bis 8.000 Quadratkilometer, Wassertemperaturen um 15 Grad
    pattern: new RegExp(`${NUM}(?:\\s+bis\\s+${NUM})?\\s*(?:Quadratkilometern?|Grad\\s*(?:Celsius|C)?|Liter|Tonnen|Hektar|qm|m²)`, 'g'),
  },
];

// --- Helpers ---

// Split text into sentences at . ! ? boundaries, preserving the delimiter.
// Handles German number format (1.700) by not splitting on dots between digits.
function splitSentences(text) {
  const sentences = [];
  let current = '';
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    current += ch;
    if (ch === '.' || ch === '?' || ch === '!') {
      // Don't split on dots that are part of numbers (digit.digit)
      if (ch === '.' && i > 0 && i < text.length - 1) {
        const prev = text[i - 1];
        const next = text[i + 1];
        if (prev >= '0' && prev <= '9' && next >= '0' && next <= '9') {
          continue;
        }
      }
      sentences.push(current.trim());
      current = '';
    }
  }
  if (current.trim()) {
    sentences.push(current.trim());
  }
  return sentences;
}

// Determine if a line is inside the meta table.
// Meta table starts with "| Feld | Wert |" (or similar header) and ends with "---".
function findSkipRanges(lines) {
  const ranges = [];
  let inMetaTable = false;
  let metaStart = -1;

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    // Detect start of meta table: line starting with | and containing |
    if (trimmed.startsWith('|') && trimmed.includes('Feld') && trimmed.includes('Wert')) {
      inMetaTable = true;
      metaStart = i;
    }
    // Detect end of meta table: line that is just ---
    if (inMetaTable && /^-{3,}$/.test(trimmed)) {
      ranges.push({ start: metaStart, end: i });
      inMetaTable = false;
    }
  }
  // If table never closed, skip to end
  if (inMetaTable) {
    ranges.push({ start: metaStart, end: lines.length - 1 });
  }
  return ranges;
}

function isInSkipRange(lineIdx, ranges) {
  return ranges.some(r => lineIdx >= r.start && lineIdx <= r.end);
}

// Check if text is inside an HTML comment
function isHtmlComment(line) {
  return /<!--.*?-->/.test(line) && line.trim().startsWith('<!--');
}

// Track the current section heading
function extractSection(line) {
  const match = line.match(/^#{2,3}\s+(.+)/);
  return match ? match[1].trim() : null;
}

// Find the sentence containing a match at a given position within a line
function findSentence(text, matchStr, matchIndex) {
  // Get a window of text around the match for sentence splitting
  // Walk backwards to find sentence start, forwards to find sentence end
  const windowStart = Math.max(0, matchIndex - 300);
  const windowEnd = Math.min(text.length, matchIndex + matchStr.length + 300);
  const window = text.substring(windowStart, windowEnd);
  const relativeIdx = matchIndex - windowStart;

  const sentences = splitSentences(window);
  let pos = 0;
  for (const sentence of sentences) {
    const sentenceStart = window.indexOf(sentence, pos);
    const sentenceEnd = sentenceStart + sentence.length;
    if (relativeIdx >= sentenceStart && relativeIdx < sentenceEnd) {
      return sentence;
    }
    pos = sentenceEnd;
  }
  // Fallback: return the full line
  return text.trim();
}

// --- Main extraction ---
const draftText = readFileSync(draftPath, 'utf-8');
const lines = draftText.split('\n');
const skipRanges = findSkipRanges(lines);

const claims = [];
let currentSection = null;

// Build a full-text version with line mapping for sentence extraction
// Process line by line to track sections and skip ranges
for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
  const line = lines[lineIdx];

  // Track current section
  const sectionMatch = extractSection(line);
  if (sectionMatch) {
    currentSection = sectionMatch;
  }

  // Skip meta table lines
  if (isInSkipRange(lineIdx, skipRanges)) continue;

  // Skip HTML comments
  if (isHtmlComment(line)) continue;

  // Skip heading lines themselves (don't extract claims from headings)
  if (/^#{1,6}\s+/.test(line)) continue;

  // Skip empty lines
  if (line.trim() === '') continue;

  // Run each category pattern against this line
  for (const cat of CATEGORIES) {
    // Reset regex lastIndex
    cat.pattern.lastIndex = 0;
    let match;
    while ((match = cat.pattern.exec(line)) !== null) {
      const value = match[0];
      const sentence = findSentence(line, value, match.index);
      claims.push({
        category: cat.name,
        value,
        sentence,
        line: lineIdx + 1, // 1-based
        charIndex: match.index,
        section: currentSection,
      });
    }
  }
}

// Sort by line number, then by character position for determinism
claims.sort((a, b) => {
  if (a.line !== b.line) return a.line - b.line;
  return a.charIndex - b.charIndex;
});

// Assign sequential IDs and remove charIndex (internal sort key)
const finalClaims = claims.map((c, i) => ({
  id: `c${String(i + 1).padStart(3, '0')}`,
  category: c.category,
  value: c.value,
  sentence: c.sentence,
  line: c.line,
  section: c.section,
}));

const output = {
  meta: {
    draft: draftPath,
    extracted_at: new Date().toISOString(),
    total_claims: finalClaims.length,
  },
  claims: finalClaims,
};

const jsonStr = JSON.stringify(output, null, 2);
if (outputPath) {
  writeFileSync(outputPath, jsonStr + '\n', 'utf-8');
} else {
  console.log(jsonStr);
}
