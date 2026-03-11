#!/usr/bin/env node
// Deterministic entity prominence calculator.
// Re-computes prominence by counting how many competitor pages mention each entity's synonyms.
// Usage: node compute-entity-prominence.mjs --entities <entities.json> --pages-dir <pages/>
// Outputs corrected JSON to stdout. Same inputs always produce byte-identical output.

import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

// --- CLI parsing ---
const args = process.argv.slice(2);
function flag(name) {
  const idx = args.indexOf(name);
  if (idx === -1 || idx + 1 >= args.length) return undefined;
  return args[idx + 1];
}

const entitiesPath = flag('--entities');
const pagesDir = flag('--pages-dir');

if (entitiesPath === undefined || pagesDir === undefined) {
  console.error('Usage: node compute-entity-prominence.mjs --entities <entities.json> --pages-dir <pages/>');
  process.exit(1);
}

// --- Load inputs ---
const entitiesData = JSON.parse(readFileSync(entitiesPath, 'utf-8'));
const pageFiles = readdirSync(pagesDir)
  .filter(f => f.endsWith('.json'))
  .sort(); // alphabetical for determinism

const pageTexts = pageFiles.map(f => {
  const page = JSON.parse(readFileSync(join(pagesDir, f), 'utf-8'));
  return (page.main_content_text || '').toLowerCase();
});

const totalPages = pageTexts.length;

// --- Check synonym match in text ---
function synonymAppearsInText(synonym, text) {
  const lower = synonym.toLowerCase();
  if (lower.length <= 4) {
    // Word-boundary matching for short synonyms to avoid false positives
    const escaped = lower.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp('\\b' + escaped + '\\b');
    return re.test(text);
  }
  return text.includes(lower);
}

// --- Parse "N/M" prominence string -> numeric count ---
function parseProminenceCount(promStr) {
  if (typeof promStr === 'undefined' || promStr === null) return NaN;
  const str = String(promStr);
  const match = str.match(/^(\d+)\s*\/\s*\d+$/);
  if (match) return parseInt(match[1], 10);
  return NaN;
}

// --- Process entity clusters ---
const corrections = [];

const outputClusters = entitiesData.entity_clusters.map(cluster => {
  const outputEntities = cluster.entities.map(entity => {
    const synonyms = entity.synonyms || [];

    // Count pages where any synonym appears
    let count = 0;
    for (const text of pageTexts) {
      let found = false;
      for (const syn of synonyms) {
        if (synonymAppearsInText(syn, text)) {
          found = true;
          break;
        }
      }
      if (found) count++;
    }

    const codeProminence = count + '/' + totalPages;
    const geminiCount = parseProminenceCount(entity.prominence);
    const delta = Number.isNaN(geminiCount) ? null : Math.abs(count - geminiCount);

    if (delta !== null && delta >= 2) {
      corrections.push({
        entity: entity.entity,
        category: cluster.category_name,
        gemini: entity.prominence,
        code: codeProminence,
        delta,
      });
    }

    return {
      entity: entity.entity,
      prominence: codeProminence,
      prominence_gemini: entity.prominence,
      prominence_source: 'code',
      synonyms: entity.synonyms,
    };
  });

  return {
    category_name: cluster.category_name,
    entities: outputEntities,
  };
});

const output = {
  entity_clusters: outputClusters,
};

if (corrections.length > 0) {
  // Sort corrections deterministically by category, then entity name
  corrections.sort((a, b) => {
    const catCmp = a.category.localeCompare(b.category);
    if (catCmp === 0) return a.entity.localeCompare(b.entity);
    return catCmp;
  });
  output._debug = { corrections };
}

console.log(JSON.stringify(output, null, 2));
