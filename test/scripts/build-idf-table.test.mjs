import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { createReadStream, writeFileSync, mkdirSync, rmSync, readFileSync } from 'node:fs';
import { createInterface } from 'node:readline';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

import { computeIdf } from '../../scripts/build-idf-table.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURES = join(__dirname, '../fixtures/build-idf-table');
const SCRIPT = join(__dirname, '../../scripts/build-idf-table.mjs');
const CORPUS_TXT = join(FIXTURES, 'corpus.txt');
const STOPWORDS_PATH = join(__dirname, '../../src/utils/stopwords.json');

// Helper: create an async iterable of lines from an array of strings
function linesFromArray(arr) {
  return arr[Symbol.iterator]
    ? (async function* () { for (const line of arr) yield line; })()
    : arr;
}

// Helper: open a fixture file and return a readline interface (async iterable)
function openFixture(filename) {
  const stream = createReadStream(join(FIXTURES, filename), { encoding: 'utf8' });
  return createInterface({ input: stream, crlfDelay: Infinity });
}

// Known expected values for the plain fixture with min-df=1:
// N=8, df: hund=8, katze=4, maus=2, vogel=1, baum=1
// IDF = Math.round(Math.log2(N/df) * 1000) / 1000
// hund:  log2(8/8) = 0.000
// katze: log2(8/4) = 1.000
// maus:  log2(8/2) = 2.000
// vogel: log2(8/1) = 3.000
// baum:  log2(8/1) = 3.000

