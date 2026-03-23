#!/usr/bin/env node
// Prints a compact plain-text summary of a briefing-data.json file to stdout.
// Deterministic: same input always produces identical output.
//
// Usage: node summarize-briefing.mjs --file <path/to/briefing-data.json>

import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

// --- CLI parsing ---
const args = process.argv.slice(2);
function flag(name) {
  const idx = args.indexOf(name);
  if (idx === -1 || idx + 1 >= args.length) return undefined;
  return args[idx + 1];
}

const file = flag('--file');

if (file === undefined) {
  console.error('Usage: node summarize-briefing.mjs --file <path/to/briefing-data.json>');
  process.exit(1);
}

const filePath = resolve(file);
if (!existsSync(filePath)) {
  console.error(`File not found: ${filePath}`);
  process.exit(1);
}

const data = JSON.parse(readFileSync(filePath, 'utf-8'));

// --- Safe accessors ---
const meta = data.meta || {};
const kw = data.keyword_data || {};
const serp = data.serp_data || {};
const comp = data.competitor_analysis || {};
const faq = data.faq_data || {};

const seedKeyword = meta.seed_keyword || 'n/a';
const totalKw = kw.total_keywords ?? 0;
const filteredKw = kw.filtered_count ?? 0;
const clusterCount = Array.isArray(kw.clusters) ? kw.clusters.length : 0;
const competitorCount = Array.isArray(serp.competitors) ? serp.competitors.length : 0;
const avgWords = comp.avg_word_count ?? 'n/a';
const faqCount = Array.isArray(faq.questions) ? faq.questions.length : 0;

// SERP features: list truthy keys
const serpFeatures = serp.serp_features || {};
const truthyFeatures = Object.entries(serpFeatures)
  .filter(([, v]) => v)
  .map(([k]) => k);
const serpLine = truthyFeatures.length > 0 ? truthyFeatures.join(', ') : 'none';

// AIO
const aioPresent = serp.aio && serp.aio.present ? 'yes' : 'no';

// Modules
const commonMods = Array.isArray(comp.common_modules) ? comp.common_modules.join(', ') : 'n/a';
const rareMods = Array.isArray(comp.rare_modules) ? comp.rare_modules.join(', ') : 'n/a';

// Removal summary: format non-zero entries as "N category, N category, ..."
const removal = kw.removal_summary || {};
const removalParts = Object.entries(removal)
  .filter(([, v]) => v > 0)
  .map(([k, v]) => `${v} ${k}`);
const removalLine = removalParts.length > 0 ? removalParts.join(', ') : 'none';

const divider = '\u2500'.repeat(35);

const summary = `Briefing Summary: ${seedKeyword}
${divider}
Keywords:    ${totalKw} total, ${filteredKw} after filtering
Clusters:    ${clusterCount}
Competitors: ${competitorCount} (${avgWords} avg words)
FAQ:         ${faqCount} questions
SERP:        ${serpLine}
AIO:         ${aioPresent}
Modules:     common: ${commonMods}, rare: ${rareMods}
Removals:    ${removalLine}`;

console.log(summary);
