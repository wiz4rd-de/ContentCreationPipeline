import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'serp', 'process-serp.mjs');
const fixtures = join(__dirname, '..', 'fixtures', 'process-serp');

function run(fixture) {
  const stdout = execFileSync('node', [script, join(fixtures, fixture)], {
    encoding: 'utf-8',
  });
  return JSON.parse(stdout);
}

function runRaw(fixture) {
  return execFileSync('node', [script, join(fixtures, fixture)], {
    encoding: 'utf-8',
  });
}

// =============================================================================
// AI Overview enrichment
// =============================================================================

describe('extractAiOverview enriched fields', () => {

  it('returns title from first ai_overview item', () => {
    const result = run('serp-with-aio.json');
    assert.equal(result.serp_features.ai_overview.title, 'Best SEO Tools for 2026');
  });

  it('concatenates text from sub-item descriptions, content, and text fields', () => {
    const result = run('serp-with-aio.json');
    const aio = result.serp_features.ai_overview;
    assert.equal(typeof aio.text, 'string');
    // Should contain text from description, content, and text fields
    assert.ok(aio.text.includes('Ahrefs is widely considered'));
    assert.ok(aio.text.includes('Semrush offers comprehensive'));
    assert.ok(aio.text.includes('Google Search Console is a free tool'));
    // Also includes the parent element description
    assert.ok(aio.text.includes('Here are the top SEO tools'));
  });

  it('returns deduplicated cited_domains sorted alphabetically', () => {
    const result = run('serp-with-aio.json');
    const aio = result.serp_features.ai_overview;
    // ahrefs.com appears twice in references but should be deduplicated
    assert.deepEqual(aio.cited_domains, ['ahrefs.com', 'google.com', 'semrush.com']);
  });

  it('returns cited_urls from all references', () => {
    const result = run('serp-with-aio.json');
    const aio = result.serp_features.ai_overview;
    assert.equal(aio.cited_urls.length, 3);
    assert.ok(aio.cited_urls.includes('https://ahrefs.com/blog/best-seo-tools'));
    assert.ok(aio.cited_urls.includes('https://semrush.com/blog/seo-tools'));
    assert.ok(aio.cited_urls.includes('https://search.google.com/search-console'));
  });

  it('returns cited_sources from all references', () => {
    const result = run('serp-with-aio.json');
    const aio = result.serp_features.ai_overview;
    assert.equal(aio.cited_sources.length, 3);
    assert.ok(aio.cited_sources.includes('Best SEO Tools - Ahrefs'));
    assert.ok(aio.cited_sources.includes('Google Search Console'));
  });

  it('returns references_count as count of unique references', () => {
    const result = run('serp-with-aio.json');
    const aio = result.serp_features.ai_overview;
    // 3 unique refs (ahrefs appears in both elements but deduped by URL)
    assert.equal(aio.references_count, 3);
  });

  it('preserves backward-compatible present and references fields', () => {
    const result = run('serp-with-aio.json');
    const aio = result.serp_features.ai_overview;
    assert.equal(aio.present, true);
    assert.ok(Array.isArray(aio.references));
    assert.equal(aio.references.length, 3);
    // Each reference has domain, url, title
    for (const ref of aio.references) {
      assert.ok('domain' in ref);
      assert.ok('url' in ref);
      assert.ok('title' in ref);
    }
  });

  it('returns text as null when AIO has no text content', () => {
    const result = run('serp-aio-no-text.json');
    const aio = result.serp_features.ai_overview;
    assert.equal(aio.present, true);
    assert.equal(aio.title, 'About this topic');
    assert.equal(aio.text, null);
    assert.equal(aio.references_count, 1);
  });
});

// =============================================================================
// AI Overview absent
// =============================================================================

describe('extractAiOverview when absent', () => {

  it('returns present: false with null/empty enriched fields', () => {
    const result = run('serp-no-aio-no-paa.json');
    const aio = result.serp_features.ai_overview;
    assert.equal(aio.present, false);
    assert.equal(aio.title, null);
    assert.equal(aio.text, null);
    assert.deepEqual(aio.cited_domains, []);
    assert.deepEqual(aio.cited_urls, []);
    assert.deepEqual(aio.cited_sources, []);
    assert.equal(aio.references_count, 0);
  });
});

// =============================================================================
// People Also Ask enrichment
// =============================================================================