describe('build-idf-table: computeIdf', () => {

  describe('plain text corpus', () => {

    it('counts total_documents correctly', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 1, maxTerms: 200000,
      });
      assert.equal(result.meta.total_documents, 8);
    });

    it('computes correct IDF for hund (df=8, N=8 → 0.0)', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 1, maxTerms: 200000,
      });
      assert.equal(result.idf.hund, 0);
    });

    it('computes correct IDF for katze (df=4, N=8 → 1.0)', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 1, maxTerms: 200000,
      });
      assert.equal(result.idf.katze, 1);
    });

    it('computes correct IDF for maus (df=2, N=8 → 2.0)', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 1, maxTerms: 200000,
      });
      assert.equal(result.idf.maus, 2);
    });

    it('computes correct IDF for vogel (df=1, N=8 → 3.0)', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 1, maxTerms: 200000,
      });
      assert.equal(result.idf.vogel, 3);
    });

    it('computes correct IDF for baum (df=1, N=8 → 3.0)', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 1, maxTerms: 200000,
      });
      assert.equal(result.idf.baum, 3);
    });

    it('meta.terms_included equals number of keys in idf', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 1, maxTerms: 200000,
      });
      assert.equal(result.meta.terms_included, Object.keys(result.idf).length);
    });

    it('meta reflects constructor options', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 1, maxTerms: 200000,
      });
      assert.equal(result.meta.corpus, 'plain.txt');
      assert.equal(result.meta.language, 'de');
      assert.equal(result.meta.min_df, 1);
    });

  });

  describe('min-df filtering', () => {

    it('excludes terms below min-df threshold', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 2, maxTerms: 200000,
      });
      // vogel and baum each have df=1, so they must be excluded
      assert.equal('vogel' in result.idf, false, 'vogel (df=1) must be excluded with min-df=2');
      assert.equal('baum' in result.idf, false, 'baum (df=1) must be excluded with min-df=2');
    });

    it('keeps terms at or above min-df threshold', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 2, maxTerms: 200000,
      });
      assert.ok('hund' in result.idf, 'hund (df=8) must be included');
      assert.ok('katze' in result.idf, 'katze (df=4) must be included');
      assert.ok('maus' in result.idf, 'maus (df=2) must be included');
    });

  });

  describe('max-terms truncation', () => {

    it('truncates output to max-terms entries (sorted by df desc)', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 1, maxTerms: 3,
      });
      // Terms sorted by df desc: hund(8), katze(4), maus(2), then baum/vogel(1 each)
      // After truncation to 3: hund, katze, maus
      assert.equal(Object.keys(result.idf).length, 3);
      assert.ok('hund' in result.idf);
      assert.ok('katze' in result.idf);
      assert.ok('maus' in result.idf);
    });

    it('meta.terms_included reflects truncated count', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 1, maxTerms: 2,
      });
      assert.equal(result.meta.terms_included, 2);
    });

  });

  describe('Leipzig tab-separated format', () => {

    it('produces identical IDF values as plain text format', async () => {
      const plain = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'corpus', minDf: 1, maxTerms: 200000,
      });
      const leipzig = await computeIdf(openFixture('leipzig.txt'), {
        language: 'de', corpusName: 'corpus', minDf: 1, maxTerms: 200000,
      });
      assert.deepEqual(plain.idf, leipzig.idf);
      assert.equal(plain.meta.total_documents, leipzig.meta.total_documents);
    });

  });

  describe('idf key ordering', () => {

    it('idf keys are sorted alphabetically', async () => {
      const result = await computeIdf(openFixture('plain.txt'), {
        language: 'de', corpusName: 'plain.txt', minDf: 1, maxTerms: 200000,
      });
      const keys = Object.keys(result.idf);
      const sorted = keys.slice().sort();
      assert.deepEqual(keys, sorted, 'idf keys must be in alphabetical order');
    });

  });

  describe('stopword filtering', () => {

    it('does not include DE stopwords in idf output', async () => {
      // "und", "die", "der" are all DE stopwords — they must not appear in output
      const lines = linesFromArray([
        'hund und die der katze',
        'maus und eine der baum',
      ]);
      const result = await computeIdf(lines, {
        language: 'de', corpusName: 'test', minDf: 1, maxTerms: 200000,
      });
      assert.equal('und' in result.idf, false, '"und" is a DE stopword and must be excluded');
      assert.equal('die' in result.idf, false, '"die" is a DE stopword and must be excluded');
      assert.equal('der' in result.idf, false, '"der" is a DE stopword and must be excluded');
    });

  });

  describe('deduplication per line', () => {

    it('counts each term at most once per line', async () => {
      // Two lines, each containing "hund" twice — df should be 2, not 4
      const lines = linesFromArray([
        'hund hund katze',
        'hund hund maus',
      ]);
      const result = await computeIdf(lines, {
        language: 'de', corpusName: 'test', minDf: 1, maxTerms: 200000,
      });
      // N=2, df(hund)=2 → IDF = log2(2/2) = 0
      assert.equal(result.idf.hund, 0);
      assert.equal(result.meta.total_documents, 2);
    });

  });

  describe('empty and stopword-only lines', () => {

    it('skips empty lines', async () => {
      const lines = linesFromArray(['hund', '', '   ', 'katze']);
      const result = await computeIdf(lines, {
        language: 'de', corpusName: 'test', minDf: 1, maxTerms: 200000,
      });
      // Only 2 non-empty productive lines
      assert.equal(result.meta.total_documents, 2);
    });

    it('skips lines that produce zero tokens after stopword removal', async () => {
      // "und die der" are all DE stopwords
      const lines = linesFromArray(['hund katze', 'und die der', 'maus']);
      const result = await computeIdf(lines, {
        language: 'de', corpusName: 'test', minDf: 1, maxTerms: 200000,
      });
      // Only 2 productive lines (stopword-only line is skipped)
      assert.equal(result.meta.total_documents, 2);
    });

  });

  describe('determinism', () => {

    it('produces byte-identical JSON output on repeated runs', async () => {
      const opts = { language: 'de', corpusName: 'plain.txt', minDf: 2, maxTerms: 200000 };
      const run1 = JSON.stringify(await computeIdf(openFixture('plain.txt'), opts));
      const run2 = JSON.stringify(await computeIdf(openFixture('plain.txt'), opts));
      assert.equal(run1, run2, 'output must be byte-identical across runs');
    });

  });

});

