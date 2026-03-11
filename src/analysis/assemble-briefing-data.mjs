#!/usr/bin/env node
// Deterministic briefing data assembler.
// Consolidates all pipeline analysis outputs into a single briefing-data.json.
// Same inputs always produce byte-identical output.
//
// Usage: node assemble-briefing-data.mjs --dir <output/YYYY-MM-DD_slug/>
// Outputs briefing-data.json to the same directory.

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join, basename } from 'node:path';

const PIPELINE_VERSION = '0.2.0';

// --- CLI parsing ---
const args = process.argv.slice(2);
function flag(name) {
  const idx = args.indexOf(name);
  if (idx === -1 || idx + 1 >= args.length) return undefined;
  return args[idx + 1];
}

const dir = flag('--dir');

if (dir === undefined) {
  console.error('Usage: node assemble-briefing-data.mjs --dir <output/YYYY-MM-DD_slug/>');
  process.exit(1);
}

// --- File discovery ---
const INPUT_FILES = {
  serp: 'serp-processed.json',
  keywordsProcessed: 'keywords-processed.json',
  keywordsFiltered: 'keywords-filtered.json',
  pageStructure: 'page-structure.json',
  contentTopics: 'content-topics.json',
  entityProminence: 'entity-prominence.json',
  competitorsData: 'competitors-data.json',
};

function loadOptional(filename) {
  const path = join(dir, filename);
  if (existsSync(path) === false) return null;
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch {
    return null;
  }
}

const data = {};
for (const [key, filename] of Object.entries(INPUT_FILES)) {
  data[key] = loadOptional(filename);
}

// --- Extract meta ---
// Date from directory name pattern YYYY-MM-DD_slug, fallback to today
function extractDateFromDir(dirPath) {
  const dirName = basename(dirPath);
  const match = dirName.match(/^(\d{4}-\d{2}-\d{2})_/);
  if (match) return match[1];
  return new Date().toISOString().slice(0, 10);
}

const dateStr = extractDateFromDir(dir);
const currentYear = parseInt(dateStr.slice(0, 4), 10);

// Seed keyword from keywords-processed or keywords-filtered or serp
const seedKeyword = data.keywordsProcessed?.seed_keyword
  || data.keywordsFiltered?.seed_keyword
  || data.serp?.target_keyword
  || null;

// --- Year normalization ---
// Replace 2024/2025 with current year in string values (recursive)
function normalizeYears(value) {
  if (value === null || value === undefined) return value;
  if (typeof value === 'string') {
    return value.replace(/\b(2024|2025)\b/g, String(currentYear));
  }
  if (Array.isArray(value)) {
    return value.map(v => normalizeYears(v));
  }
  if (typeof value === 'object') {
    const result = {};
    const keys = Object.keys(value).sort();
    for (const k of keys) {
      result[k] = normalizeYears(value[k]);
    }
    return result;
  }
  return value;
}

// --- 1. Cluster ranking: sort keyword clusters by total search volume desc ---
function buildClusterRanking() {
  const source = data.keywordsFiltered || data.keywordsProcessed;
  if (source === null || Array.isArray(source.clusters) === false) return [];

  const ranked = source.clusters.map(cluster => {
    const keywords = Array.isArray(cluster.keywords) ? cluster.keywords : [];
    const totalVolume = keywords.reduce((sum, kw) => sum + (kw.search_volume || 0), 0);
    return {
      cluster_keyword: cluster.cluster_keyword,
      cluster_label: cluster.cluster_label || null,
      keyword_count: cluster.keyword_count || keywords.length,
      total_search_volume: totalVolume,
      cluster_opportunity: cluster.cluster_opportunity ?? null,
      rank: 0, // placeholder, assigned after sort
    };
  });

  // Sort by total_search_volume desc, then cluster_keyword alphabetically for determinism
  ranked.sort((a, b) => {
    if (b.total_search_volume !== a.total_search_volume) {
      return b.total_search_volume - a.total_search_volume;
    }
    return a.cluster_keyword.localeCompare(b.cluster_keyword);
  });

  // Assign rank
  for (let i = 0; i < ranked.length; i++) {
    ranked[i].rank = i + 1;
  }

  return ranked;
}

// --- 2. Proof keywords from content-topics ---
function buildProofKeywords() {
  if (data.contentTopics === null) return null;
  return normalizeYears(data.contentTopics.proof_keywords || []);
}

// --- 3. Module frequency from page-structure ---
function buildModuleFrequency() {
  if (data.pageStructure === null) return null;
  const cc = data.pageStructure.cross_competitor;
  if (cc === undefined || cc === null) return null;
  return {
    common_modules: cc.common_modules || [],
    rare_modules: cc.rare_modules || [],
    module_frequency: cc.module_frequency || {},
  };
}

// --- 4. Section weights from content-topics ---
function buildSectionWeights() {
  if (data.contentTopics === null) return null;
  return data.contentTopics.section_weights || [];
}

// --- 5. AIO data from serp ---
function buildAioData() {
  if (data.serp === null) return null;
  const aio = data.serp.serp_features?.ai_overview;
  if (aio === undefined || aio === null) return { present: false };
  return normalizeYears(aio);
}

// --- 6. FAQ with priority + cluster mapping from filter-keywords ---
function buildFaqData() {
  if (data.keywordsFiltered === null) return null;
  const faqSelection = data.keywordsFiltered.faq_selection;
  if (Array.isArray(faqSelection) === false) return null;

  const questions = normalizeYears(faqSelection);
  // Determine source: PAA questions come from SERP
  return {
    questions,
    paa_source: 'serp',
  };
}

