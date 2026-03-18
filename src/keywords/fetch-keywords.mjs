#!/usr/bin/env node
// Calls DataForSEO related_keywords and keyword_suggestions endpoints.
// Saves raw responses as audit trail, then invokes merge-keywords.mjs
// to produce a deduplicated keyword list.
//
// Usage: node fetch-keywords.mjs <seed-keyword> --market <cc> --language <lc> --outdir <dir> [--limit N]
//
// Requires api.env with DATAFORSEO_AUTH and DATAFORSEO_BASE.

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { loadEnv } from '../utils/load-api-config.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- Parse arguments ---
const args = process.argv.slice(2);

function flagValue(name, fallback) {
  const idx = args.indexOf(name);
  return idx !== -1 ? args[idx + 1] : fallback;
}

const seedKeyword = args.find(a => !a.startsWith('--'));
const market = flagValue('--market', undefined);
const language = flagValue('--language', undefined);
const outdir = flagValue('--outdir', undefined);
const limit = parseInt(flagValue('--limit', '50'), 10);

if (!seedKeyword || !market || !language || !outdir) {
  console.error('Usage: node fetch-keywords.mjs <seed-keyword> --market <cc> --language <lc> --outdir <dir> [--limit N]');
  process.exit(1);
}

// --- Load API credentials ---
const envPath = join(__dirname, '..', '..', 'api.env');
const { auth, base } = loadEnv(envPath);

// --- Resolve location code ---
const codes = JSON.parse(readFileSync(join(__dirname, '..', 'utils', 'location-codes.json'), 'utf-8'));
const locationCode = codes[market.toLowerCase()];
if (locationCode === undefined) {
  console.error(`Unknown market: "${market}". Available: ${Object.keys(codes).join(', ')}`);
  process.exit(1);
}

// --- Ensure output directory exists ---
mkdirSync(outdir, { recursive: true });

// --- API call helper ---
async function callEndpoint(path, body) {
  const url = `${base}/${path}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Basic ${auth}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(30000),
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

// --- Call both endpoints ---
const requestBody = [{
  keyword: seedKeyword,
  language_code: language,
  location_code: locationCode,
  limit,
}];

console.error(`Fetching related keywords for "${seedKeyword}" (market=${market}, lang=${language}, limit=${limit})...`);

const [relatedResponse, suggestionsResponse] = await Promise.all([
  callEndpoint('dataforseo_labs/google/related_keywords/live', requestBody),
  callEndpoint('dataforseo_labs/google/keyword_suggestions/live', requestBody),
]);

// --- Save raw responses ---
const relatedPath = join(outdir, 'keywords-related-raw.json');
const suggestionsPath = join(outdir, 'keywords-suggestions-raw.json');

writeFileSync(relatedPath, JSON.stringify(relatedResponse, null, 2));
writeFileSync(suggestionsPath, JSON.stringify(suggestionsResponse, null, 2));

console.error(`Saved: ${relatedPath}`);
console.error(`Saved: ${suggestionsPath}`);

// --- Invoke merge-keywords.mjs for deterministic processing ---
import { execFileSync } from 'node:child_process';

const mergeScript = join(__dirname, 'merge-keywords.mjs');
const mergedOutput = execFileSync('node', [
  mergeScript,
  '--related', relatedPath,
  '--suggestions', suggestionsPath,
  '--seed', seedKeyword,
], { encoding: 'utf-8' });

const expandedPath = join(outdir, 'keywords-expanded.json');
writeFileSync(expandedPath, mergedOutput);
console.error(`Saved: ${expandedPath}`);

// Output to stdout as well for pipeline chaining
console.log(mergedOutput);