// ---------------------------------------------------------------------------
// CLI-level integration tests (fixture corpus.txt — Leipzig tab-format)
//
// corpus.txt contains 5 lines in "index\tsentence" format.
// After tokenization + DE+EN stopword removal the token sets per line are:
//   Line 1: {katze, sitzt, matte, schaut, fenster}
//   Line 2: {hund, liegt, katze, sofa}
//   Line 3: {matte, tuer, alt, schmutzig}
//   Line 4: {katze, jagt, maus, garten}
//   Line 5: {garten, zaun, blumen}
//
// N=5, document frequencies (df):
//   katze=3, matte=2, garten=2
//   sitzt=schaut=fenster=hund=liegt=sofa=tuer=alt=schmutzig=jagt=maus=zaun=blumen=1
//
// Expected IDF values (IDF = Math.round(Math.log2(N/df) * 1000) / 1000):
//   katze  (df=3): Math.round(Math.log2(5/3) * 1000) / 1000 = 0.737
//   matte  (df=2): Math.round(Math.log2(5/2) * 1000) / 1000 = 1.322
//   garten (df=2): Math.round(Math.log2(5/2) * 1000) / 1000 = 1.322
//   any df=1 term: Math.round(Math.log2(5/1) * 1000) / 1000 = 2.322
// ---------------------------------------------------------------------------

