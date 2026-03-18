#!/usr/bin/env node
// Deterministic qualitative merge.
// Patches qualitative.json fields into briefing-data.json.
// Only overwrites fields that are non-null in qualitative.json.
// Same inputs always produce byte-identical output.
//
// Usage: node merge-qualitative.mjs --dir <output/YYYY-MM-DD_slug/>

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

// --- CLI parsing ---
const args = process.argv.slice(2);
function flag(name) {
  const idx = args.indexOf(name);
  if (idx === -1 || idx + 1 >= args.length) return undefined;
  return args[idx + 1];
}

const dir = flag('--dir');

if (dir === undefined) {
  console.error('Usage: node merge-qualitative.mjs --dir <output/YYYY-MM-DD_slug/>');
  process.exit(1);
}

const briefingPath = join(dir, 'briefing-data.json');
const qualitativePath = join(dir, 'qualitative.json');

if (existsSync(briefingPath) === false) {
  console.error(`Error: briefing-data.json not found in ${dir}`);
  process.exit(1);
}

if (existsSync(qualitativePath) === false) {
  console.error(`Error: qualitative.json not found in ${dir}`);
  process.exit(1);
}

const briefing = JSON.parse(readFileSync(briefingPath, 'utf-8'));
const qualitative = JSON.parse(readFileSync(qualitativePath, 'utf-8'));

// Merge non-null qualitative fields into briefing-data.json.
// Only the top-level keys of qualitative.json are considered.
const merged = { ...briefing };
merged.qualitative = { ...briefing.qualitative };

for (const [key, value] of Object.entries(qualitative)) {
  if (value !== null && value !== undefined) {
    merged.qualitative[key] = value;
  }
}

const jsonStr = JSON.stringify(merged, null, 2) + '\n';
writeFileSync(briefingPath, jsonStr);
console.log(`merge-qualitative: patched ${Object.keys(qualitative).filter(k => qualitative[k] !== null).length} field(s) into briefing-data.json`);