describe('extractPeopleAlsoAsk enriched format', () => {

  it('returns array of objects with question, answer, url, domain', () => {
    const result = run('serp-with-aio.json');
    const paa = result.serp_features.people_also_ask;
    assert.ok(Array.isArray(paa));
    assert.equal(paa.length, 3);
    for (const item of paa) {
      assert.ok('question' in item);
      assert.ok('answer' in item);
      assert.ok('url' in item);
      assert.ok('domain' in item);
    }
  });

  it('extracts answer from expanded_element description', () => {
    const result = run('serp-with-aio.json');
    const paa = result.serp_features.people_also_ask;
    const first = paa[0];
    assert.equal(first.question, 'What is the best free SEO tool?');
    assert.equal(first.answer, 'Google Search Console is widely considered the best free SEO tool.');
    assert.equal(first.url, 'https://example.com/free-seo-tools');
    assert.equal(first.domain, 'example.com');
  });

  it('sets null fields when expanded_element is empty array', () => {
    const result = run('serp-with-aio.json');
    const paa = result.serp_features.people_also_ask;
    const third = paa[2];
    assert.equal(third.question, 'Is Ahrefs better than Semrush?');
    assert.equal(third.answer, null);
    assert.equal(third.url, null);
    assert.equal(third.domain, null);
  });

  it('handles PAA items with null or missing expanded_element', () => {
    const result = run('serp-paa-no-expanded.json');
    const paa = result.serp_features.people_also_ask;
    // Third item has title: null, should be skipped
    assert.equal(paa.length, 2);
    assert.equal(paa[0].question, 'What is SEO?');
    assert.equal(paa[0].answer, null);
    assert.equal(paa[0].url, null);
    assert.equal(paa[0].domain, null);
    assert.equal(paa[1].question, 'How does SEO work?');
    assert.equal(paa[1].answer, null);
  });

  it('returns empty array when no PAA present', () => {
    const result = run('serp-no-aio-no-paa.json');
    const paa = result.serp_features.people_also_ask;
    assert.deepEqual(paa, []);
  });
});

// =============================================================================
// Backward compatibility
// =============================================================================

describe('backward compatibility', () => {

  it('competitors still have cited_in_ai_overview field', () => {
    const result = run('serp-with-aio.json');
    for (const comp of result.competitors) {
      assert.ok('cited_in_ai_overview' in comp);
    }
    // ahrefs.com is cited in AIO
    const ahrefs = result.competitors.find(c => c.domain === 'ahrefs.com');
    assert.equal(ahrefs.cited_in_ai_overview, true);
  });

  it('maintains all existing top-level output fields', () => {
    const result = run('serp-with-aio.json');
    const keys = [
      'target_keyword', 'se_results_count', 'location_code',
      'language_code', 'item_types_present', 'serp_features', 'competitors',
    ];
    for (const key of keys) {
      assert.ok(key in result, `missing key: ${key}`);
    }
  });

  it('maintains all existing serp_features keys', () => {
    const result = run('serp-with-aio.json');
    const keys = [
      'ai_overview', 'featured_snippet', 'people_also_ask',
      'people_also_search', 'related_searches', 'discussions_and_forums',
      'video', 'top_stories', 'knowledge_graph',
      'commercial_signals', 'local_signals', 'other_features_present',
    ];
    for (const key of keys) {
      assert.ok(key in result.serp_features, `missing serp_features key: ${key}`);
    }
  });
});

// =============================================================================
// Determinism
// =============================================================================

describe('determinism', () => {

  it('produces byte-identical output for same input (with AIO)', () => {
    const run1 = runRaw('serp-with-aio.json');
    const run2 = runRaw('serp-with-aio.json');
    assert.equal(run1, run2);
  });

  it('produces byte-identical output for same input (no AIO)', () => {
    const run1 = runRaw('serp-no-aio-no-paa.json');
    const run2 = runRaw('serp-no-aio-no-paa.json');
    assert.equal(run1, run2);
  });
});

// =============================================================================
// Real-world fixture (if serp-raw-v3 exists)
// =============================================================================

describe('real-world PAA fixture', () => {

  it('extracts PAA with answers from real DataForSEO response', () => {
    const realFixture = join(
      __dirname, '..', '..', 'output',
      '2026-03-03_schoenste-straende-thailand', 'serp-raw-v3.json',
    );
    let result;
    try {
      const stdout = execFileSync('node', [script, realFixture], {
        encoding: 'utf-8',
      });
      result = JSON.parse(stdout);
    } catch (_e) {
      // Skip if real fixture does not exist
      return;
    }
    const paa = result.serp_features.people_also_ask;
    assert.ok(paa.length >= 1, 'should have at least one PAA question');
    for (const item of paa) {
      assert.equal(typeof item.question, 'string');
      assert.ok('answer' in item);
      assert.ok('url' in item);
      assert.ok('domain' in item);
    }
    // First question from the real fixture
    assert.ok(paa[0].question.includes('Thailand'));
    // First PAA has an expanded answer
    assert.equal(typeof paa[0].answer, 'string');
    assert.equal(typeof paa[0].url, 'string');
    assert.equal(typeof paa[0].domain, 'string');
  });
});