describe('build-idf-table: CLI', () => {

  function runCli(args, opts = {}) {
    return execFileSync('node', [SCRIPT, ...args], { encoding: 'utf-8', stdio: 'pipe', ...opts });
  }

  function runCliParsed(args) {
    return JSON.parse(runCli(args));
  }

  // Test 1: missing --corpus flag exits with non-zero code
  it('exits with error when --corpus flag is missing', () => {
    try {
      runCli(['--language', 'de']);
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
    }
  });

  // Test 2: missing --language flag exits with non-zero code
  it('exits with error when --language flag is missing', () => {
    try {
      runCli(['--corpus', CORPUS_TXT]);
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
    }
  });

  // Test 3: non-existent corpus file exits with non-zero code
  it('exits with error when corpus file does not exist', () => {
    try {
      runCli(['--corpus', '/tmp/does-not-exist-corpus.txt', '--language', 'de']);
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
    }
  });

  // Test 4: valid output has meta and idf top-level keys
  it('produces valid JSON with meta and idf top-level keys', () => {
    const result = runCliParsed(['--corpus', CORPUS_TXT, '--language', 'de', '--min-df', '1']);
    assert.ok(typeof result === 'object' && result !== null, 'output must be an object');
    assert.ok(typeof result.meta === 'object' && result.meta !== null, 'must have meta key');
    assert.ok(typeof result.idf === 'object' && result.idf !== null, 'must have idf key');
  });

  // Test 5: meta.total_documents matches line count
  // corpus.txt has 5 non-empty lines, all produce tokens → total_documents = 5
  it('meta.total_documents matches the number of productive lines in corpus', () => {
    const result = runCliParsed(['--corpus', CORPUS_TXT, '--language', 'de', '--min-df', '1']);
    assert.equal(result.meta.total_documents, 5, 'corpus.txt has 5 productive lines');
  });

  // Test 6: correct IDF values for known terms
  // katze (df=3, N=5): log2(5/3) ≈ 0.73697 → 0.737
  // matte (df=2, N=5): log2(5/2) ≈ 1.32193 → 1.322
  it('computes correct IDF for katze (df=3, N=5 → 0.737)', () => {
    const result = runCliParsed(['--corpus', CORPUS_TXT, '--language', 'de', '--min-df', '1']);
    assert.equal(result.idf.katze, 0.737, 'katze IDF must be 0.737');
  });

  it('computes correct IDF for matte (df=2, N=5 → 1.322)', () => {
    const result = runCliParsed(['--corpus', CORPUS_TXT, '--language', 'de', '--min-df', '1']);
    assert.equal(result.idf.matte, 1.322, 'matte IDF must be 1.322');
  });

  // Test 7: --min-df filtering
  it('--min-df 2 excludes terms with df=1', () => {
    const result = runCliParsed(['--corpus', CORPUS_TXT, '--language', 'de', '--min-df', '2']);
    // sitzt, schaut, fenster, hund, liegt, sofa, tuer, alt, schmutzig, jagt, maus, zaun, blumen all have df=1
    assert.equal('hund' in result.idf, false, 'hund (df=1) must be excluded with --min-df 2');
    assert.equal('maus' in result.idf, false, 'maus (df=1) must be excluded with --min-df 2');
  });

  it('--min-df 1 includes terms with df=1', () => {
    const result = runCliParsed(['--corpus', CORPUS_TXT, '--language', 'de', '--min-df', '1']);
    assert.ok('hund' in result.idf, 'hund (df=1) must be included with --min-df 1');
    assert.ok('maus' in result.idf, 'maus (df=1) must be included with --min-df 1');
  });

  // Test 8: --max-terms cap
  // With --min-df 1, terms sorted by df desc then alpha: katze(3), garten(2), matte(2), then df=1 terms
  // --max-terms 3 → exactly 3 terms: katze, garten, matte
  it('--max-terms 3 caps output to exactly 3 terms', () => {
    const result = runCliParsed(['--corpus', CORPUS_TXT, '--language', 'de', '--min-df', '1', '--max-terms', '3']);
    const keys = Object.keys(result.idf);
    assert.equal(keys.length, 3, 'idf must have exactly 3 entries');
    // katze has df=3 (highest), garten and matte have df=2
    assert.ok('katze' in result.idf, 'katze (df=3) must be one of the top 3');
    assert.ok('garten' in result.idf, 'garten (df=2) must be one of the top 3');
    assert.ok('matte' in result.idf, 'matte (df=2) must be one of the top 3');
  });

  // Test 9: stopwords excluded from idf output — cross-referenced with stopwords.json
  it('no German or English stopword appears as a key in idf', () => {
    const stopwordsData = JSON.parse(readFileSync(STOPWORDS_PATH, 'utf-8'));
    const allStopwords = new Set([...(stopwordsData.de || []), ...(stopwordsData.en || [])]);
    const result = runCliParsed(['--corpus', CORPUS_TXT, '--language', 'de', '--min-df', '1']);
    for (const term of Object.keys(result.idf)) {
      assert.equal(allStopwords.has(term), false, `stopword "${term}" must not appear in idf output`);
    }
  });

  // Test 10: Leipzig tab-format handled correctly — tab-prefixed line numbers must not appear as terms
  it('Leipzig tab-format line numbers do not appear as terms in idf output', () => {
    const result = runCliParsed(['--corpus', CORPUS_TXT, '--language', 'de', '--min-df', '1']);
    // Line number tokens would be "1", "2", "3", "4", "5" — all single-char, filtered by tokenizer
    // But also verify they are absent from idf
    for (const num of ['1', '2', '3', '4', '5']) {
      assert.equal(num in result.idf, false, `line number "${num}" must not appear in idf output`);
    }
  });

  // Test 11: plain-text format (no tabs) produces correct output
  it('handles plain-text format (no tab prefix) correctly', () => {
    const tmpDir = join(tmpdir(), 'idf-test-' + randomBytes(4).toString('hex'));
    const plainFile = join(tmpDir, 'plain-corpus.txt');
    mkdirSync(tmpDir, { recursive: true });
    try {
      // Plain-text version of corpus.txt (same sentences, no tab prefix)
      writeFileSync(plainFile, [
        'Die Katze sitzt auf der Matte und schaut aus dem Fenster',
        'Der Hund liegt neben der Katze auf dem Sofa',
        'Die Matte vor der Tuer ist alt und schmutzig',
        'Eine Katze jagt eine Maus durch den Garten',
        'Der Garten hat einen Zaun und viele Blumen',
      ].join('\n') + '\n', 'utf-8');
      const result = runCliParsed(['--corpus', plainFile, '--language', 'de', '--min-df', '1']);
      // Same N and IDF as corpus.txt since content is identical after tab-stripping
      assert.equal(result.meta.total_documents, 5, 'plain-text corpus must have 5 documents');
      assert.equal(result.idf.katze, 0.737, 'katze IDF must be 0.737 in plain-text corpus');
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  // Test 12: idf keys sorted alphabetically
  it('idf keys are sorted alphabetically in CLI output', () => {
    const result = runCliParsed(['--corpus', CORPUS_TXT, '--language', 'de', '--min-df', '1']);
    const keys = Object.keys(result.idf);
    const sorted = keys.slice().sort();
    assert.deepEqual(keys, sorted, 'idf keys must be in alphabetical order');
  });

  // Test 13: byte-identical output on repeated runs (determinism)
  it('produces byte-identical output on repeated CLI runs', () => {
    const args = ['--corpus', CORPUS_TXT, '--language', 'de', '--min-df', '1'];
    const out1 = runCli(args);
    const out2 = runCli(args);
    assert.equal(out1, out2, 'CLI output must be byte-identical across repeated runs');
  });

});
