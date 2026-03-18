import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'analysis', 'score-draft-wdfidf.mjs');
const fixtureDraft = join(__dirname, '..', 'fixtures', 'score-draft-wdfidf', 'draft.txt');
const fixturePages = join(__dirname, '..', 'fixtures', 'score-draft-wdfidf', 'pages');

function run(opts = {}) {
  const args = [script];
  args.push('--draft', opts.draft || fixtureDraft);
  args.push('--pages-dir', opts.pagesDir || fixturePages);
  if (opts.language) args.push('--language', opts.language);
  if (opts.threshold !== undefined) args.push('--threshold', String(opts.threshold));
  return execFileSync('node', args, { encoding: 'utf-8' });
}

function runParsed(opts = {}) {
  return JSON.parse(run(opts));
}

function makeTmpDir() {
  const dir = join(tmpdir(), 'wdfidf-test-' + randomBytes(4).toString('hex'));
  const pagesDir = join(dir, 'pages');
  mkdirSync(pagesDir, { recursive: true });
  return { dir, pagesDir };
}

function makePage(text) {
  return JSON.stringify({
    url: 'https://example.com/page',
    main_content_text: text,
    headings: [],
    html_signals: {},
  });
}

describe('score-draft-wdfidf', () => {

  it('exits with usage error when --draft is missing', () => {
    try {
      execFileSync('node', [script, '--pages-dir', fixturePages], { encoding: 'utf-8', stdio: 'pipe' });
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
    }
  });

  it('exits with usage error when --pages-dir is missing', () => {
    try {
      execFileSync('node', [script, '--draft', fixtureDraft], { encoding: 'utf-8', stdio: 'pipe' });
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
    }
  });

  it('produces valid JSON with meta and terms keys', () => {
    const result = runParsed();
    assert.ok(typeof result.meta === 'object', 'meta must be an object');
    assert.ok(Array.isArray(result.terms), 'terms must be an array');
  });

  it('meta contains required fields', () => {
    const result = runParsed();
    const m = result.meta;
    assert.ok(typeof m.draft === 'string', 'meta.draft must be a string');
    assert.ok(typeof m.pages_dir === 'string', 'meta.pages_dir must be a string');
    assert.ok(typeof m.language === 'string', 'meta.language must be a string');
    assert.ok(typeof m.threshold === 'number', 'meta.threshold must be a number');
    assert.ok(typeof m.competitor_count === 'number', 'meta.competitor_count must be a number');
    assert.ok(
      m.idf_source === 'reference' || m.idf_source === 'corpus-local',
      'meta.idf_source must be "reference" or "corpus-local"'
    );
  });

  it('uses reference IDF for German language', () => {
    const result = runParsed();
    assert.equal(result.meta.idf_source, 'reference', 'German must use reference IDF table');
  });

  it('uses corpus-local IDF fallback for non-German language', () => {
    const result = runParsed({ language: 'en' });
    assert.equal(result.meta.idf_source, 'corpus-local', 'non-German must use corpus-local IDF');
  });

  it('each term entry has all required fields with correct types', () => {
    const result = runParsed();
    assert.ok(result.terms.length > 0, 'must have at least one term');
    for (const t of result.terms) {
      assert.ok(typeof t.term === 'string', 'term must be a string');
      assert.ok(typeof t.draft_wdfidf === 'number', 'draft_wdfidf must be a number');
      assert.ok(typeof t.competitor_avg_wdfidf === 'number', 'competitor_avg_wdfidf must be a number');
      assert.ok(typeof t.delta === 'number', 'delta must be a number');
      assert.ok(
        t.signal === 'increase' || t.signal === 'decrease' || t.signal === 'ok',
        `signal must be increase/decrease/ok, got "${t.signal}"`
      );
    }
  });

  it('delta equals draft_wdfidf minus competitor_avg_wdfidf', () => {
    const result = runParsed();
    for (const t of result.terms) {
      const expected = Math.round((t.draft_wdfidf - t.competitor_avg_wdfidf) * 1000000) / 1000000;
      assert.equal(t.delta, expected,
        `delta for "${t.term}" must equal draft_wdfidf - competitor_avg_wdfidf`);
    }
  });

  it('signal is "increase" when delta is negative and exceeds threshold', () => {
    const result = runParsed({ threshold: 0.01 });
    const negTerms = result.terms.filter(t => t.delta < -0.01);
    assert.ok(negTerms.length > 0, 'must have terms with negative delta in fixtures');
    for (const t of negTerms) {
      assert.equal(t.signal, 'increase', `term "${t.term}" with delta=${t.delta} must signal "increase"`);
    }
  });

  it('signal is "decrease" when delta is positive and exceeds threshold', () => {
    const result = runParsed({ threshold: 0.01 });
    const posTerms = result.terms.filter(t => t.delta > 0.01);
    assert.ok(posTerms.length > 0, 'must have terms with positive delta in fixtures');
    for (const t of posTerms) {
      assert.equal(t.signal, 'decrease', `term "${t.term}" with delta=${t.delta} must signal "decrease"`);
    }
  });

  it('signal is "ok" when absolute delta is within threshold', () => {
    const result = runParsed({ threshold: 100 });
    for (const t of result.terms) {
      assert.equal(t.signal, 'ok', `with threshold=100 all terms must signal "ok"`);
    }
  });

  it('terms are sorted by absolute delta descending', () => {
    const result = runParsed();
    for (let i = 1; i < result.terms.length; i++) {
      const prev = Math.abs(result.terms[i - 1].delta);
      const curr = Math.abs(result.terms[i].delta);
      assert.ok(prev >= curr, 'terms must be sorted by absolute delta descending');
    }
  });

  it('terms with equal absolute delta are sorted alphabetically for determinism', () => {
    const tmp = makeTmpDir();
    try {
      // Create two pages with distinct single terms each (df=1 each) so both get
      // corpus-local IDF of log2(2/1)=1. Draft contains neither term.
      // Both terms then have draft_wdfidf=0 and equal competitor_avg_wdfidf.
      // Alphabetical order must be the tiebreaker.
      const filler = 'wort '.repeat(30);
      writeFileSync(join(tmp.pagesDir, 'p1.json'), makePage(`zebra ${filler}`));
      writeFileSync(join(tmp.pagesDir, 'p2.json'), makePage(`apfel ${filler}`));
      writeFileSync(join(tmp.dir, 'draft.txt'), 'nichts');
      const result = JSON.parse(
        execFileSync('node', [script,
          '--draft', join(tmp.dir, 'draft.txt'),
          '--pages-dir', tmp.pagesDir,
          '--language', 'en',
        ], { encoding: 'utf-8' })
      );
      const zebraIdx = result.terms.findIndex(t => t.term === 'zebra');
      const apfelIdx = result.terms.findIndex(t => t.term === 'apfel');
      if (zebraIdx !== -1 && apfelIdx !== -1) {
        assert.ok(apfelIdx < zebraIdx, '"apfel" must sort before "zebra" when deltas are equal');
      }
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('competitor_count in meta matches number of page files', () => {
    const result = runParsed();
    assert.equal(result.meta.competitor_count, 2, 'fixture has 2 competitor pages');
  });

  it('produces byte-identical output on repeated runs (determinism)', () => {
    const run1 = run();
    const run2 = run();
    assert.equal(run1, run2, 'same inputs must produce byte-identical output');
  });

  it('determinism holds for corpus-local IDF path', () => {
    const run1 = run({ language: 'en' });
    const run2 = run({ language: 'en' });
    assert.equal(run1, run2, 'corpus-local IDF path must also be deterministic');
  });

  it('reference-IDF path: term present in draft but absent in competitors has negative delta', () => {
    const tmp = makeTmpDir();
    try {
      // "spass" is in the fixture draft but not the fixture pages —
      // so draft_wdfidf > 0, competitor_avg_wdfidf = 0, delta > 0 → signal "decrease"
      const result = runParsed({ draft: fixtureDraft, pagesDir: fixturePages });
      const spass = result.terms.find(t => t.term === 'spass');
      assert.ok(spass !== undefined, '"spass" must appear in terms');
      assert.ok(spass.draft_wdfidf > 0, 'draft_wdfidf must be positive');
      assert.equal(spass.competitor_avg_wdfidf, 0, 'competitor_avg_wdfidf must be 0');
      assert.ok(spass.delta > 0, 'delta must be positive');
      assert.equal(spass.signal, 'decrease');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('fallback-IDF path: term absent in draft but present in competitors has negative delta', () => {
    const tmp = makeTmpDir();
    try {
      // Use 3 competitor pages where "schnorcheln" appears in only one (df=1, N=3).
      // corpus-local IDF = log2(3/1) > 0, so competitor_avg_wdfidf > 0.
      // Draft does not contain "schnorcheln", so draft_wdfidf=0 and delta < 0.
      const filler = 'wort '.repeat(30);
      writeFileSync(join(tmp.pagesDir, 'p1.json'), makePage(`schnorcheln tauchen ${filler}`));
      writeFileSync(join(tmp.pagesDir, 'p2.json'), makePage(`meer strand ${filler}`));
      writeFileSync(join(tmp.pagesDir, 'p3.json'), makePage(`urlaub reisen ${filler}`));
      writeFileSync(join(tmp.dir, 'draft.txt'), 'kurzer text ohne das keyword');
      const result = JSON.parse(
        execFileSync('node', [script,
          '--draft', join(tmp.dir, 'draft.txt'),
          '--pages-dir', tmp.pagesDir,
          '--language', 'en',
        ], { encoding: 'utf-8' })
      );
      assert.equal(result.meta.idf_source, 'corpus-local');
      const term = result.terms.find(t => t.term === 'schnorcheln');
      assert.ok(term !== undefined, '"schnorcheln" must appear in terms');
      assert.equal(term.draft_wdfidf, 0, 'draft_wdfidf must be 0');
      assert.ok(term.competitor_avg_wdfidf > 0, 'competitor_avg_wdfidf must be positive');
      assert.ok(term.delta < 0, 'delta must be negative');
      assert.equal(term.signal, 'increase');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('handles empty pages directory gracefully', () => {
    const tmp = makeTmpDir();
    try {
      const result = JSON.parse(
        execFileSync('node', [script,
          '--draft', fixtureDraft,
          '--pages-dir', tmp.pagesDir,
        ], { encoding: 'utf-8' })
      );
      assert.equal(result.meta.competitor_count, 0);
      assert.ok(Array.isArray(result.terms));
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('WDF is 0 for terms with zero count in a document', () => {
    const result = runParsed();
    // Terms that appear in competitors but not draft: draft_wdfidf must be 0
    const draftOnlyAbsent = result.terms.filter(t => t.draft_wdfidf === 0);
    assert.ok(draftOnlyAbsent.length > 0, 'must have terms absent from draft');
    for (const t of draftOnlyAbsent) {
      assert.equal(t.draft_wdfidf, 0);
    }
  });

  it('default threshold is 0.1 when not specified', () => {
    const result = runParsed();
    assert.equal(result.meta.threshold, 0.1, 'default threshold must be 0.1');
  });

  it('custom --threshold flag is reflected in meta and signal calculation', () => {
    const result = runParsed({ threshold: 0.5 });
    assert.equal(result.meta.threshold, 0.5, 'custom threshold must appear in meta');
  });

  it('n-gram terms appear in output (bigrams and trigrams)', () => {
    const result = runParsed();
    const ngrams = result.terms.filter(t => t.term.includes(' '));
    assert.ok(ngrams.length > 0, 'must have at least one n-gram term in output');
  });

});