// --- 7. Entity candidates with prominence ---
function buildEntityCandidates() {
  // Base entity candidates from content-topics
  const baseCandidates = data.contentTopics?.entity_candidates || null;
  if (baseCandidates === null) return null;

  // If entity prominence data exists, merge prominence info
  if (data.entityProminence === null) return baseCandidates;

  const prominenceMap = new Map();
  const clusters = data.entityProminence.entity_clusters;
  if (Array.isArray(clusters)) {
    for (const cluster of clusters) {
      if (Array.isArray(cluster.entities)) {
        for (const entity of cluster.entities) {
          prominenceMap.set(entity.entity.toLowerCase(), {
            prominence: entity.prominence,
            prominence_source: entity.prominence_source || null,
          });
        }
      }
    }
  }

  return baseCandidates.map(candidate => {
    const promData = prominenceMap.get(candidate.term.toLowerCase());
    if (promData) {
      return {
        ...candidate,
        prominence: promData.prominence,
        prominence_source: promData.prominence_source,
      };
    }
    return candidate;
  });
}

// --- 8. SERP features ---
function buildSerpFeatures() {
  if (data.serp === null) return null;
  const features = data.serp.serp_features;
  if (features === undefined || features === null) return null;
  // Extract a summary of which features are present
  const summary = {};
  for (const [key, val] of Object.entries(features)) {
    if (key === 'ai_overview') {
      summary[key] = val?.present || false;
    } else if (key === 'featured_snippet') {
      summary[key] = val?.present || false;
    } else if (key === 'knowledge_graph') {
      summary[key] = val?.present || false;
    } else if (Array.isArray(val)) {
      summary[key] = val.length > 0;
    } else if (typeof val === 'object' && val !== null) {
      // For signal objects (commercial_signals, local_signals), check if any are true
      summary[key] = Object.values(val).some(v => v === true);
    } else {
      summary[key] = false;
    }
  }
  return summary;
}

// --- 9. Competitors from competitors-data or serp ---
function buildCompetitors() {
  if (data.competitorsData !== null) {
    return normalizeYears(data.competitorsData.competitors || []);
  }
  if (data.serp !== null) {
    return normalizeYears(data.serp.competitors || []);
  }
  return null;
}

// --- 10. Page structures from page-structure ---
function buildPageStructures() {
  if (data.pageStructure === null) return null;
  return data.pageStructure.competitors || [];
}

// --- 11. Content format signals from content-topics ---
function buildContentFormatSignals() {
  if (data.contentTopics === null) return null;
  return data.contentTopics.content_format_signals || {};
}

// --- 12. Stats summary -- quick-glance pipeline coverage metrics ---
function buildStatsSummary() {
  const source = data.keywordsFiltered || data.keywordsProcessed;
  const totalKeywords = source?.total_keywords ?? 0;
  const filteredCount = data.keywordsFiltered?.filtered_keywords ?? totalKeywords;
  const clusterCount = Array.isArray(source?.clusters) ? source.clusters.length : 0;
  const competitorCount = (data.competitorsData?.competitors || data.serp?.competitors || []).length;

  return {
    total_keywords: totalKeywords,
    filtered_keywords: filteredCount,
    total_clusters: clusterCount,
    competitor_count: competitorCount,
  };
}


// --- Keyword data ---
function buildKeywordData() {
  const clusters = buildClusterRanking();
  const source = data.keywordsFiltered || data.keywordsProcessed;
  return {
    clusters: normalizeYears(clusters),
    total_keywords: source?.total_keywords ?? 0,
    filtered_count: data.keywordsFiltered?.filtered_keywords ?? source?.total_keywords ?? 0,
    removal_summary: data.keywordsFiltered?.removal_summary ?? null,
  };
}

// --- Average word count from page structure ---
function buildAvgWordCount() {
  if (data.pageStructure === null) return null;
  return data.pageStructure.cross_competitor?.avg_word_count ?? null;
}

// --- Assemble final output ---
const output = {
  meta: {
    seed_keyword: seedKeyword,
    date: dateStr,
    current_year: currentYear,
    pipeline_version: PIPELINE_VERSION,
  },
  stats: buildStatsSummary(),
  keyword_data: buildKeywordData(),
  serp_data: {
    competitors: buildCompetitors(),
    serp_features: buildSerpFeatures(),
    aio: buildAioData(),
  },
  content_analysis: {
    proof_keywords: buildProofKeywords(),
    entity_candidates: buildEntityCandidates(),
    section_weights: buildSectionWeights(),
    content_format_signals: buildContentFormatSignals(),
  },
  competitor_analysis: {
    page_structures: buildPageStructures(),
    common_modules: buildModuleFrequency()?.common_modules ?? null,
    rare_modules: buildModuleFrequency()?.rare_modules ?? null,
    avg_word_count: buildAvgWordCount(),
  },
  faq_data: buildFaqData(),
  qualitative: {
    entity_clusters: null,
    unique_angles: null,
    content_format_recommendation: null,
    geo_audit: null,
    aio_strategy: null,
    briefing: null,
  },
};

// Write to file and stdout
const jsonStr = JSON.stringify(output, null, 2) + '\n';
writeFileSync(join(dir, 'briefing-data.json'), jsonStr);
console.log(jsonStr);
