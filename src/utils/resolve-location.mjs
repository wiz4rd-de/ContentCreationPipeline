#!/usr/bin/env node
// Resolves an ISO 3166-1 alpha-2 country code to a DataForSEO location code.
// Pure file lookup, zero network calls.
// Usage: node resolve-location.mjs <market>

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const codes = JSON.parse(readFileSync(join(__dirname, 'location-codes.json'), 'utf-8'));

const market = process.argv[2];

if (!market) {
  console.error('Usage: node resolve-location.mjs <market>');
  process.exit(1);
}

const key = market.toLowerCase();
const locationCode = codes[key];

if (locationCode === undefined) {
  console.error(`Unknown market: "${market}". Available: ${Object.keys(codes).join(', ')}`);
  process.exit(1);
}

console.log(locationCode);
