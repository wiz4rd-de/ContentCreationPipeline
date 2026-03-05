#!/usr/bin/env node
// Deterministic SERP parser for DataForSEO advanced endpoint responses.
// Usage: node process-serp.mjs <raw-serp.json> [--top N]
// Outputs structured JSON to stdout. Same input always produces identical output.

import { readFileSync } from 'node:fs';

const args = process.argv.slice(2);
const filePath = args.find(a => !a.startsWith('--'));
const topFlag = args.indexOf('--top');
const topN = topFlag !== -1 ? parseInt(args[topFlag + 1], 10) : 10;

if (!filePath) {
  console.error('Usage: node process-serp.mjs <raw-serp.json> [--top N]');
  process.exit(1);
}

const raw = JSON.parse(readFileSync(filePath, 'utf-8'));
const result = raw.tasks?.[0]?.result?.[0];

if (!result) {
  console.error('Error: No result found at tasks[0].result[0]');
  process.exit(1);
}

const items = result.items || [];

// --- Helper: filter items by type ---
function itemsByType(type) {
  return items.filter(i => i.type === type);
}

// --- Extract AI Overview ---
function extractAiOverview() {
  const aiItems = itemsByType('ai_overview');
  if (aiItems.length === 0) return { present: false };

  const item = aiItems[0];
  // Collect all unique references from ai_overview_element sub-items
  const seen = new Set();
  const references = [];
  if (item.items) {
    for (const element of item.items) {
      if (element.references) {
        for (const ref of element.references) {
          const key = ref.url || ref.domain;
          if (key && !seen.has(key)) {
            seen.add(key);
            references.push({
              domain: ref.domain || null,
              url: ref.url || null,
              title: ref.title || null,
            });
          }
        }
      }
    }
  }
  return { present: true, references };
}

// --- Extract Featured Snippet ---
function extractFeaturedSnippet() {
  const organic = itemsByType('organic');
  const snippet = organic.find(i => i.is_featured_snippet === true);
  if (!snippet) {
    // Also check for dedicated featured_snippet type
    const dedicated = itemsByType('featured_snippet');
    if (dedicated.length === 0) return { present: false };
    const d = dedicated[0];
    return {
      present: true,
      format: d.featured_snippet?.type || null,
      source_domain: d.domain || null,
      source_url: d.url || null,
    };
  }
  return {
    present: true,
    format: snippet.featured_snippet?.type || null,
    source_domain: snippet.domain || null,
    source_url: snippet.url || null,
  };
}

// --- Extract People Also Ask ---
function extractPeopleAlsoAsk() {
  const paaItems = itemsByType('people_also_ask');
  const questions = [];
  for (const paa of paaItems) {
    if (paa.items) {
      for (const q of paa.items) {
        if (q.title) questions.push(q.title);
      }
    }
  }
  return questions;
}

// --- Extract People Also Search ---
function extractPeopleAlsoSearch() {
  const pasItems = itemsByType('people_also_search');
  const queries = [];
  for (const pas of pasItems) {
    if (pas.items) {
      for (const q of pas.items) {
        if (typeof q === 'string') queries.push(q);
      }
    }
  }
  return queries;
}

// --- Extract Related Searches ---
function extractRelatedSearches() {
  const rsItems = itemsByType('related_searches');
  const queries = [];
  for (const rs of rsItems) {
    if (rs.items) {
      for (const q of rs.items) {
        if (typeof q === 'string') queries.push(q);
      }
    }
  }
  return queries;
}

// --- Extract Discussions and Forums ---
function extractDiscussions() {
  const items_ = itemsByType('discussions_and_forums');
  const results = [];
  for (const d of items_) {
    if (d.items) {
      for (const item of d.items) {
        results.push({
          source: item.domain || item.source || null,
          url: item.url || null,
          title: item.title || null,
        });
      }
    } else {
      results.push({
        source: d.domain || d.source || null,
        url: d.url || null,
        title: d.title || null,
      });
    }
  }
  return results;
}

