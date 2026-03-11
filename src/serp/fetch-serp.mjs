#!/usr/bin/env node
// Fetches SERP data via DataForSEO async workflow (task_post / tasks_ready / task_get).
// Saves raw response as audit trail and outputs to stdout for pipeline chaining.
//
// Usage: node fetch-serp.mjs <keyword> --market <cc> --language <lc> [--outdir <dir>] [--depth N] [--timeout N] [--force]
//
// Requires api.env with DATAFORSEO_AUTH and DATAFORSEO_BASE.

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { slugify } from '../utils/slugify.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- Pure functions (exported for testing) ---

/**
 * Parse CLI argv into structured options.
 * @param {string[]} argv - process.argv.slice(2)
 * @returns {{ keyword, market, language, outdir, depth, timeout }}
 */
function parseArgs(argv) {
  function flagValue(name, fallback) {
    const idx = argv.indexOf(name);
    if (idx === -1) return fallback;
    return argv[idx + 1];
  }

  const keyword = argv.find(a => {
    if (a.startsWith('--')) return false;
    // Skip values that follow a flag
    const prevIdx = argv.indexOf(a) - 1;
    if (prevIdx >= 0 && argv[prevIdx].startsWith('--')) return false;
    return true;
  });

  return {
    keyword: keyword === undefined ? undefined : keyword,
    market: flagValue('--market', undefined),
    language: flagValue('--language', undefined),
    outdir: flagValue('--outdir', undefined),
    depth: parseInt(flagValue('--depth', '10'), 10),
    timeout: parseInt(flagValue('--timeout', '120'), 10),
    force: argv.includes('--force'),
  };
}

/**
 * Parse an api.env file into { auth, base }.
 * @param {string} filePath - path to the env file
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

/**
 * Look up a DataForSEO location code for a market.
 * @param {string} market - two-letter country code
 * @returns {number} location code
 */
function resolveLocation(market) {
  const codes = JSON.parse(readFileSync(join(__dirname, '..', 'utils', 'location-codes.json'), 'utf-8'));
  const code = codes[market.toLowerCase()];
  if (code === undefined) {
    throw new Error(`Unknown market: "${market}". Available: ${Object.keys(codes).join(', ')}`);
  }
  return code;
}

/**
 * Extract task UUID from a task_post response.
 * @param {object} response - parsed JSON from task_post
 * @returns {string} task ID
 */
function extractTaskId(response) {
  const task = response.tasks && response.tasks[0];
  if (task === undefined || task === null) {
    throw new Error('task_post returned no tasks in response');
  }

  const statusCode = task.status_code;
  if (statusCode === undefined || statusCode === null) {
    throw new Error('task_post returned no status_code');
  }
  if (String(statusCode) === '20100') {
    // 20100 = Task Created -- expected
  } else {
    throw new Error(`task_post failed with status ${statusCode}: ${task.status_message || 'unknown error'}`);
  }

  const taskId = task.id;
  if (taskId === undefined || taskId === null) {
    throw new Error('task_post returned no task ID');
  }
  return taskId;
}

/**
 * Check if a specific task ID appears in a tasks_ready response.
 * Returns false if the task is not found, or an object with the endpoint URL if found.
 * @param {object} response - parsed JSON from tasks_ready
 * @param {string} taskId - the task ID to look for
 * @returns {false | { ready: true, endpoint_advanced: string|null }}
 */
function isTaskReady(response, taskId) {
  const readyTasks = response.tasks;
  if (readyTasks && readyTasks.length > 0) {
    for (const t of readyTasks) {
      if (t.result && t.result.length > 0) {
        for (const r of t.result) {
          if (r.id === taskId) {
            return {
              ready: true,
              endpoint_advanced: r.endpoint_advanced || null,
            };
          }
        }
      }
    }
  }
  return false;
}

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

/**
 * Check whether a cached serp-raw.json file exists and contains valid, complete data
 * for the given keyword. Returns { hit: true, data } when usable, { hit: false, reason } otherwise.
 * @param {string} filePath - absolute path to serp-raw.json
 * @param {string} [keyword] - the keyword being requested; if provided, cache is rejected on mismatch
 * @returns {{ hit: true, data: object } | { hit: false, reason: string }}
 */
