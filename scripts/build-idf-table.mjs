#!/usr/bin/env node
// Offline IDF computation script.
// Reads a plain-text or Leipzig tab-separated corpus line-by-line,
// computes document-frequency-based IDF values, and writes compact JSON to stdout.
//
// Usage:
//   node scripts/build-idf-table.mjs --corpus <path> --language <code> [--min-df 5] [--max-terms 200000]

import { createReadStream } from 'node:fs';
import { createInterface } from 'node:readline';
import { existsSync } from 'node:fs';
import { basename } from 'node:path';

import { tokenize, removeStopwords, loadStopwordSet } from '../src/utils/tokenizer.mjs';

// --- Argument parsing ---

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--corpus')    { args.corpus   = argv[i + 1]; i++; }
    else if (argv[i] === '--language') { args.language = argv[i + 1]; i++; }
    else if (argv[i] === '--min-df')   { args.minDf    = argv[i + 1]; i++; }
    else if (argv[i] === '--max-terms'){ args.maxTerms = argv[i + 1]; i++; }
  }
  return args;
}

function printUsage() {
  process.stderr.write(
    'Usage: node scripts/build-idf-table.mjs --corpus <path> --language <code> [--min-df 5] [--max-terms 200000]\n'
  );
}

// --- IDF computation (exported for testing) ---

/**
 * Compute IDF table from an async iterable of lines.
 * Returns { meta, idf } output object.
 *
 * @param {AsyncIterable<string>} lines
 * @param {{ language: string, corpusName: string, minDf: number, maxTerms: number }} opts
 * @returns {Promise<{ meta: object, idf: object }>}
 */
export async function computeIdf(lines, { language, corpusName, minDf, maxTerms }) {
  const stopwordSet = loadStopwordSet(language);
  const dfMap = new Map();
  let N = 0;

  for await (const rawLine of lines) {
    // Strip Leipzig tab-index prefix: lines are "index\tsentence"
    const line = rawLine.includes('\t') ? rawLine.slice(rawLine.indexOf('\t') + 1) : rawLine;

    const tokens = tokenize(line);
    const filtered = removeStopwords(tokens, stopwordSet);
    if (filtered.length === 0) continue;

    // Deduplicate within the line so each term contributes at most 1 to DF
    const unique = new Set(filtered);
    N++;
    for (const term of unique) {
      dfMap.set(term, (dfMap.get(term) || 0) + 1);
    }
  }

  // Filter by min-df; also drop pure-digit tokens (years, numbers) since they
  // cause V8 to hoist integer-indexed keys before alphabetic ones in Object.keys(),
  // breaking the alphabetical-sort guarantee for the idf object.
  const pureDigit = /^[0-9]+$/;
  const eligible = [];
  for (const [term, df] of dfMap) {
    if (df >= minDf && pureDigit.test(term) === false) {
      eligible.push([term, df]);
    }
  }

  // Sort: df descending, then alphabetically for determinism
  eligible.sort((a, b) => {
    if (b[1] === a[1]) return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0;
    return b[1] - a[1];
  });

  // Truncate
  const truncated = eligible.slice(0, maxTerms);

  // Build idf object with alphabetically sorted keys for determinism
  const sortedByKey = truncated.slice().sort((a, b) => a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0);
  const idf = {};
  for (const [term, df] of sortedByKey) {
    // IDF formula: log2(N / df), rounded to 3 decimal places
    idf[term] = Math.round(Math.log2(N / df) * 1000) / 1000;
  }

  return {
    meta: {
      corpus: corpusName,
      language,
      total_documents: N,
      terms_included: sortedByKey.length,
      min_df: minDf,
    },
    idf,
  };
}

// --- Main entry point ---

async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (args.corpus === undefined || args.language === undefined) {
    printUsage();
    process.exit(1);
  }

  if (existsSync(args.corpus) === false) {
    process.stderr.write(`Error: corpus file not found: ${args.corpus}\n`);
    printUsage();
    process.exit(1);
  }

  const minDf    = args.minDf    === undefined ? 5      : parseInt(args.minDf, 10);
  const maxTerms = args.maxTerms === undefined ? 200000 : parseInt(args.maxTerms, 10);

  const corpusName = basename(args.corpus);

  const fileStream = createReadStream(args.corpus, { encoding: 'utf8' });
  const rl = createInterface({ input: fileStream, crlfDelay: Infinity });

  const output = await computeIdf(rl, {
    language: args.language,
    corpusName,
    minDf,
    maxTerms,
  });

  process.stdout.write(JSON.stringify(output));
}

// Only run main when executed directly (not when imported by tests)
if (process.argv[1] === new URL(import.meta.url).pathname) {
  main().catch(err => {
    process.stderr.write(`${err.message}\n`);
    process.exit(1);
  });
}
