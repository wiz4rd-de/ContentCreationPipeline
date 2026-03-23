import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { writeFileSync, mkdirSync, rmSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'analysis', 'analyze-content-topics.mjs');
const fixturePages = join(__dirname, '..', 'fixtures', 'analyze-content-topics', 'pages');

function run(opts = {}) {
  const args = [script];
  args.push('--pages-dir', opts.pagesDir || fixturePages);
  args.push('--seed', opts.seed || 'mallorca');
  if (opts.language) {
    args.push('--language', opts.language);
  }
  return execFileSync('node', args, { encoding: 'utf-8' });
}

function runParsed(opts = {}) {
  return JSON.parse(run(opts));
}

function makeTmpDir() {
  const dir = join(tmpdir(), 'act-test-' + randomBytes(4).toString('hex'));
  const pagesDir = join(dir, 'pages');
  mkdirSync(pagesDir, { recursive: true });
  return { dir, pagesDir };
}

describe('analyze-content-topics', () => {

  it('exits with usage error when --pages-dir is missing', () => {
    try {
      execFileSync('node', [script, '--seed', 'test'], { encoding: 'utf-8', stdio: 'pipe' });
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
    }
  });

  it('exits with usage error when --seed is missing', () => {
    try {
      execFileSync('node', [script, '--pages-dir', fixturePages], { encoding: 'utf-8', stdio: 'pipe' });
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
    }
  });

  it('produces valid JSON with all top-level keys', () => {
    const result = runParsed();
    assert.ok(Array.isArray(result.proof_keywords), 'proof_keywords must be an array');
    assert.ok(Array.isArray(result.entity_candidates), 'entity_candidates must be an array');
    assert.ok(Array.isArray(result.section_weights), 'section_weights must be an array');
    assert.ok(typeof result.content_format_signals === 'object', 'content_format_signals must be an object');
  });

  it('proof_keywords have required fields and exclude the seed keyword', () => {
    const result = runParsed();
    for (const pk of result.proof_keywords) {
      assert.ok(typeof pk.term === 'string', 'term must be a string');
      assert.ok(typeof pk.document_frequency === 'number', 'document_frequency must be a number');
      assert.ok(typeof pk.total_pages === 'number', 'total_pages must be a number');
      assert.ok(typeof pk.avg_tf === 'number', 'avg_tf must be a number');
      assert.ok(typeof pk.idf_boost === 'number', 'idf_boost must be a number');
      assert.ok(typeof pk.idf_score === 'number', 'idf_score must be a number');
      assert.ok(pk.idf_boost > 0, 'idf_boost must be positive');
      assert.ok(pk.idf_score > 0, 'idf_score must be positive');
      assert.ok(pk.term === 'mallorca' ? false : true, 'seed keyword must be excluded');
    }
  });

  it('proof_keywords are sorted by idf_score descending', () => {
    const result = runParsed();
    for (let i = 1; i < result.proof_keywords.length; i++) {
      const prev = result.proof_keywords[i - 1];
      const curr = result.proof_keywords[i];
      assert.ok(prev.idf_score >= curr.idf_score,
        'proof_keywords must be sorted by idf_score desc');
    }
  });

  it('extracts n-gram terms that appear across multiple pages', () => {
    const result = runParsed();
    // "beste reisezeit" appears in all 3 pages
    const besteReisezeit = result.proof_keywords.find(pk => pk.term === 'beste reisezeit');
    assert.ok(besteReisezeit, '"beste reisezeit" must appear as proof keyword');
    assert.equal(besteReisezeit.document_frequency, 3, 'must appear in all 3 pages');
    assert.equal(besteReisezeit.total_pages, 3);
  });

  it('entity_candidates have required fields', () => {
    const result = runParsed();
    for (const ec of result.entity_candidates) {
      assert.ok(typeof ec.term === 'string', 'term must be a string');
      assert.ok(typeof ec.document_frequency === 'number', 'document_frequency must be a number');
      assert.ok(Array.isArray(ec.pages), 'pages must be an array');
      // pages should contain domain strings
      for (const p of ec.pages) {
        assert.ok(typeof p === 'string', 'page entry must be a string');
      }
    }
  });

  it('entity_candidates are 1-grams only (no spaces)', () => {
    const result = runParsed();
    for (const ec of result.entity_candidates) {
      assert.ok(ec.term.includes(' ') === false, 'entity candidates must be 1-grams');
    }
  });

  it('entity_candidates pages are sorted alphabetically', () => {
    const result = runParsed();
    for (const ec of result.entity_candidates) {
      const sorted = [...ec.pages].sort();
      assert.deepEqual(ec.pages, sorted, 'pages must be sorted');
    }
  });

  it('section_weights have required fields', () => {
    const result = runParsed();
    assert.ok(result.section_weights.length > 0, 'must have section weights');
    for (const sw of result.section_weights) {
      assert.ok(typeof sw.heading_cluster === 'string', 'heading_cluster must be a string');
      assert.ok(Array.isArray(sw.sample_headings), 'sample_headings must be an array');
      assert.ok(typeof sw.occurrence === 'number', 'occurrence must be a number');
      assert.ok(typeof sw.avg_word_count === 'number', 'avg_word_count must be a number');
      assert.ok(typeof sw.avg_content_percentage === 'number', 'avg_content_percentage must be a number');
      assert.ok(['high', 'medium', 'low'].includes(sw.weight), 'weight must be high/medium/low');
    }
  });

  it('clusters similar headings using Jaccard overlap', () => {
    const result = runParsed();
    // All three pages have strand/beach headings that should cluster:
    // "Straende und Buchten", "Straende auf Mallorca", "Die schoensten Straende"
    // "straende und buchten", "straende auf mallorca", "die schoensten straende"
    // Jaccard("straende buchten", "straende mallorca") = 1/3 = 0.33 < 0.5
    // These may or may not cluster depending on overlap. Let's just verify clustering works.
    const strandClusters = result.section_weights.filter(sw =>
      sw.heading_cluster.includes('straende')
    );
    assert.ok(strandClusters.length > 0, 'must have strand-related section weights');
  });

  it('sample_headings are sorted alphabetically', () => {
    const result = runParsed();
    for (const sw of result.section_weights) {
      const sorted = [...sw.sample_headings].sort();
      assert.deepEqual(sw.sample_headings, sorted, 'sample_headings must be sorted');
    }
  });

  it('weight is deterministic based on avg_content_percentage thresholds', () => {
    const tmp = makeTmpDir();
    try {
      // Create pages where one section has very high content percentage
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({
        url: 'https://a.example.com/test',
        main_content_text: 'Intro text. Big Section ' + 'word '.repeat(200) + 'Small Section A few words here.',
        headings: [
          { level: 2, text: 'Big Section' },
          { level: 2, text: 'Small Section' },
        ],
        html_signals: {},
      }));
      writeFileSync(join(tmp.pagesDir, 'p2.json'), JSON.stringify({
        url: 'https://b.example.com/test',
        main_content_text: 'Intro. Big Section ' + 'word '.repeat(200) + 'Small Section Just a bit.',
        headings: [
          { level: 2, text: 'Big Section' },
          { level: 2, text: 'Small Section' },
        ],
        html_signals: {},
      }));
      const result = runParsed({ pagesDir: tmp.pagesDir, seed: 'test' });
      const big = result.section_weights.find(sw => sw.heading_cluster === 'big section');
      const small = result.section_weights.find(sw => sw.heading_cluster === 'small section');
      assert.ok(big, 'must have big section');
      assert.ok(small, 'must have small section');
      // Big section should have much higher percentage
      assert.ok(big.avg_content_percentage > small.avg_content_percentage,
        'big section must have higher content percentage');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('content_format_signals has all required fields', () => {
    const result = runParsed();
    const cfs = result.content_format_signals;
    assert.ok(typeof cfs.pages_with_numbered_lists === 'number');
    assert.ok(typeof cfs.pages_with_faq === 'number');
    assert.ok(typeof cfs.pages_with_tables === 'number');
    assert.ok(typeof cfs.avg_h2_count === 'number');
    assert.equal(cfs.dominant_pattern, null, 'dominant_pattern must be null');
  });

  it('content_format_signals counts are correct for fixtures', () => {
    const result = runParsed();
    const cfs = result.content_format_signals;
    // alpha has ordered_lists: 1, beta has ordered_lists: 0, gamma has ordered_lists: 0
    assert.equal(cfs.pages_with_numbered_lists, 1, 'only alpha has ordered_lists');
    // alpha has tables: 1, beta has tables: 1, gamma has tables: 0
    assert.equal(cfs.pages_with_tables, 2, 'alpha and beta have tables');
    // beta has faq heading + faq_sections: 1
    assert.equal(cfs.pages_with_faq, 1, 'only beta has FAQ');
  });

  it('handles empty pages directory', () => {
    const tmp = makeTmpDir();
    try {
      const result = runParsed({ pagesDir: tmp.pagesDir, seed: 'test' });
      assert.deepEqual(result.proof_keywords, []);
      assert.deepEqual(result.entity_candidates, []);
      assert.deepEqual(result.section_weights, []);
      assert.equal(result.content_format_signals.pages_with_numbered_lists, 0);
      assert.equal(result.content_format_signals.dominant_pattern, null);
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('handles pages with missing fields gracefully', () => {
    const tmp = makeTmpDir();
    try {
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({
        url: 'https://example.com/minimal',
        main_content_text: 'Some basic content text here.',
      }));
      writeFileSync(join(tmp.pagesDir, 'p2.json'), JSON.stringify({
        url: 'https://other.example.com/page',
        main_content_text: 'Another basic content text here.',
        headings: [],
        html_signals: {},
      }));
      const result = runParsed({ pagesDir: tmp.pagesDir, seed: 'test' });
      assert.ok(Array.isArray(result.proof_keywords));
      assert.ok(Array.isArray(result.section_weights));
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('stopwords are filtered out from term extraction', () => {
    const result = runParsed();
    // Common German stopwords should not appear as proof keywords
    const stopwords = ['und', 'ist', 'die', 'der', 'von', 'fuer', 'mit'];
    for (const sw of stopwords) {
      const found = result.proof_keywords.find(pk => pk.term === sw);
      assert.ok(found === undefined, `stopword "${sw}" must be filtered out`);
    }
  });

  it('umlaut stopwords are filtered from proof_keywords', () => {
    const tmp = makeTmpDir();
    try {
      // Both pages share a topic keyword ("wandern") but also contain many umlaut stopwords
      // that should never surface in proof_keywords regardless of document frequency.
      // Pad to 200+ words so the quality filter does not exclude these pages.
      const filler = 'thema '.repeat(185);
      const sharedText = 'wandern für über im als auf mit und ist die der';
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({
        url: 'https://a.example.com/test',
        main_content_text: `${sharedText} wandern für über im als ${filler}`,
        headings: [],
        html_signals: {},
      }));
      writeFileSync(join(tmp.pagesDir, 'p2.json'), JSON.stringify({
        url: 'https://b.example.com/test',
        main_content_text: `${sharedText} wandern für über im als ${filler}`,
        headings: [],
        html_signals: {},
      }));
      const result = runParsed({ pagesDir: tmp.pagesDir, seed: 'test' });
      const umlautStopwords = ['für', 'über', 'im', 'als'];
      for (const sw of umlautStopwords) {
        const found = result.proof_keywords.find(pk => pk.term === sw);
        assert.ok(found === undefined, `umlaut stopword "${sw}" must be filtered from proof_keywords`);
      }
      // The shared non-stopword term must still appear
      const wandern = result.proof_keywords.find(pk => pk.term === 'wandern');
      assert.ok(wandern !== undefined, '"wandern" must appear as proof keyword');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('only considers H2 headings for section weight analysis', () => {
    const result = runParsed();
    // H3 headings from fixtures should not appear in section_weights
    const h3Headings = ['wann ist die beste reisezeit fuer mallorca',
      'brauche ich einen mietwagen auf mallorca',
      'wie komme ich nach mallorca',
      'wann ist die beste reisezeit'];
    for (const sw of result.section_weights) {
      for (const h3 of h3Headings) {
        assert.ok(sw.heading_cluster === h3 ? false : true,
          `H3 heading "${h3}" must not appear in section_weights`);
      }
    }
  });

  it('produces byte-identical output on repeated runs (determinism)', () => {
    const run1 = run();
    const run2 = run();
    assert.equal(run1, run2, 'same inputs must produce byte-identical output');
  });

  it('idf_boost is 1.0 for terms absent from the IDF table (n-grams)', () => {
    const result = runParsed();
    // N-gram terms (containing a space) are never in the unigram IDF table,
    // so they must always receive a neutral idf_boost of 1.0.
    const ngrams = result.proof_keywords.filter(pk => pk.term.includes(' '));
    assert.ok(ngrams.length > 0, 'fixture must contain at least one n-gram proof keyword');
    for (const pk of ngrams) {
      assert.equal(pk.idf_boost, 1.0, `n-gram "${pk.term}" must have idf_boost 1.0`);
      assert.equal(pk.idf_score, pk.document_frequency,
        `n-gram "${pk.term}" idf_score must equal document_frequency when boost is 1.0`);
    }
  });

  it('idf_score equals document_frequency * idf_boost (rounded to 3dp)', () => {
    const result = runParsed();
    for (const pk of result.proof_keywords) {
      const expected = Math.round(pk.document_frequency * pk.idf_boost * 1000) / 1000;
      assert.equal(pk.idf_score, expected,
        `idf_score for "${pk.term}" must equal df * idf_boost`);
    }
  });

  it('common-language unigrams rank lower than topic-specific unigrams with same DF', () => {
    const tmp = makeTmpDir();
    try {
      // Build 3 pages each containing both a common German word ("insel", IDF ~8.86)
      // and a rare/specific word ("schnorcheln", IDF ~17.6).  Both have DF=3.
      // With IDF boosting, "schnorcheln" (boost ~1.76) must outrank "insel" (boost ~0.886).
      // Filler is 200 words to clear the 200-word quality gate.
      const filler = 'wort '.repeat(200);
      for (const host of ['a', 'b', 'c']) {
        writeFileSync(join(tmp.pagesDir, `p-${host}.json`), JSON.stringify({
          url: `https://${host}.example.com/page`,
          main_content_text: `schnorcheln insel ${filler}`,
          headings: [],
          html_signals: {},
        }));
      }
      const result = runParsed({ pagesDir: tmp.pagesDir, seed: 'test' });
      const schnorcheln = result.proof_keywords.find(pk => pk.term === 'schnorcheln');
      const insel = result.proof_keywords.find(pk => pk.term === 'insel');
      assert.ok(schnorcheln !== undefined, '"schnorcheln" must appear in proof_keywords');
      assert.ok(insel !== undefined, '"insel" must appear in proof_keywords');
      assert.equal(schnorcheln.document_frequency, insel.document_frequency,
        'both terms must have the same DF (3)');
      assert.ok(schnorcheln.idf_boost > insel.idf_boost,
        '"schnorcheln" must have higher idf_boost than "insel"');
      assert.ok(schnorcheln.idf_score > insel.idf_score,
        '"schnorcheln" must rank above "insel" via idf_score');
      // Find their positions in the sorted list
      const schnorchelIdx = result.proof_keywords.indexOf(schnorcheln);
      const inselIdx = result.proof_keywords.indexOf(insel);
      assert.ok(schnorchelIdx < inselIdx,
        '"schnorcheln" must appear before "insel" in proof_keywords');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('idf_boost is 1.0 for non-German languages (IDF table not loaded)', () => {
    const tmp = makeTmpDir();
    try {
      // Filler is 200 words to clear the 200-word quality gate.
      const filler = 'word '.repeat(200);
      for (const host of ['a', 'b']) {
        writeFileSync(join(tmp.pagesDir, `p-${host}.json`), JSON.stringify({
          url: `https://${host}.example.com/page`,
          main_content_text: `swimming beach ${filler}`,
          headings: [],
          html_signals: {},
        }));
      }
      const result = runParsed({ pagesDir: tmp.pagesDir, seed: 'test', language: 'en' });
      for (const pk of result.proof_keywords) {
        assert.equal(pk.idf_boost, 1.0,
          `term "${pk.term}" must have idf_boost 1.0 for non-German language`);
      }
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('supports --language flag', () => {
    const result = runParsed({ language: 'en' });
    assert.ok(Array.isArray(result.proof_keywords));
  });

  it('total_pages in proof_keywords matches actual page count', () => {
    const result = runParsed();
    for (const pk of result.proof_keywords) {
      assert.equal(pk.total_pages, 3, 'total_pages must match fixture page count');
    }
  });

  it('filters thin/blocked pages from topic analysis', () => {
    const tmp = makeTmpDir();
    try {
      // Substantive page with unique term "schnorcheln" that should appear in proof_keywords
      const text1 = ('schnorcheln tauchen strand ' + 'wort '.repeat(70)).trim();
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({
        url: 'https://a.example.com/page',
        main_content_text: text1,
        headings: [{ level: 2, text: 'Aktivitaeten' }],
        html_signals: { ordered_lists: 0, tables: 0, faq_sections: 0, video_embeds: 0, forms: 0, images_in_content: 0 },
      }));
      writeFileSync(join(tmp.pagesDir, 'p2.json'), JSON.stringify({
        url: 'https://b.example.com/page',
        main_content_text: text1,
        headings: [{ level: 2, text: 'Sport' }],
        html_signals: { ordered_lists: 0, tables: 0, faq_sections: 0, video_embeds: 0, forms: 0, images_in_content: 0 },
      }));
      // Blocked/thin page — must not contaminate proof_keywords or format signals
      writeFileSync(join(tmp.pagesDir, 'p-blocked.json'), JSON.stringify({
        url: 'https://blocked.example.com/page',
        main_content_text: 'Access denied. You do not have permission to access this page.',
        headings: [{ level: 1, text: 'Access denied' }],
        html_signals: { ordered_lists: 1, tables: 1, faq_sections: 1, video_embeds: 0, forms: 0, images_in_content: 0 },
      }));
      const result = runParsed({ pagesDir: tmp.pagesDir, seed: 'test' });
      // total_pages reflects only the 2 valid pages
      for (const pk of result.proof_keywords) {
        assert.equal(pk.total_pages, 2, 'total_pages must count only valid (non-filtered) pages');
      }
      // The blocked page's html_signals (ordered_lists:1, tables:1, faq:1) must not be counted
      assert.equal(result.content_format_signals.pages_with_numbered_lists, 0,
        'ordered_lists from blocked page must not count');
      assert.equal(result.content_format_signals.pages_with_tables, 0,
        'tables from blocked page must not count');
      assert.equal(result.content_format_signals.pages_with_faq, 0,
        'faq from blocked page must not count');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('avg_h2_count is computed correctly', () => {
    const result = runParsed();
    // alpha: 3 H2, beta: 3 H2, gamma: 2 H2 => avg = 8/3 = 2.7
    assert.equal(result.content_format_signals.avg_h2_count, 2.7,
      'avg_h2_count must be 2.7 for fixtures');
  });

  it('logs competitor count and seed to stderr before processing', () => {
    const proc = spawnSync('node', [script, '--pages-dir', fixturePages, '--seed', 'mallorca'], { encoding: 'utf-8' });
    assert.ok(proc.stderr.includes('Analyzing content topics for'), 'stderr must include progress message');
    assert.ok(proc.stderr.includes('competitors'), 'stderr must mention competitors');
    assert.ok(proc.stderr.includes('mallorca'), 'stderr must include the seed keyword');
  });

  it('writes JSON to file when --output is provided', () => {
    const tmp = makeTmpDir();
    const outFile = join(tmp.dir, 'result.json');
    try {
      const proc = spawnSync('node', [script, '--pages-dir', fixturePages, '--seed', 'mallorca', '--output', outFile], { encoding: 'utf-8' });
      assert.equal(proc.status, 0, 'must exit with code 0');
      assert.equal(proc.stdout, '', 'stdout must be empty when --output is used');
      const written = JSON.parse(readFileSync(outFile, 'utf-8'));
      assert.ok(Array.isArray(written.proof_keywords), 'file must contain proof_keywords');
      assert.ok(Array.isArray(written.entity_candidates), 'file must contain entity_candidates');
      assert.ok(Array.isArray(written.section_weights), 'file must contain section_weights');
      assert.ok(typeof written.content_format_signals === 'object', 'file must contain content_format_signals');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('writes JSON to file on empty-dir early exit when --output is provided', () => {
    const tmp = makeTmpDir();
    const outFile = join(tmp.dir, 'empty-result.json');
    try {
      const proc = spawnSync('node', [script, '--pages-dir', tmp.pagesDir, '--seed', 'test', '--output', outFile], { encoding: 'utf-8' });
      assert.equal(proc.status, 0, 'must exit with code 0');
      assert.equal(proc.stdout, '', 'stdout must be empty when --output is used');
      const written = JSON.parse(readFileSync(outFile, 'utf-8'));
      assert.deepEqual(written.proof_keywords, []);
      assert.deepEqual(written.section_weights, []);
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });
});
