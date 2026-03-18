// Shared utility: parse an api.env file and return DataForSEO credentials.
// Used by fetch-serp.mjs and fetch-keywords.mjs.

import { readFileSync } from 'node:fs';

/**
 * Parse an api.env file into { auth, base }.
 * Skips empty lines and comment lines (starting with #).
 * Splits each line on the first `=` only, so values may contain `=`.
 * @param {string} filePath - absolute path to the env file
 * @returns {{ auth: string, base: string }}
 */
function loadEnv(filePath) {
  const content = readFileSync(filePath, 'utf-8');
  const env = {};
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (trimmed === '' || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;
    env[trimmed.slice(0, eqIdx)] = trimmed.slice(eqIdx + 1);
  }

  const auth = env.DATAFORSEO_AUTH;
  const base = env.DATAFORSEO_BASE;
  if (auth === undefined || auth === '') {
    throw new Error('DATAFORSEO_AUTH must be set in api.env');
  }
  if (base === undefined || base === '') {
    throw new Error('DATAFORSEO_BASE must be set in api.env');
  }
  return { auth, base };
}

export { loadEnv };