// --- Extract Video ---
function extractVideo() {
  const videoItems = itemsByType('video');
  const results = [];
  for (const v of videoItems) {
    if (v.items) {
      for (const item of v.items) {
        results.push({
          title: item.title || null,
          url: item.url || null,
          source: item.domain || item.source || null,
        });
      }
    } else {
      results.push({
        title: v.title || null,
        url: v.url || null,
        source: v.domain || v.source || null,
      });
    }
  }
  return results;
}

// --- Extract Top Stories ---
function extractTopStories() {
  const tsItems = itemsByType('top_stories');
  const results = [];
  for (const ts of tsItems) {
    if (ts.items) {
      for (const item of ts.items) {
        results.push({
          title: item.title || null,
          url: item.url || null,
          source: item.domain || item.source || null,
        });
      }
    } else {
      results.push({
        title: ts.title || null,
        url: ts.url || null,
        source: ts.domain || ts.source || null,
      });
    }
  }
  return results;
}

// --- Extract Knowledge Graph ---
function extractKnowledgeGraph() {
  const kgItems = itemsByType('knowledge_graph');
  if (kgItems.length === 0) return { present: false };
  const kg = kgItems[0];
  return {
    present: true,
    title: kg.title || null,
    description: kg.description || null,
  };
}

// --- Extract Commercial Signals ---
function extractCommercialSignals() {
  const types = new Set(items.map(i => i.type));
  return {
    paid_ads_present: types.has('paid'),
    shopping_present: types.has('shopping'),
    commercial_units_present: types.has('commercial_units'),
    popular_products_present: types.has('popular_products'),
  };
}

// --- Extract Local Signals ---
function extractLocalSignals() {
  const types = new Set(items.map(i => i.type));
  return {
    local_pack_present: types.has('local_pack'),
    map_present: types.has('map'),
    hotels_pack_present: types.has('hotels_pack'),
  };
}

// --- Extract Other Features ---
function extractOtherFeatures() {
  const dedicatedTypes = new Set([
    'organic', 'ai_overview', 'featured_snippet',
    'people_also_ask', 'people_also_search', 'related_searches',
    'discussions_and_forums', 'video', 'top_stories', 'knowledge_graph',
    'paid', 'shopping', 'commercial_units', 'popular_products',
    'local_pack', 'map', 'hotels_pack',
  ]);
  const present = new Set();
  for (const item of items) {
    if (!dedicatedTypes.has(item.type)) {
      present.add(item.type);
    }
  }
  return [...present].sort();
}

// --- Extract Competitors (organic results) ---
function extractCompetitors() {
  const organicItems = itemsByType('organic');
  const aiOverview = extractAiOverview();
  const aiDomains = new Set();
  if (aiOverview.present && aiOverview.references) {
    for (const ref of aiOverview.references) {
      if (ref.domain) aiDomains.add(ref.domain);
    }
  }

  return organicItems.slice(0, topN).map(item => ({
    rank: item.rank_group,
    rank_absolute: item.rank_absolute,
    url: item.url || null,
    domain: item.domain || null,
    title: item.title || null,
    description: item.description || null,
    is_featured_snippet: item.is_featured_snippet === true,
    is_video: item.is_video === true,
    has_rating: item.rating != null,
    rating: item.rating ? {
      value: item.rating.value,
      votes_count: item.rating.votes_count,
      rating_max: item.rating.rating_max,
    } : null,
    timestamp: item.timestamp || null,
    cited_in_ai_overview: aiDomains.has(item.domain),
  }));
}

// --- Build output ---
const output = {
  target_keyword: result.keyword,
  se_results_count: result.se_results_count,
  location_code: result.location_code,
  language_code: result.language_code,
  item_types_present: result.item_types || [],
  serp_features: {
    ai_overview: extractAiOverview(),
    featured_snippet: extractFeaturedSnippet(),
    people_also_ask: extractPeopleAlsoAsk(),
    people_also_search: extractPeopleAlsoSearch(),
    related_searches: extractRelatedSearches(),
    discussions_and_forums: extractDiscussions(),
    video: extractVideo(),
    top_stories: extractTopStories(),
    knowledge_graph: extractKnowledgeGraph(),
    commercial_signals: extractCommercialSignals(),
    local_signals: extractLocalSignals(),
    other_features_present: extractOtherFeatures(),
  },
  competitors: extractCompetitors(),
};

console.log(JSON.stringify(output, null, 2));