function checkCache(filePath, keyword) {
  if (existsSync(filePath) === false) {
    return { hit: false, reason: 'file not found' };
  }

  let data;
  try {
    data = JSON.parse(readFileSync(filePath, 'utf-8'));
  } catch (_err) {
    return { hit: false, reason: 'invalid JSON' };
  }

  // Validate shape: tasks[0].result[0].items must exist and have length > 0
  const tasks = data.tasks;
  if (tasks === undefined || tasks === null || Array.isArray(tasks) === false || tasks.length === 0) {
    return { hit: false, reason: 'missing or empty tasks array' };
  }

  const result = tasks[0].result;
  if (result === undefined || result === null || Array.isArray(result) === false || result.length === 0) {
    return { hit: false, reason: 'missing or empty result array' };
  }

  const items = result[0].items;
  if (items === undefined || items === null || Array.isArray(items) === false || items.length === 0) {
    return { hit: false, reason: 'missing or empty items array' };
  }

  // Reject cache when the stored keyword does not match the requested keyword
  if (keyword !== undefined) {
    const cachedKeyword = tasks[0].data && tasks[0].data.keyword;
    if (cachedKeyword !== keyword) {
      return { hit: false, reason: `keyword mismatch: cached "${cachedKeyword}", requested "${keyword}"` };
    }
  }

  return { hit: true, data };
}

/**
 * Derive the output directory path from a keyword and base directory.
 * Uses today's date (YYYY-MM-DD) and slugified keyword.
 * @param {string} keyword - the search keyword
 * @param {string} baseDir - parent directory for output folders
 * @returns {string} e.g. baseDir/2026-03-11_thailand-urlaub
 */
function deriveOutdir(keyword, baseDir) {
  const today = new Date();
  const yyyy = String(today.getFullYear());
  const mm = String(today.getMonth() + 1).padStart(2, '0');
  const dd = String(today.getDate()).padStart(2, '0');
  const dateStr = `${yyyy}-${mm}-${dd}`;
  const slug = slugify(keyword);
  return join(baseDir, `${dateStr}_${slug}`);
}

// --- Export pure functions for testing ---
export { parseArgs, loadEnv, resolveLocation, extractTaskId, isTaskReady, calculateBackoff, checkCache, deriveOutdir };

