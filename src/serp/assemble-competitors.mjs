#!/usr/bin/env node
// Assembles competitor data skeleton by merging SERP processed data with page extractor outputs.
// Qualitative fields are set to null for LLM to fill in Phase 2.
// Usage: node assemble-competitors.mjs <serp-processed.json> <pages-dir/> [--date YYYY-MM-DD]

import { readFileSync, readdirSync, existsSync, writeFileSync } from 'node:fs';
import { join, basename } from 'node:path';

const args = process.argv.slice(2);
const positional = args.filter(a => !a.startsWith('--'));
const serpFile = positional[0];
const pagesDir = positional[1];
const dateFlag = args.indexOf('--date');
const date = dateFlag !== -1 ? args[dateFlag + 1] : new Date().toISOString().slice(0, 10);
const outputFlag = args.indexOf('--output');
const outputPath = outputFlag !== -1 ? args[outputFlag + 1] : null;

if (!serpFile || !pagesDir) {
  console.error('Usage: node assemble-competitors.mjs <serp-processed.json> <pages-dir/> [--date YYYY-MM-DD]');
  process.exit(1);
}

const serp = JSON.parse(readFileSync(serpFile, 'utf-8'));

// Load page extractor outputs, keyed by domain
const pageData = new Map();
if (existsSync(pagesDir)) {
  for (const file of readdirSync(pagesDir)) {
    if (!file.endsWith('.json')) continue;
    try {
      const data = JSON.parse(readFileSync(join(pagesDir, file), 'utf-8'));
      // Key by domain from filename (e.g., www.tourlane.de.json -> www.tourlane.de)
      const domain = basename(file, '.json');
      pageData.set(domain, data);
    } catch {
      // Skip malformed files
    }
  }
}

// Look up page data by domain, falling back to null for all fields
function getPageFields(domain) {
  const page = pageData.get(domain);
  if (!page || page.error) {
    return {
      word_count: null,
      h1: null,
      headings: null,
      link_count: null,
      meta_description: null,
    };
  }
  return {
    word_count: page.word_count ?? null,
    h1: page.h1 ?? null,
    headings: page.headings ?? null,
    link_count: page.link_count ?? null,
    meta_description: page.meta_description ?? null,
  };
}

// Build competitors with deterministic + null qualitative fields
const competitors = serp.competitors.map(comp => {
  const pageFields = getPageFields(comp.domain);
  return {
    // Deterministic fields from SERP
    rank: comp.rank,
    rank_absolute: comp.rank_absolute,
    url: comp.url,
    domain: comp.domain,
    title: comp.title,
    description: comp.description,
    is_featured_snippet: comp.is_featured_snippet,
    is_video: comp.is_video,
    has_rating: comp.has_rating,
    rating: comp.rating,
    timestamp: comp.timestamp,
    cited_in_ai_overview: comp.cited_in_ai_overview,
    // Deterministic fields from page extractor
    word_count: pageFields.word_count,
    h1: pageFields.h1,
    headings: pageFields.headings,
    link_count: pageFields.link_count,
    meta_description: pageFields.meta_description,
    // Qualitative fields — null placeholders for LLM
    format: null,
    topics: null,
    unique_angle: null,
    strengths: null,
    weaknesses: null,
  };
});

const output = {
  target_keyword: serp.target_keyword,
  date,
  se_results_count: serp.se_results_count,
  location_code: serp.location_code,
  language_code: serp.language_code,
  item_types_present: serp.item_types_present,
  serp_features: serp.serp_features,
  competitors,
  // Qualitative fields — null placeholders for LLM
  common_themes: null,
  content_gaps: null,
  opportunities: null,
};

const json = JSON.stringify(output, null, 2);
if (outputPath) {
  writeFileSync(outputPath, json);
} else {
  console.log(json);
}
