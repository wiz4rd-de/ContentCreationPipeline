import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { createReadStream } from 'node:fs';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

import { computeIdf } from '../../scripts/build-idf-table.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURES = join(__dirname, '../fixtures/build-idf-table');

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
