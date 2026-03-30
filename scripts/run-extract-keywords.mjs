#!/usr/bin/env node
// CLI wrapper for extract-keywords library module.
// Used by generate-golden.sh to produce golden output snapshots.
//
// Usage: node scripts/run-extract-keywords.mjs <input.json> --output <output.json>

import { readFileSync, writeFileSync } from 'node:fs';
import { extractKeywords } from '../src/keywords/extract-keywords.mjs';

const args = process.argv.slice(2);
const filePath = args.find(a => !a.startsWith('--'));
const outputIdx = args.indexOf('--output');
const outputPath = outputIdx !== -1 ? args[outputIdx + 1] : null;

if (!filePath) {
  console.error('Usage: node scripts/run-extract-keywords.mjs <input.json> --output <output.json>');
  process.exit(1);
}

const raw = JSON.parse(readFileSync(filePath, 'utf-8'));
const result = extractKeywords(raw, { includeDifficulty: true });
const json = JSON.stringify(result, null, 2);

if (outputPath) {
  writeFileSync(outputPath, json);
} else {
  console.log(json);
}