// --- Main execution guard ---
// Only run main logic when executed directly (not when imported as a module)
const isMain = process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/'));
if (isMain) {
  // --- Parse arguments ---
  const parsed = parseArgs(process.argv.slice(2));
  const { keyword, market, language, depth, timeout } = parsed;

  if (keyword === undefined || market === undefined || language === undefined) {
    console.error('Usage: node fetch-serp.mjs <keyword> --market <cc> --language <lc> [--outdir <dir>] [--depth N] [--timeout N] [--force]');
    process.exit(1);
  }

  // Auto-derive outdir when not provided
  const projectRoot = join(__dirname, '..', '..');
  let outdir = parsed.outdir;
  if (outdir === undefined) {
    outdir = deriveOutdir(keyword, join(projectRoot, 'output'));
    console.error(`Auto-derived outdir: ${outdir}`);
  }

  // --- Cache check ---
  if (parsed.force === false) {
    const cachePath = join(outdir, 'serp-raw.json');
    const cached = checkCache(cachePath, keyword);
    if (cached.hit === true) {
      const kw = cached.data.tasks[0].data.keyword;
      const dt = cached.data.tasks[0].result[0].datetime;
      console.error(`Cache hit: ${cachePath}`);
      console.error(`Keyword: ${kw} | Retrieved: ${dt}`);
      console.error('To fetch fresh data, re-run with --force');
      process.stdout.write(JSON.stringify(cached.data, null, 2) + '\n');
      process.exit(0);
    }
    if (cached.hit === false) {
      console.error(`No valid cache (${cached.reason}), fetching from API...`);
    }
  }

  // --- Load API credentials ---
  const envPath = join(__dirname, '..', '..', 'api.env');
  let creds;
  try {
    creds = loadEnv(envPath);
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(1);
  }
  const { auth, base } = creds;

  // --- Resolve location code ---
  let locationCode;
  try {
    locationCode = resolveLocation(market);
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }

  // --- Ensure output directory exists ---
  mkdirSync(outdir, { recursive: true });

  // --- API helpers ---
  async function postEndpoint(path, body) {
    const url = `${base}/${path}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Basic ${auth}`,
        'Content-Type': 'application/json; charset=utf-8',
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });
    if (res.ok === false) {
      throw new Error(`API error ${res.status}: ${await res.text()}`);
    }
    return res.json();
  }

  async function getEndpoint(path) {
    const url = `${base}/${path}`;
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Basic ${auth}`,
      },
      signal: AbortSignal.timeout(30000),
    });
    if (res.ok === false) {
      throw new Error(`API error ${res.status}: ${await res.text()}`);
    }
    return res.json();
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // --- Step 1: Post task ---
  console.error(`Posting SERP task for "${keyword}" (market=${market}, lang=${language}, depth=${depth})...`);

  const taskPostBody = [{
    keyword,
    language_code: language,
    location_code: locationCode,
    depth,
  }];

  const postResponse = await postEndpoint('serp/google/organic/task_post', taskPostBody);
  const taskId = extractTaskId(postResponse);

  console.error(`Task created: ${taskId}`);

  // --- Step 2: Poll tasks_ready with exponential backoff ---
  const INITIAL_DELAY = 5000;  // 5 seconds
  const BACKOFF_FACTOR = 1.5;
  const MAX_DELAY = 30000;     // 30 seconds
  const timeoutMs = timeout * 1000;
  const startTime = Date.now();

  let attempt = 0;
  let taskReady = false;

  while (taskReady === false) {
    const elapsed = Date.now() - startTime;
    if (elapsed >= timeoutMs) {
      throw new Error(`Task ${taskId} timed out after ${timeout} seconds. Status: pending`);
    }

    const delay = calculateBackoff(attempt, { initialDelay: INITIAL_DELAY, factor: BACKOFF_FACTOR, maxDelay: MAX_DELAY });
    console.error(`Waiting ${(delay / 1000).toFixed(1)}s before poll attempt ${attempt + 1}...`);
    await sleep(delay);

    console.error(`Polling for task ${taskId}... attempt ${attempt + 1}`);

    const readyResponse = await getEndpoint('serp/google/organic/tasks_ready');
    const result = isTaskReady(readyResponse, taskId);

    if (result !== false) {
      taskReady = true;
    }

    attempt += 1;
  }

  console.error(`Task ${taskId} is ready. Retrieving results...`);

  // --- Step 3: Retrieve results ---
  const getResponse = await getEndpoint(`serp/google/organic/task_get/advanced/${taskId}`);

  const getTask = getResponse.tasks && getResponse.tasks[0];
  if (getTask === undefined || getTask === null) {
    throw new Error('task_get returned no tasks in response');
  }

  const getStatusCode = getTask.status_code;
  if (getStatusCode !== undefined && getStatusCode !== null) {
    const code = getStatusCode.toString();
    if (code === '40401') {
      throw new Error(`Task ${taskId} not found (40401). The task may have expired.`);
    }
    if (code === '40403') {
      throw new Error(`Task ${taskId} results expired (40403). Results are only available for 3 days.`);
    }
    if (code === '20000') {
      // Success
    } else {
      throw new Error(`task_get failed with status ${getStatusCode}: ${getTask.status_message || 'unknown error'}`);
    }
  } else {
    throw new Error('task_get returned no status_code');
  }

  // --- Save raw response ---
  const rawPath = join(outdir, 'serp-raw.json');
  const rawJson = JSON.stringify(getResponse, null, 2);
  writeFileSync(rawPath, rawJson);
  console.error(`Saved: ${rawPath}`);

  // --- Output to stdout for pipeline chaining ---
  process.stdout.write(rawJson + '\n');
}
