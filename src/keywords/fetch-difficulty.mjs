#!/usr/bin/env node
// Calls DataForSEO keyword_difficulty/live endpoint for an expanded keyword list.
// Saves raw response as audit trail, then invokes merge-difficulty.mjs
// to merge KD values into keyword records.
//
// Usage: node fetch-difficulty.mjs --expanded <file> --language <lc> --market <cc> --outdir <dir>
//
// Requires api.env with DATAFORSEO_AUTH and DATAFORSEO_BASE.

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- Parse arguments ---
const args = process.argv.slice(2);

function flagValue(name, fallback) {
  const idx = args.indexOf(name);
  return idx !== -1 ? args[idx + 1] : fallback;
}

const expandedFile = flagValue('--expanded', undefined);
const language = flagValue('--language', undefined);
const market = flagValue('--market', undefined);
const outdir = flagValue('--outdir', undefined);

if (!expandedFile || !language || !market || !outdir) {
  console.error('Usage: node fetch-difficulty.mjs --expanded <file> --language <lc> --market <cc> --outdir <dir>');
  process.exit(1);
}

// --- Load API credentials ---
const envPath = join(__dirname, '..', '..', 'api.env');
const envContent = readFileSync(envPath, 'utf-8');
const env = {};
for (const line of envContent.split('\n')) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('#')) continue;
  const eqIdx = trimmed.indexOf('=');
  if (eqIdx === -1) continue;
  env[trimmed.slice(0, eqIdx)] = trimmed.slice(eqIdx + 1);
}

const auth = env.DATAFORSEO_AUTH;
const base = env.DATAFORSEO_BASE;
if (!auth || !base) {
  console.error('Error: DATAFORSEO_AUTH and DATAFORSEO_BASE must be set in api.env');
  process.exit(1);
}

// --- Resolve location code ---
const codes = JSON.parse(readFileSync(join(__dirname, '..', 'utils', 'location-codes.json'), 'utf-8'));
const locationCode = codes[market.toLowerCase()];
if (locationCode === undefined) {
  console.error(`Unknown market: "${market}". Available: ${Object.keys(codes).join(', ')}`);
  process.exit(1);
}

// --- Load expanded keywords ---
const expanded = JSON.parse(readFileSync(expandedFile, 'utf-8'));
const keywords = expanded.keywords.map(kw => kw.keyword);

if (keywords.length === 0) {
  console.error('No keywords found in expanded file.');
  process.exit(1);
}

// API accepts max 1000 keywords per request
if (keywords.length > 1000) {
  console.error(`Warning: ${keywords.length} keywords exceeds API limit of 1000. Truncating to first 1000.`);
  keywords.length = 1000;
}

// --- Ensure output directory exists ---
mkdirSync(outdir, { recursive: true });

// --- Call keyword_difficulty endpoint ---
const url = `${base}/dataforseo_labs/google/keyword_difficulty/live`;
const requestBody = [{
  keywords,
  language_code: language,
  location_code: locationCode,
}];

console.error(`Fetching keyword difficulty for ${keywords.length} keywords (market=${market}, lang=${language})...`);

const res = await fetch(url, {
  method: 'POST',
  headers: {
    'Authorization': `Basic ${auth}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(requestBody),
  signal: AbortSignal.timeout(30000),
});

if (!res.ok) {
  throw new Error(`API error ${res.status}: ${await res.text()}`);
}

const difficultyResponse = await res.json();

// --- Save raw response ---
const rawPath = join(outdir, 'keywords-difficulty-raw.json');
writeFileSync(rawPath, JSON.stringify(difficultyResponse, null, 2));
console.error(`Saved: ${rawPath}`);

// --- Invoke merge-difficulty.mjs for deterministic processing ---
const mergeScript = join(__dirname, 'merge-difficulty.mjs');
const mergedOutput = execFileSync('node', [
  mergeScript,
  '--expanded', expandedFile,
  '--difficulty', rawPath,
], { encoding: 'utf-8' });

const mergedPath = join(outdir, 'keywords-expanded.json');
writeFileSync(mergedPath, mergedOutput);
console.error(`Updated: ${mergedPath}`);

// Output to stdout for pipeline chaining
console.log(mergedOutput);
