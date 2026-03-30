#!/usr/bin/env node
// Post-processing step: freezes non-deterministic fields in briefing-data.json
// to fixed sentinel values for golden output snapshot determinism.
//
// Usage: node scripts/freeze-briefing-fields.mjs <briefing-data.json>
//
// Overwrites the file in-place with:
//   meta.phase1_completed_at -> "2026-01-01T00:00:00.000Z"
//   meta.current_year -> 2026

import { readFileSync, writeFileSync } from 'node:fs';

const filePath = process.argv[2];
if (!filePath) {
  console.error('Usage: node scripts/freeze-briefing-fields.mjs <briefing-data.json>');
  process.exit(1);
}

const data = JSON.parse(readFileSync(filePath, 'utf-8'));

if (data.meta) {
  data.meta.phase1_completed_at = '2026-01-01T00:00:00.000Z';
  data.meta.current_year = 2026;
}

writeFileSync(filePath, JSON.stringify(data, null, 2) + '\n');
