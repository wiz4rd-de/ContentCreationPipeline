import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { writeFileSync, readFileSync, mkdirSync, rmSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'analysis', 'assemble-briefing-data.mjs');
const fixtureDir = join(__dirname, '..', 'fixtures', 'assemble-briefing-data', '2026-03-09_test-keyword');

function run(opts = {}) {
  const extraArgs = opts.extraArgs || [];
  const args = [script, '--dir', opts.dir || fixtureDir, ...extraArgs];
  return execFileSync('node', args, { encoding: 'utf-8' });
}

function runParsed(opts = {}) {
  return JSON.parse(run(opts));
}

function makeTmpDir(name) {
  const dirName = name || '2026-03-09_tmp-test-' + randomBytes(4).toString('hex');
  const dir = join(tmpdir(), dirName);
  mkdirSync(dir, { recursive: true });
  return dir;
}

describe('assemble-briefing-data', () => {

  it('exits with usage error when --dir is missing', () => {
    try {
      execFileSync('node', [script], { encoding: 'utf-8', stdio: 'pipe' });
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
    }
  });

  it('produces valid JSON with all top-level keys', () => {
    const result = runParsed();
    assert.ok(typeof result.meta === 'object', 'meta must be an object');
    assert.ok(typeof result.stats === 'object', 'stats must be an object');
    assert.ok(typeof result.keyword_data === 'object', 'keyword_data must be an object');
    assert.ok(typeof result.serp_data === 'object', 'serp_data must be an object');
    assert.ok(typeof result.content_analysis === 'object', 'content_analysis must be an object');
    assert.ok(typeof result.competitor_analysis === 'object', 'competitor_analysis must be an object');
    assert.ok(typeof result.qualitative === 'object', 'qualitative must be an object');
  });

  it('meta has correct base fields', () => {
    const result = runParsed();
    assert.equal(result.meta.seed_keyword, 'test keyword');
    assert.equal(result.meta.date, '2026-03-09');
    assert.equal(result.meta.current_year, 2026);
    assert.equal(result.meta.pipeline_version, '0.2.0');
  });

  it('meta new fields default to null when flags are omitted', () => {
    const result = runParsed();
    assert.equal(result.meta.market, null);
    assert.equal(result.meta.language, null);
    assert.equal(result.meta.user_domain, null);
    assert.equal(result.meta.business_context, null);
  });

  it('meta new flags are reflected in output when provided', () => {
    const result = runParsed({ extraArgs: [
      '--market', 'de',
      '--language', 'de',
      '--user-domain', 'example.com',
      '--business-context', 'Travel agency',
    ] });
    assert.equal(result.meta.market, 'de');
    assert.equal(result.meta.language, 'de');
    assert.equal(result.meta.user_domain, 'example.com');
    assert.equal(result.meta.business_context, 'Travel agency');
  });

  it('meta phase1_completed_at is a valid ISO timestamp', () => {
    const result = runParsed();
    assert.ok(typeof result.meta.phase1_completed_at === 'string', 'phase1_completed_at must be a string');
    const parsed = new Date(result.meta.phase1_completed_at);
    assert.ok(isNaN(parsed.getTime()) === false, 'phase1_completed_at must be a valid date');
    assert.ok(result.meta.phase1_completed_at.endsWith('Z'), 'phase1_completed_at must be UTC ISO string');
  });

  it('meta data_sources.competitor_urls populated from serp-processed.json', () => {
    const result = runParsed();
    assert.ok(Array.isArray(result.meta.data_sources.competitor_urls), 'competitor_urls must be an array');
    assert.deepEqual(result.meta.data_sources.competitor_urls, [
      'https://example.com/page',
      'https://test.de/page',
      'https://third.com/page',
    ]);
  });

  it('meta data_sources.location_code populated from serp-raw.json', () => {
    const result = runParsed();
    assert.equal(result.meta.data_sources.location_code, 2276);
  });

  it('meta data_sources.location_code is null when serp-raw.json is absent', () => {
    const dir = makeTmpDir();
    try {
      const result = runParsed({ dir });
      assert.equal(result.meta.data_sources.location_code, null);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('meta data_sources.competitor_urls is empty when no serp data', () => {
    const dir = makeTmpDir();
    try {
      const result = runParsed({ dir });
      assert.deepEqual(result.meta.data_sources.competitor_urls, []);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('extracts date from directory name pattern', () => {
    const dir = makeTmpDir('2025-12-01_some-keyword');
    try {
      // Write minimal serp file so seed_keyword is available
      writeFileSync(join(dir, 'serp-processed.json'), JSON.stringify({
        target_keyword: 'some keyword', competitors: [], serp_features: {},
        item_types_present: []
      }));
      const result = runParsed({ dir });
      assert.equal(result.meta.date, '2025-12-01');
      assert.equal(result.meta.current_year, 2025);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('cluster ranking computed by total search volume descending', () => {
    const result = runParsed();
    const clusters = result.keyword_data.clusters;
    assert.ok(Array.isArray(clusters), 'clusters must be an array');
    assert.ok(clusters.length > 0, 'must have clusters');

    // Verify sorted by total_search_volume desc
    for (let i = 1; i < clusters.length; i++) {
      assert.ok(
        clusters[i - 1].total_search_volume >= clusters[i].total_search_volume,
        'clusters must be sorted by total_search_volume desc'
      );
    }

    // Verify rank assignment
    for (let i = 0; i < clusters.length; i++) {
      assert.equal(clusters[i].rank, i + 1, 'rank must be 1-indexed sequential');
    }
  });

  it('cluster ranking uses filtered keywords when available', () => {
    const result = runParsed();
    const clusters = result.keyword_data.clusters;
    assert.equal(clusters[0].cluster_keyword, 'keyword tool');
    assert.equal(clusters[0].total_search_volume, 1800);
    assert.equal(clusters[0].rank, 1);
  });

  it('proof keywords consolidated from content-topics', () => {
    const result = runParsed();
    assert.ok(Array.isArray(result.content_analysis.proof_keywords), 'proof_keywords must be an array');
    assert.ok(result.content_analysis.proof_keywords.length > 0, 'must have proof keywords');
    const first = result.content_analysis.proof_keywords[0];
    assert.ok(typeof first.term === 'string');
    assert.ok(typeof first.document_frequency === 'number');
  });

  it('module frequency consolidated from page-structure', () => {
    const result = runParsed();
    assert.ok(Array.isArray(result.competitor_analysis.common_modules));
    assert.ok(Array.isArray(result.competitor_analysis.rare_modules));
    assert.deepEqual(result.competitor_analysis.common_modules, ['list']);
    assert.deepEqual(result.competitor_analysis.rare_modules, ['faq']);
  });

  it('section weights consolidated from content-topics', () => {
    const result = runParsed();
    assert.ok(Array.isArray(result.content_analysis.section_weights));
    assert.ok(result.content_analysis.section_weights.length > 0);
  });

  it('AIO data assembled from serp', () => {
    const result = runParsed();
    assert.ok(typeof result.serp_data.aio === 'object');
    assert.equal(result.serp_data.aio.present, true);
  });

  it('FAQ data assembled with priority from filter-keywords', () => {
    const result = runParsed();
    assert.ok(typeof result.faq_data === 'object');
    assert.ok(Array.isArray(result.faq_data.questions));
    assert.equal(result.faq_data.paa_source, 'serp');
    assert.ok(result.faq_data.questions.length > 0);
    const first = result.faq_data.questions[0];
    assert.ok(typeof first.question === 'string');
    assert.ok(typeof first.priority === 'string');
  });

  it('entity candidates assembled with prominence', () => {
    const result = runParsed();
    assert.ok(Array.isArray(result.content_analysis.entity_candidates));
    // Google entity should have prominence merged from entity-prominence.json
    const google = result.content_analysis.entity_candidates.find(e => e.term === 'google');
    assert.ok(google, 'must have google entity');
    assert.equal(google.prominence, '3/3');
    assert.equal(google.prominence_source, 'code');
  });

  // --- Stats summary tests ---

  it('stats has correct fields with full fixture data', () => {
    const result = runParsed();
    assert.ok(typeof result.stats === 'object', 'stats must be an object');
    assert.equal(result.stats.total_keywords, 10);
    assert.equal(result.stats.filtered_keywords, 8);
    assert.equal(result.stats.total_clusters, 3);
    assert.equal(result.stats.competitor_count, 3);
  });

  it('stats uses competitors-data count over serp count when available', () => {
    const dir = makeTmpDir();
    try {
      writeFileSync(join(dir, 'serp-processed.json'), JSON.stringify({
        target_keyword: 'stats test',
        competitors: [{ rank: 1 }, { rank: 2 }],
        serp_features: {},
        item_types_present: []
      }));
      writeFileSync(join(dir, 'competitors-data.json'), JSON.stringify({
        competitors: [{ rank: 1 }, { rank: 2 }, { rank: 3 }, { rank: 4 }, { rank: 5 }]
      }));
      const result = runParsed({ dir });
      assert.equal(result.stats.competitor_count, 5);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('stats falls back to serp competitors when competitors-data is absent', () => {
    const dir = makeTmpDir();
    try {
      writeFileSync(join(dir, 'serp-processed.json'), JSON.stringify({
        target_keyword: 'stats test',
        competitors: [{ rank: 1 }, { rank: 2 }],
        serp_features: {},
        item_types_present: []
      }));
      const result = runParsed({ dir });
      assert.equal(result.stats.competitor_count, 2);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('stats has zero values when no input files exist', () => {
    const dir = makeTmpDir();
    try {
      const result = runParsed({ dir });
      assert.equal(result.stats.total_keywords, 0);
      assert.equal(result.stats.filtered_keywords, 0);
      assert.equal(result.stats.total_clusters, 0);
      assert.equal(result.stats.competitor_count, 0);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('stats prefers keywords-filtered over keywords-processed', () => {
    const dir = makeTmpDir();
    try {
      writeFileSync(join(dir, 'keywords-processed.json'), JSON.stringify({
        seed_keyword: 'stats pref test',
        total_keywords: 20,
        clusters: [{ cluster_keyword: 'a' }, { cluster_keyword: 'b' }]
      }));
      writeFileSync(join(dir, 'keywords-filtered.json'), JSON.stringify({
        seed_keyword: 'stats pref test',
        total_keywords: 20,
        filtered_keywords: 15,
        clusters: [{ cluster_keyword: 'a' }, { cluster_keyword: 'b' }, { cluster_keyword: 'c' }]
      }));
      const result = runParsed({ dir });
      assert.equal(result.stats.total_keywords, 20);
      assert.equal(result.stats.filtered_keywords, 15);
      assert.equal(result.stats.total_clusters, 3);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });


  it('missing input files handled gracefully with null fields', () => {
    const dir = makeTmpDir();
    try {
      const result = runParsed({ dir });
      // All data sections should have null for missing inputs
      assert.equal(result.meta.seed_keyword, null);
      assert.deepEqual(result.keyword_data.clusters, []);
      assert.equal(result.serp_data.competitors, null);
      assert.equal(result.serp_data.serp_features, null);
      assert.equal(result.serp_data.aio, null);
      assert.equal(result.content_analysis.proof_keywords, null);
      assert.equal(result.content_analysis.entity_candidates, null);
      assert.equal(result.content_analysis.section_weights, null);
      assert.equal(result.content_analysis.content_format_signals, null);
      assert.equal(result.competitor_analysis.page_structures, null);
      assert.equal(result.competitor_analysis.common_modules, null);
      assert.equal(result.competitor_analysis.rare_modules, null);
      assert.equal(result.competitor_analysis.avg_word_count, null);
      assert.equal(result.faq_data, null);
      // Stats should have zeros
      assert.equal(result.stats.total_keywords, 0);
      assert.equal(result.stats.filtered_keywords, 0);
      assert.equal(result.stats.total_clusters, 0);
      assert.equal(result.stats.competitor_count, 0);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('all qualitative fields explicitly set to null', () => {
    const result = runParsed();
    assert.equal(result.qualitative.entity_clusters, null);
    assert.equal(result.qualitative.unique_angles, null);
    assert.equal(result.qualitative.content_format_recommendation, null);
    assert.equal(result.qualitative.geo_audit, null);
    assert.equal(result.qualitative.aio_strategy, null);
    assert.equal(result.qualitative.briefing, null);
  });

  it('writes briefing-data.json to the output directory', () => {
    const dir = makeTmpDir();
    try {
      // Write a minimal file
      writeFileSync(join(dir, 'serp-processed.json'), JSON.stringify({
        target_keyword: 'output test', competitors: [], serp_features: {},
        item_types_present: []
      }));
      run({ dir });
      const outputPath = join(dir, 'briefing-data.json');
      assert.ok(existsSync(outputPath), 'briefing-data.json must be written');
      const written = JSON.parse(readFileSync(outputPath, 'utf-8'));
      assert.equal(written.meta.seed_keyword, 'output test');
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('year normalization replaces 2024/2025 with current year', () => {
    const result = runParsed();
    const jsonStr = JSON.stringify(result);
    // The fixture has "2024" and "2025" in competitor titles/timestamps and AIO text
    // They should be replaced with 2026 (current year from dir name)
    assert.ok(jsonStr.includes('2026'), 'must contain current year');
    // Check specific fields
    const aioText = result.serp_data.aio.text;
    assert.ok(aioText.includes('2026'), 'AIO text year must be normalized');
    assert.ok(aioText.includes('2024') === false, 'AIO text must not contain 2024');
  });

  it('year normalization in competitors', () => {
    const result = runParsed();
    const comp = result.serp_data.competitors[0];
    // Title had "2025" -> should be "2026"
    assert.ok(comp.title.includes('2026'), 'competitor title year must be normalized');
    assert.ok(comp.title.includes('2025') === false, 'competitor title must not contain 2025');
  });

  it('avg_word_count from page-structure', () => {
    const result = runParsed();
    assert.equal(result.competitor_analysis.avg_word_count, 2100);
  });

  it('keyword_data has correct totals', () => {
    const result = runParsed();
    assert.equal(result.keyword_data.total_keywords, 10);
    assert.equal(result.keyword_data.filtered_count, 8);
    assert.ok(typeof result.keyword_data.removal_summary === 'object');
    assert.equal(result.keyword_data.removal_summary.brand, 1);
  });

  it('serp_features is a summary of feature presence', () => {
    const result = runParsed();
    const sf = result.serp_data.serp_features;
    assert.equal(sf.ai_overview, true);
    assert.equal(sf.featured_snippet, false);
    assert.equal(sf.knowledge_graph, false);
    assert.equal(sf.people_also_ask, true);
  });

  it('page_structures from page-structure.json', () => {
    const result = runParsed();
    assert.ok(Array.isArray(result.competitor_analysis.page_structures));
    assert.equal(result.competitor_analysis.page_structures.length, 3);
  });

  it('content_format_signals from content-topics', () => {
    const result = runParsed();
    const cfs = result.content_analysis.content_format_signals;
    assert.equal(cfs.pages_with_numbered_lists, 1);
    assert.equal(cfs.pages_with_faq, 1);
    assert.equal(cfs.pages_with_tables, 2);
    assert.equal(cfs.avg_h2_count, 4.3);
    assert.equal(cfs.dominant_pattern, null);
  });

  it('produces identical output on repeated runs except for phase1_completed_at (determinism)', () => {
    const result1 = runParsed();
    const result2 = runParsed();
    // phase1_completed_at is a live timestamp and will differ between runs; exclude it
    delete result1.meta.phase1_completed_at;
    delete result2.meta.phase1_completed_at;
    assert.deepEqual(result1, result2, 'same inputs must produce identical output (excluding timestamp)');
  });

  it('works with only serp-processed.json present', () => {
    const dir = makeTmpDir();
    try {
      writeFileSync(join(dir, 'serp-processed.json'), JSON.stringify({
        target_keyword: 'partial test',
        se_results_count: 100,
        location_code: 2276,
        language_code: 'de',
        item_types_present: ['organic'],
        serp_features: {
          ai_overview: { present: false },
          featured_snippet: { present: false },
          people_also_ask: [],
          knowledge_graph: { present: false },
          commercial_signals: { paid_ads_present: false, shopping_present: false, commercial_units_present: false, popular_products_present: false },
          local_signals: { local_pack_present: false, map_present: false, hotels_pack_present: false },
        },
        competitors: [
          { rank: 1, url: 'https://a.com', domain: 'a.com', title: 'A' }
        ]
      }));
      const result = runParsed({ dir });
      assert.equal(result.meta.seed_keyword, 'partial test');
      assert.ok(Array.isArray(result.serp_data.competitors));
      assert.equal(result.content_analysis.proof_keywords, null);
      assert.equal(result.faq_data, null);
      // Stats should reflect serp-only state
      assert.equal(result.stats.total_keywords, 0);
      assert.equal(result.stats.competitor_count, 1);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('works with only keywords-processed.json present', () => {
    const dir = makeTmpDir();
    try {
      writeFileSync(join(dir, 'keywords-processed.json'), JSON.stringify({
        seed_keyword: 'kw only test',
        total_keywords: 2,
        total_clusters: 1,
        clusters: [
          { cluster_keyword: 'kw only', cluster_label: null, keyword_count: 2, keywords: [
            { keyword: 'kw only', search_volume: 100, difficulty: 10 },
            { keyword: 'kw only test', search_volume: 50, difficulty: 5 }
          ]}
        ]
      }));
      const result = runParsed({ dir });
      assert.equal(result.meta.seed_keyword, 'kw only test');
      assert.ok(Array.isArray(result.keyword_data.clusters));
      assert.equal(result.keyword_data.clusters.length, 1);
      assert.equal(result.keyword_data.clusters[0].total_search_volume, 150);
      assert.equal(result.serp_data.competitors, null);
      // Stats should reflect keywords-only state
      assert.equal(result.stats.total_keywords, 2);
      assert.equal(result.stats.total_clusters, 1);
      assert.equal(result.stats.competitor_count, 0);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

});
