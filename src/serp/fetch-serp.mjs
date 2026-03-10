#!/usr/bin/env node
// Fetches SERP data via DataForSEO async workflow (task_post / tasks_ready / task_get).
// Saves raw response as audit trail and outputs to stdout for pipeline chaining.
//
// Usage: node fetch-serp.mjs <keyword> --market <cc> --language <lc> --outdir <dir> [--depth N] [--timeout N]
//
// Requires api.env with DATAFORSEO_AUTH and DATAFORSEO_BASE.

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- Parse arguments ---
const args = process.argv.slice(2);

function flagValue(name, fallback) {
  const idx = args.indexOf(name);
  if (idx === -1) return fallback;
  return args[idx + 1];
}

const keyword = args.find(a => {
  if (a.startsWith('--')) return false;
  // Skip values that follow a flag
  const prevIdx = args.indexOf(a) - 1;
  if (prevIdx >= 0 && args[prevIdx].startsWith('--')) return false;
  return true;
});
const market = flagValue('--market', undefined);
const language = flagValue('--language', undefined);
const outdir = flagValue('--outdir', undefined);
const depth = parseInt(flagValue('--depth', '10'), 10);
const timeout = parseInt(flagValue('--timeout', '120'), 10);

if (keyword === undefined || market === undefined || language === undefined || outdir === undefined) {
  console.error('Usage: node fetch-serp.mjs <keyword> --market <cc> --language <lc> --outdir <dir> [--depth N] [--timeout N]');
  process.exit(1);
}

// --- Load API credentials ---
const envPath = join(__dirname, '..', '..', 'api.env');
const envContent = readFileSync(envPath, 'utf-8');
const env = {};
for (const line of envContent.split('\n')) {
  const trimmed = line.trim();
  if (trimmed === '' || trimmed.startsWith('#')) continue;
  const eqIdx = trimmed.indexOf('=');
  if (eqIdx === -1) continue;
  env[trimmed.slice(0, eqIdx)] = trimmed.slice(eqIdx + 1);
}

const auth = env.DATAFORSEO_AUTH;
const base = env.DATAFORSEO_BASE;
if (auth === undefined || auth === '' || base === undefined || base === '') {
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

// --- Exponential backoff calculator ---
function calculateBackoff(attempt, initialDelay, factor, maxDelay) {
  const delay = Math.min(initialDelay * Math.pow(factor, attempt), maxDelay);
  return delay;
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

const postTask = postResponse.tasks && postResponse.tasks[0];
if (postTask === undefined || postTask === null) {
  throw new Error('task_post returned no tasks in response');
}

const statusCode = postTask.status_code;
if (statusCode === undefined || statusCode === null) {
  throw new Error('task_post returned no status_code');
}
if (String(statusCode) === '20100') {
  // 20100 = Task Created -- expected
} else {
  throw new Error(`task_post failed with status ${statusCode}: ${postTask.status_message || 'unknown error'}`);
}

const taskId = postTask.id;
if (taskId === undefined || taskId === null) {
  throw new Error('task_post returned no task ID');
}

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

  const delay = calculateBackoff(attempt, INITIAL_DELAY, BACKOFF_FACTOR, MAX_DELAY);
  console.error(`Waiting ${(delay / 1000).toFixed(1)}s before poll attempt ${attempt + 1}...`);
  await sleep(delay);

  console.error(`Polling for task ${taskId}... attempt ${attempt + 1}`);

  const readyResponse = await getEndpoint('serp/google/organic/tasks_ready');
  const readyTasks = readyResponse.tasks;

  if (readyTasks && readyTasks.length > 0) {
    for (const t of readyTasks) {
      if (t.result && t.result.length > 0) {
        for (const r of t.result) {
          if (r.id === taskId) {
            taskReady = true;
            break;
          }
        }
      }
      if (taskReady) break;
    }
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
