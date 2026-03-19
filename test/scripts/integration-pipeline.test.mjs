import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { writeFileSync, readFileSync, mkdirSync, rmSync, cpSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(__dirname, '..', '..');
const fixtures = join(__dirname, '..', 'fixtures', 'integration');

// Script paths
const processKeywords = join(projectRoot, 'src', 'keywords', 'process-keywords.mjs');
const processSerp = join(projectRoot, 'src', 'serp', 'process-serp.mjs');
const filterKeywords = join(projectRoot, 'src', 'keywords', 'filter-keywords.mjs');
const analyzePageStructure = join(projectRoot, 'src', 'analysis', 'analyze-page-structure.mjs');
const analyzeContentTopics = join(projectRoot, 'src', 'analysis', 'analyze-content-topics.mjs');
const assembleBriefingData = join(projectRoot, 'src', 'analysis', 'assemble-briefing-data.mjs');

const SEED = 'mallorca urlaub';

function makeTmpDir() {
  const dir = join(tmpdir(), '2026-03-19_integration-' + randomBytes(4).toString('hex'));
  mkdirSync(dir, { recursive: true });
  return dir;
}

function runScript(script, args) {
  return execFileSync('node', [script, ...args], {
    encoding: 'utf-8',
    stdio: ['pipe', 'pipe', 'pipe'],
  });
}

describe('integration: full pipeline end-to-end', () => {
  let tmpDir;
  let keywordsProcessedOutput;
  let serpProcessedOutput;
  let keywordsFilteredOutput;
  let pageStructureOutput;
  let contentTopicsOutput;
  let briefingData;

  it('runs the full pipeline and produces valid briefing-data.json', () => {
    tmpDir = makeTmpDir();
    try {
      // --- Stage 1: process-keywords ---
      const kwStdout = runScript(processKeywords, [
        '--related', join(fixtures, 'keywords-related-raw.json'),
        '--suggestions', join(fixtures, 'keywords-suggestions-raw.json'),
        '--seed', SEED,
      ]);
      keywordsProcessedOutput = JSON.parse(kwStdout);

      assert.equal(keywordsProcessedOutput.seed_keyword, SEED);
      assert.ok(keywordsProcessedOutput.total_keywords >= 3, 'should have at least 3 deduplicated keywords');
      assert.ok(Array.isArray(keywordsProcessedOutput.clusters), 'clusters must be an array');
      assert.ok(keywordsProcessedOutput.clusters.length > 0, 'must have at least 1 cluster');

      // Write output for next stage
      writeFileSync(join(tmpDir, 'keywords-processed.json'), kwStdout);

      // --- Stage 2: process-serp ---
      const serpStdout = runScript(processSerp, [
        join(fixtures, 'serp-raw.json'),
      ]);
      serpProcessedOutput = JSON.parse(serpStdout);

      assert.equal(serpProcessedOutput.target_keyword, SEED);
      assert.ok(Array.isArray(serpProcessedOutput.competitors), 'competitors must be an array');
      assert.ok(serpProcessedOutput.competitors.length >= 3, 'should have at least 3 competitors');
      assert.ok(typeof serpProcessedOutput.serp_features === 'object', 'serp_features must be an object');

      // Write output for next stage
      writeFileSync(join(tmpDir, 'serp-processed.json'), serpStdout);

      // Copy serp-raw.json for assemble-briefing-data (it reads location_code from it)
      cpSync(join(fixtures, 'serp-raw.json'), join(tmpDir, 'serp-raw.json'));

      // --- Stage 3: filter-keywords ---
      const filterStdout = runScript(filterKeywords, [
        '--keywords', join(tmpDir, 'keywords-processed.json'),
        '--serp', join(tmpDir, 'serp-processed.json'),
        '--seed', SEED,
      ]);
      keywordsFilteredOutput = JSON.parse(filterStdout);

      assert.equal(keywordsFilteredOutput.seed_keyword, SEED);
      assert.ok(keywordsFilteredOutput.total_keywords > 0, 'must have keywords');
      assert.equal(
        keywordsFilteredOutput.total_keywords,
        keywordsFilteredOutput.filtered_keywords + keywordsFilteredOutput.removed_count,
        'total = filtered + removed',
      );
      assert.ok(Array.isArray(keywordsFilteredOutput.clusters), 'filtered clusters must be an array');
      assert.ok(Array.isArray(keywordsFilteredOutput.faq_selection), 'faq_selection must be an array');

      // Every keyword must have filter_status
      for (const cluster of keywordsFilteredOutput.clusters) {
        for (const kw of cluster.keywords) {
          assert.ok(
            kw.filter_status === 'keep' || kw.filter_status === 'removed',
            `keyword "${kw.keyword}" must have valid filter_status`,
          );
        }
      }

      writeFileSync(join(tmpDir, 'keywords-filtered.json'), filterStdout);

      // --- Stage 4: analyze-page-structure ---
      const pagesDir = join(fixtures, 'pages');
      const psStdout = runScript(analyzePageStructure, [
        '--pages-dir', pagesDir,
      ]);
      pageStructureOutput = JSON.parse(psStdout);

      assert.ok(Array.isArray(pageStructureOutput.competitors), 'page structure competitors must be an array');
      assert.ok(pageStructureOutput.competitors.length > 0, 'must have analyzed competitors');
      assert.ok(typeof pageStructureOutput.cross_competitor === 'object', 'cross_competitor must be an object');
      assert.ok(Array.isArray(pageStructureOutput.cross_competitor.common_modules), 'common_modules must be an array');
      assert.ok(typeof pageStructureOutput.cross_competitor.avg_word_count === 'number', 'avg_word_count must be a number');

      writeFileSync(join(tmpDir, 'page-structure.json'), psStdout);

      // --- Stage 5: analyze-content-topics ---
      const ctStdout = runScript(analyzeContentTopics, [
        '--pages-dir', pagesDir,
        '--seed', SEED,
      ]);
      contentTopicsOutput = JSON.parse(ctStdout);

      assert.ok(Array.isArray(contentTopicsOutput.proof_keywords), 'proof_keywords must be an array');
      assert.ok(Array.isArray(contentTopicsOutput.entity_candidates), 'entity_candidates must be an array');
      assert.ok(Array.isArray(contentTopicsOutput.section_weights), 'section_weights must be an array');
      assert.ok(typeof contentTopicsOutput.content_format_signals === 'object', 'content_format_signals must be an object');

      writeFileSync(join(tmpDir, 'content-topics.json'), ctStdout);

      // --- Stage 6: assemble-briefing-data ---
      const bdStdout = runScript(assembleBriefingData, [
        '--dir', tmpDir,
      ]);
      briefingData = JSON.parse(bdStdout);

      // --- Verify briefing-data.json top-level keys ---
      const requiredKeys = [
        'meta', 'stats', 'keyword_data', 'serp_data',
        'content_analysis', 'competitor_analysis', 'faq_data', 'qualitative',
      ];
      for (const key of requiredKeys) {
        assert.ok(key in briefingData, `briefing-data.json must have key: ${key}`);
      }

      // --- Verify meta ---
      assert.equal(briefingData.meta.seed_keyword, SEED);
      assert.equal(briefingData.meta.date, '2026-03-19');
      assert.ok(typeof briefingData.meta.phase1_completed_at === 'string');

      // --- Verify keyword_data flows from process-keywords -> filter-keywords ---
      assert.ok(Array.isArray(briefingData.keyword_data.clusters));
      assert.ok(briefingData.keyword_data.clusters.length > 0);
      assert.ok(briefingData.keyword_data.total_keywords > 0);

      // --- Verify serp_data flows from process-serp ---
      assert.ok(Array.isArray(briefingData.serp_data.competitors));
      assert.ok(briefingData.serp_data.competitors.length >= 3);
      assert.ok(typeof briefingData.serp_data.serp_features === 'object');

      // --- Verify content_analysis flows from analyze-content-topics ---
      assert.ok(Array.isArray(briefingData.content_analysis.proof_keywords));
      assert.ok(Array.isArray(briefingData.content_analysis.section_weights));
      assert.ok(typeof briefingData.content_analysis.content_format_signals === 'object');

      // --- Verify competitor_analysis flows from analyze-page-structure ---
      assert.ok(Array.isArray(briefingData.competitor_analysis.page_structures));
      assert.ok(typeof briefingData.competitor_analysis.avg_word_count === 'number');

      // --- Verify faq_data flows from filter-keywords ---
      assert.ok(typeof briefingData.faq_data === 'object');
      assert.ok(Array.isArray(briefingData.faq_data.questions));
      assert.ok(briefingData.faq_data.questions.length > 0);

      // --- Verify all qualitative fields are null ---
      assert.equal(briefingData.qualitative.entity_clusters, null);
      assert.equal(briefingData.qualitative.unique_angles, null);
      assert.equal(briefingData.qualitative.content_format_recommendation, null);
      assert.equal(briefingData.qualitative.geo_audit, null);
      assert.equal(briefingData.qualitative.aio_strategy, null);
      assert.equal(briefingData.qualitative.briefing, null);

      // --- Verify briefing-data.json was written to disk ---
      const diskData = JSON.parse(readFileSync(join(tmpDir, 'briefing-data.json'), 'utf-8'));
      assert.equal(diskData.meta.seed_keyword, SEED);

    } finally {
      if (tmpDir) {
        rmSync(tmpDir, { recursive: true, force: true });
      }
    }
  });

  it('each stage output is valid input for the next stage (contract verification)', () => {
    tmpDir = makeTmpDir();
    try {
      // Run full pipeline collecting intermediate outputs
      const kwStdout = runScript(processKeywords, [
        '--related', join(fixtures, 'keywords-related-raw.json'),
        '--suggestions', join(fixtures, 'keywords-suggestions-raw.json'),
        '--seed', SEED,
      ]);
      const kwParsed = JSON.parse(kwStdout);
      writeFileSync(join(tmpDir, 'keywords-processed.json'), kwStdout);

      const serpStdout = runScript(processSerp, [join(fixtures, 'serp-raw.json')]);
      const serpParsed = JSON.parse(serpStdout);
      writeFileSync(join(tmpDir, 'serp-processed.json'), serpStdout);

      // Verify process-keywords output has the fields filter-keywords expects
      assert.ok(Array.isArray(kwParsed.clusters), 'process-keywords must output clusters array');
      for (const cluster of kwParsed.clusters) {
        assert.ok(typeof cluster.cluster_keyword === 'string');
        assert.ok(Array.isArray(cluster.keywords));
        for (const kw of cluster.keywords) {
          assert.ok(typeof kw.keyword === 'string');
        }
      }

      // Verify process-serp output has fields filter-keywords needs (PAA)
      assert.ok(typeof serpParsed.serp_features === 'object');
      assert.ok(Array.isArray(serpParsed.serp_features.people_also_ask));

      // filter-keywords produces output assemble-briefing-data expects
      const filterStdout = runScript(filterKeywords, [
        '--keywords', join(tmpDir, 'keywords-processed.json'),
        '--serp', join(tmpDir, 'serp-processed.json'),
        '--seed', SEED,
      ]);
      const filterParsed = JSON.parse(filterStdout);

      assert.ok(typeof filterParsed.seed_keyword === 'string');
      assert.ok(typeof filterParsed.total_keywords === 'number');
      assert.ok(typeof filterParsed.filtered_keywords === 'number');
      assert.ok(typeof filterParsed.removal_summary === 'object');
      assert.ok(Array.isArray(filterParsed.faq_selection));

    } finally {
      if (tmpDir) {
        rmSync(tmpDir, { recursive: true, force: true });
      }
    }
  });

  it('pipeline produces deterministic output (excluding timestamp)', () => {
    const tmpDir1 = makeTmpDir();
    const tmpDir2 = makeTmpDir();
    try {
      function runFullPipeline(dir) {
        const kwStdout = runScript(processKeywords, [
          '--related', join(fixtures, 'keywords-related-raw.json'),
          '--suggestions', join(fixtures, 'keywords-suggestions-raw.json'),
          '--seed', SEED,
        ]);
        writeFileSync(join(dir, 'keywords-processed.json'), kwStdout);

        const serpStdout = runScript(processSerp, [join(fixtures, 'serp-raw.json')]);
        writeFileSync(join(dir, 'serp-processed.json'), serpStdout);
        cpSync(join(fixtures, 'serp-raw.json'), join(dir, 'serp-raw.json'));

        const filterStdout = runScript(filterKeywords, [
          '--keywords', join(dir, 'keywords-processed.json'),
          '--serp', join(dir, 'serp-processed.json'),
          '--seed', SEED,
        ]);
        writeFileSync(join(dir, 'keywords-filtered.json'), filterStdout);

        const psStdout = runScript(analyzePageStructure, [
          '--pages-dir', join(fixtures, 'pages'),
        ]);
        writeFileSync(join(dir, 'page-structure.json'), psStdout);

        const ctStdout = runScript(analyzeContentTopics, [
          '--pages-dir', join(fixtures, 'pages'),
          '--seed', SEED,
        ]);
        writeFileSync(join(dir, 'content-topics.json'), ctStdout);

        const bdStdout = runScript(assembleBriefingData, ['--dir', dir]);
        return JSON.parse(bdStdout);
      }

      const result1 = runFullPipeline(tmpDir1);
      const result2 = runFullPipeline(tmpDir2);

      // Exclude timestamps which differ between runs
      delete result1.meta.phase1_completed_at;
      delete result2.meta.phase1_completed_at;

      assert.deepEqual(result1, result2, 'full pipeline must produce deterministic output');
    } finally {
      rmSync(tmpDir1, { recursive: true, force: true });
      rmSync(tmpDir2, { recursive: true, force: true });
    }
  });

  it('stats summary reflects pipeline data correctly', () => {
    tmpDir = makeTmpDir();
    try {
      const kwStdout = runScript(processKeywords, [
        '--related', join(fixtures, 'keywords-related-raw.json'),
        '--suggestions', join(fixtures, 'keywords-suggestions-raw.json'),
        '--seed', SEED,
      ]);
      writeFileSync(join(tmpDir, 'keywords-processed.json'), kwStdout);

      const serpStdout = runScript(processSerp, [join(fixtures, 'serp-raw.json')]);
      writeFileSync(join(tmpDir, 'serp-processed.json'), serpStdout);
      cpSync(join(fixtures, 'serp-raw.json'), join(tmpDir, 'serp-raw.json'));

      const filterStdout = runScript(filterKeywords, [
        '--keywords', join(tmpDir, 'keywords-processed.json'),
        '--serp', join(tmpDir, 'serp-processed.json'),
        '--seed', SEED,
      ]);
      const filterParsed = JSON.parse(filterStdout);
      writeFileSync(join(tmpDir, 'keywords-filtered.json'), filterStdout);

      const psStdout = runScript(analyzePageStructure, [
        '--pages-dir', join(fixtures, 'pages'),
      ]);
      writeFileSync(join(tmpDir, 'page-structure.json'), psStdout);

      const ctStdout = runScript(analyzeContentTopics, [
        '--pages-dir', join(fixtures, 'pages'),
        '--seed', SEED,
      ]);
      writeFileSync(join(tmpDir, 'content-topics.json'), ctStdout);

      const bdStdout = runScript(assembleBriefingData, ['--dir', tmpDir]);
      const bd = JSON.parse(bdStdout);

      // Stats should reflect actual data
      assert.equal(bd.stats.total_keywords, filterParsed.total_keywords);
      assert.equal(bd.stats.filtered_keywords, filterParsed.filtered_keywords);
      assert.ok(bd.stats.total_clusters > 0);
      assert.equal(bd.stats.competitor_count, 3);
    } finally {
      if (tmpDir) {
        rmSync(tmpDir, { recursive: true, force: true });
      }
    }
  });
});
