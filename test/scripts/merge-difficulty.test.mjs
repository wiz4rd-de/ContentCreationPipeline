import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'keywords', 'merge-difficulty.mjs');
const fixtures = join(__dirname, '..', 'fixtures', 'keyword-difficulty');

function run(expandedFile, difficultyFile) {
  const stdout = execFileSync('node', [
    script,
    '--expanded', expandedFile,
    '--difficulty', difficultyFile,
  ], { encoding: 'utf-8' });
  return JSON.parse(stdout);
}

describe('merge-difficulty', () => {
  describe('KD values correctly merged', () => {
    it('merges difficulty values into matching keyword records', () => {
      const result = run(
        join(fixtures, 'expanded.json'),
        join(fixtures, 'difficulty-raw.json'),
      );
      const kw = result.keywords.find(k => k.keyword === 'keyword recherche');
      assert.equal(kw.difficulty, 42);

      const kw2 = result.keywords.find(k => k.keyword === 'keyword analyse');
      assert.equal(kw2.difficulty, 55);
    });

    it('matches keywords case-insensitively', () => {
      const result = run(
        join(fixtures, 'expanded.json'),
        join(fixtures, 'difficulty-raw.json'),
      );
      // Expanded has "SEO Keywords finden", difficulty has "SEO Keywords finden"
      const kw = result.keywords.find(k => k.keyword === 'SEO Keywords finden');
      assert.equal(kw.difficulty, 0);

      // Expanded has "Keyword Planner", difficulty has "Keyword Planner"
      const kw2 = result.keywords.find(k => k.keyword === 'Keyword Planner');
      assert.equal(kw2.difficulty, 100);
    });

    it('preserves all original keyword fields', () => {
      const result = run(
        join(fixtures, 'expanded.json'),
        join(fixtures, 'difficulty-raw.json'),
      );
      const kw = result.keywords.find(k => k.keyword === 'keyword recherche');
      assert.equal(kw.search_volume, 1200);
      assert.equal(kw.cpc, 2.5);
      assert.equal(kw.source, 'related');
      assert.ok('monthly_searches' in kw);
    });
  });

  describe('missing keywords get difficulty: null', () => {
    it('sets difficulty to null for keywords not in KD response', () => {
      const result = run(
        join(fixtures, 'expanded.json'),
        join(fixtures, 'difficulty-partial.json'),
      );
      // "keyword recherche tool" is not in partial response
      const kw = result.keywords.find(k => k.keyword === 'keyword recherche tool');
      assert.equal(kw.difficulty, null);

      // "SEO Keywords finden" is not in partial response
      const kw2 = result.keywords.find(k => k.keyword === 'SEO Keywords finden');
      assert.equal(kw2.difficulty, null);
    });

    it('sets all difficulties to null when KD response is empty', () => {
      const result = run(
        join(fixtures, 'expanded.json'),
        join(fixtures, 'difficulty-empty.json'),
      );
      for (const kw of result.keywords) {
        assert.equal(kw.difficulty, null, `${kw.keyword} should have difficulty: null`);
      }
    });

    it('never assigns difficulty: 0 by default -- only from actual API data', () => {
      const result = run(
        join(fixtures, 'expanded.json'),
        join(fixtures, 'difficulty-partial.json'),
      );
      // Keywords missing from KD response must be null, not 0
      const missing = result.keywords.filter(
        k => !['keyword recherche', 'keyword analyse'].includes(k.keyword.toLowerCase()),
      );
      for (const kw of missing) {
        assert.equal(kw.difficulty, null, `${kw.keyword} missing from KD response must be null, not 0`);
      }
    });
  });

  describe('boundary values', () => {
    it('handles difficulty: 0 from API (minimum boundary)', () => {
      const result = run(
        join(fixtures, 'expanded.json'),
        join(fixtures, 'difficulty-raw.json'),
      );
      const kw = result.keywords.find(k => k.keyword === 'SEO Keywords finden');
      assert.equal(kw.difficulty, 0);
      // Ensure 0 is integer, not null
      assert.equal(typeof kw.difficulty, 'number');
    });

    it('handles difficulty: 100 from API (maximum boundary)', () => {
      const result = run(
        join(fixtures, 'expanded.json'),
        join(fixtures, 'difficulty-raw.json'),
      );
      const kw = result.keywords.find(k => k.keyword === 'Keyword Planner');
      assert.equal(kw.difficulty, 100);
      assert.equal(typeof kw.difficulty, 'number');
    });
  });

  describe('output structure', () => {
    it('preserves seed_keyword and total_keywords', () => {
      const result = run(
        join(fixtures, 'expanded.json'),
        join(fixtures, 'difficulty-raw.json'),
      );
      assert.equal(result.seed_keyword, 'keyword recherche');
      assert.equal(result.total_keywords, 5);
      assert.equal(result.keywords.length, 5);
    });

    it('every keyword record has a difficulty field', () => {
      const result = run(
        join(fixtures, 'expanded.json'),
        join(fixtures, 'difficulty-raw.json'),
      );
      for (const kw of result.keywords) {
        assert.ok('difficulty' in kw, `${kw.keyword} must have difficulty field`);
      }
    });

    it('preserves original keyword order', () => {
      const result = run(
        join(fixtures, 'expanded.json'),
        join(fixtures, 'difficulty-raw.json'),
      );
      const keywords = result.keywords.map(k => k.keyword);
      assert.deepEqual(keywords, [
        'Keyword Planner',
        'keyword recherche',
        'keyword analyse',
        'SEO Keywords finden',
        'keyword recherche tool',
      ]);
    });
  });

  describe('determinism', () => {
    it('produces byte-identical output for identical input', () => {
      const run1 = execFileSync('node', [
        script,
        '--expanded', join(fixtures, 'expanded.json'),
        '--difficulty', join(fixtures, 'difficulty-raw.json'),
      ], { encoding: 'utf-8' });

      const run2 = execFileSync('node', [
        script,
        '--expanded', join(fixtures, 'expanded.json'),
        '--difficulty', join(fixtures, 'difficulty-raw.json'),
      ], { encoding: 'utf-8' });

      assert.equal(run1, run2, 'same input must produce byte-identical output');
    });
  });

  describe('CLI validation', () => {
    it('exits with error when --expanded is missing', () => {
      assert.throws(
        () => execFileSync('node', [
          script,
          '--difficulty', join(fixtures, 'difficulty-raw.json'),
        ], { encoding: 'utf-8', stdio: 'pipe' }),
        (err) => {
          assert.equal(err.status, 1);
          assert.ok(err.stderr.includes('Usage'));
          return true;
        },
      );
    });

    it('exits with error when --difficulty is missing', () => {
      assert.throws(
        () => execFileSync('node', [
          script,
          '--expanded', join(fixtures, 'expanded.json'),
        ], { encoding: 'utf-8', stdio: 'pipe' }),
        (err) => {
          assert.equal(err.status, 1);
          assert.ok(err.stderr.includes('Usage'));
          return true;
        },
      );
    });
  });
});
