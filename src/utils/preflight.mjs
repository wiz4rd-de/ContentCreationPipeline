#!/usr/bin/env node
// Pre-flight validation for pipeline runs.
// Checks credentials, api.env, and extractor dependencies before any pipeline script runs.
//
// Usage: node src/utils/preflight.mjs

import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- Pure check functions (exported for testing) ---

/**
 * Check that api.env exists and is readable at the given project root.
 * @param {string} projectRoot - absolute path to the project root directory
 * @returns {{ ok: boolean, message: string }}
 */
function checkApiEnv(projectRoot) {
  const envPath = join(projectRoot, 'api.env');
  if (existsSync(envPath)) {
    return { ok: true, message: 'api.env exists' };
  }
  return {
    ok: false,
    message: 'api.env not found. Copy the template: cp api.env.example api.env',
  };
}

/**
 * Parse the raw content of an api.env file into a key/value map.
 * Skips empty lines and comment lines.
 * @param {string} content - raw file content
 * @returns {Record<string, string>}
 */
function parseEnvContent(content) {
  const env = {};
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (trimmed === '' || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;
    env[trimmed.slice(0, eqIdx)] = trimmed.slice(eqIdx + 1);
  }
  return env;
}

/**
 * Check that DATAFORSEO_AUTH is present and non-empty in the parsed env map.
 * @param {Record<string, string>} env - parsed env key/value map
 * @returns {{ ok: boolean, message: string }}
 */
function checkAuth(env) {
  const value = env.DATAFORSEO_AUTH;
  if (value !== undefined && value !== '') {
    return { ok: true, message: 'DATAFORSEO_AUTH is set' };
  }
  return {
    ok: false,
    message: 'DATAFORSEO_AUTH is not set in api.env. See api.env.example for the format.',
  };
}

/**
 * Check that a value looks like valid base64.
 * Uses a regex to catch common mistakes like leaving the placeholder or pasting raw login:password.
 * @param {string} value - the value to validate
 * @returns {boolean}
 */
function checkBase64(value) {
  if (typeof value !== 'string' || value === '') return false;
  return /^[A-Za-z0-9+/]+=*$/.test(value);
}

/**
 * Check that DATAFORSEO_AUTH in the parsed env map appears to be valid base64.
 * @param {Record<string, string>} env - parsed env key/value map
 * @returns {{ ok: boolean, message: string }}
 */
function checkAuthFormat(env) {
  const value = env.DATAFORSEO_AUTH;
  if (checkBase64(value)) {
    return { ok: true, message: 'DATAFORSEO_AUTH is valid base64 format' };
  }
  return {
    ok: false,
    message: "DATAFORSEO_AUTH does not look like valid base64. Generate it with: echo -n 'login:password' | base64",
  };
}

/**
 * Check that DATAFORSEO_BASE is present and non-empty in the parsed env map.
 * @param {Record<string, string>} env - parsed env key/value map
 * @returns {{ ok: boolean, message: string }}
 */
function checkBase(env) {
  const value = env.DATAFORSEO_BASE;
  if (value !== undefined && value !== '') {
    return { ok: true, message: 'DATAFORSEO_BASE is set' };
  }
  return {
    ok: false,
    message: 'DATAFORSEO_BASE is not set in api.env. Expected: https://api.dataforseo.com/v3',
  };
}

/**
 * Check that extractor node_modules are installed.
 * @param {string} extractorDir - absolute path to the extractor directory
 * @returns {{ ok: boolean, message: string }}
 */
function checkExtractorDeps(extractorDir) {
  if (existsSync(join(extractorDir, 'node_modules'))) {
    return { ok: true, message: 'Extractor dependencies installed' };
  }
  return {
    ok: false,
    message: 'Extractor dependencies missing. Run: cd src/extractor && npm install',
  };
}

/**
 * Run all pre-flight checks and report results to stderr.
 * Continues checking even after a failure to report all problems at once.
 * @param {string} projectRoot - absolute path to the project root
 * @returns {boolean} true if all checks passed, false if any failed
 */
function runPreflight(projectRoot) {
  const extractorDir = join(projectRoot, 'src', 'extractor');
  let allPassed = true;

  function report(result) {
    const prefix = result.ok ? '[OK]' : '[FAIL]';
    process.stderr.write(`${prefix} ${result.message}\n`);
    if (!result.ok) allPassed = false;
  }

  // Check 1: api.env exists
  const apiEnvResult = checkApiEnv(projectRoot);
  report(apiEnvResult);

  if (apiEnvResult.ok) {
    // Only parse env content if the file exists — otherwise checks 2-4 are meaningless
    const envPath = join(projectRoot, 'api.env');
    const content = readFileSync(envPath, 'utf-8');
    const env = parseEnvContent(content);

    // Check 2: DATAFORSEO_AUTH is set
    const authResult = checkAuth(env);
    report(authResult);

    // Check 3: DATAFORSEO_AUTH appears to be valid base64
    // Run regardless of check 2 so all failures are reported at once
    report(checkAuthFormat(env));

    // Check 4: DATAFORSEO_BASE is set
    report(checkBase(env));
  }

  // Check 5: Extractor dependencies installed (independent of api.env)
  report(checkExtractorDeps(extractorDir));

  return allPassed;
}

export {
  checkApiEnv,
  checkAuth,
  checkBase64,
  checkAuthFormat,
  checkBase,
  checkExtractorDeps,
  parseEnvContent,
  runPreflight,
};

// --- Main execution guard ---
const isMain = process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/'));
if (isMain) {
  const projectRoot = join(__dirname, '..', '..');
  const passed = runPreflight(projectRoot);
  if (passed) {
    process.stderr.write('All pre-flight checks passed.\n');
    process.exit(0);
  } else {
    process.exit(1);
  }
}
