#!/usr/bin/env node
// Calls DataForSEO related_keywords and keyword_suggestions endpoints.
// Saves raw responses as audit trail, then invokes merge-keywords.mjs
// to produce a deduplicated keyword list.
//
// Usage: node fetch-keywords.mjs <seed-keyword> --market <cc> --language <lc> --outdir <dir> [--limit N]
//
// Requires api.env with DATAFORSEO_AUTH and DATAFORSEO_BASE.

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { loadEnv } from '../utils/load-api-config.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- Pure functions (exported for testing) ---

/**
 * Exponential backoff calculator.
 * @param {number} attempt - zero-based attempt number
 * @param {{ initialDelay: number, factor: number, maxDelay: number }} opts
 * @returns {number} delay in milliseconds
 */
function calculateBackoff(attempt, opts) {
  const { initialDelay, factor, maxDelay } = opts;
  const delay = Math.min(initialDelay * Math.pow(factor, attempt), maxDelay);
  return delay;
}

// Backoff constants: 1s initial, 2x factor, 8s max (3 retries: 1s, 2s, 4s)
// Chosen smaller than fetch-serp (5s/1.5x/30s) because keywords endpoints
// are synchronous live calls, not async tasks — failures are expected to
// resolve faster.
const RETRY_INITIAL_DELAY = 1000;
const RETRY_FACTOR = 2;
const RETRY_MAX_DELAY = 8000;
const RETRY_MAX_ATTEMPTS = 3; // 3 retries = 4 total attempts

/**
 * Call a DataForSEO endpoint with retry logic and exponential backoff.
 * Retries on: network errors (TypeError), HTTP 5xx, and timeout (AbortError).
 * Does NOT retry on: HTTP 4xx (permanent client errors).
 * @param {string} url - full URL to POST
 * @param {object} body - request body (will be JSON-serialised)
 * @param {string} auth - Basic auth token
 * @param {string} label - human-readable label for log messages
 * @param {Function} [fetchFn=fetch] - fetch implementation (injectable for testing)
 * @returns {Promise<object>} parsed JSON response
 */
async function callEndpoint(url, body, auth, label, fetchFn = fetch) {
  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  let lastError;
  for (let attempt = 0; attempt <= RETRY_MAX_ATTEMPTS; attempt++) {
    if (attempt > 0) {
      const delay = calculateBackoff(attempt - 1, {
        initialDelay: RETRY_INITIAL_DELAY,
        factor: RETRY_FACTOR,
        maxDelay: RETRY_MAX_DELAY,
      });
      console.error(`Retry ${attempt}/${RETRY_MAX_ATTEMPTS} for ${label} after ${(delay / 1000).toFixed(1)}s...`);
      await sleep(delay);
    }

    let res;
    try {
      res = await fetchFn(url, {
        method: 'POST',
        headers: {
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(30000),
      });
    } catch (err) {
      // Network error (TypeError) or timeout (AbortError) — both are retriable
      lastError = err;
      if (attempt < RETRY_MAX_ATTEMPTS) {
        console.error(`Request failed for ${label} (attempt ${attempt + 1}): ${err.message}`);
        continue;
      }
      throw err;
    }

    // HTTP 4xx = permanent client error, do not retry
    if (res.status >= 400 && res.status < 500) {
      throw new Error(`API error ${res.status}: ${await res.text()}`);
    }

    // HTTP 5xx = transient server error, retry
    if (res.status >= 500) {
      const text = await res.text();
      lastError = new Error(`API error ${res.status}: ${text}`);
      if (attempt < RETRY_MAX_ATTEMPTS) {
        console.error(`Server error for ${label} (attempt ${attempt + 1}): ${res.status}`);
        continue;
      }
      throw lastError;
    }

    return res.json();
  }

  // Should not reach here, but guard anyway
  throw lastError;
}

// --- Export pure functions for testing ---
export { calculateBackoff, callEndpoint };

// --- Main execution guard ---
// Only run main logic when executed directly (not when imported as a module)
const isMain = process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/'));
if (isMain) {
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

  const requestBody = [{
    keyword: seedKeyword,
    language_code: language,
    location_code: locationCode,
    limit,
  }];

  console.error(`Fetching related keywords for "${seedKeyword}" (market=${market}, lang=${language}, limit=${limit})...`);

  // --- Call both endpoints in parallel (each retries independently) ---
  const [relatedResponse, suggestionsResponse] = await Promise.all([
    callEndpoint(
      `${base}/dataforseo_labs/google/related_keywords/live`,
      requestBody,
      auth,
      'related_keywords',
    ),
    callEndpoint(
      `${base}/dataforseo_labs/google/keyword_suggestions/live`,
      requestBody,
      auth,
      'keyword_suggestions',
    ),
  ]);

  // --- Save raw responses ---
  const relatedPath = join(outdir, 'keywords-related-raw.json');
  const suggestionsPath = join(outdir, 'keywords-suggestions-raw.json');

  writeFileSync(relatedPath, JSON.stringify(relatedResponse, null, 2));
  writeFileSync(suggestionsPath, JSON.stringify(suggestionsResponse, null, 2));

  console.error(`Saved: ${relatedPath}`);
  console.error(`Saved: ${suggestionsPath}`);

  // --- Invoke merge-keywords.mjs for deterministic processing ---
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
}
