import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'keywords', 'merge-keywords.mjs');
const fixtures = join(__dirname, '..', 'fixtures', 'keyword-expansion');

function run(relatedFile, suggestionsFile, seed) {
  const stdout = execFileSync('node', [
    script,
    '--related', relatedFile,
    '--suggestions', suggestionsFile,
    '--seed', seed,
  ], { encoding: 'utf-8' });
  return JSON.parse(stdout);
}

describe('merge-keywords', () => {
  describe('deduplication', () => {
    it('deduplicates keywords across related and suggestions (case-insensitive)', () => {
      const result = run(
        join(fixtures, 'related-raw.json'),
        join(fixtures, 'suggestions-raw.json'),
        'keyword recherche',
      );
      // "Keyword Analyse" appears in both (related has "keyword analyse", suggestions has "Keyword Analyse")
      // Should appear only once
      const analyseEntries = result.keywords.filter(
        k => k.keyword.toLowerCase() === 'keyword analyse',
      );
      assert.equal(analyseEntries.length, 1, 'duplicate keyword must appear only once');
    });

    it('prefers the related_keywords entry when a keyword appears in both sources', () => {
      const result = run(
        join(fixtures, 'related-raw.json'),
        join(fixtures, 'suggestions-raw.json'),
        'keyword recherche',
      );
      const analyse = result.keywords.find(
        k => k.keyword.toLowerCase() === 'keyword analyse',
      );
      assert.equal(analyse.source, 'related', 'duplicate should keep related source');
      // Related has search_volume 800, suggestions has 900; related should win
      assert.equal(analyse.search_volume, 800);
    });
  });

  describe('seed keyword inclusion', () => {
    it('includes seed keyword when it appears in API results', () => {
      const result = run(
        join(fixtures, 'related-raw.json'),
        join(fixtures, 'suggestions-raw.json'),
        'keyword recherche',
      );
      assert.equal(result.seed_keyword, 'keyword recherche');
      const seed = result.keywords.find(k => k.keyword === 'keyword recherche');
      assert.ok(seed, 'seed keyword must be in the list');
    });

    it('adds seed keyword even when absent from API results', () => {
      const result = run(
        join(fixtures, 'related-empty.json'),
        join(fixtures, 'suggestions-empty.json'),
        'my unique seed',
      );
      assert.equal(result.total_keywords, 1);
      assert.equal(result.keywords[0].keyword, 'my unique seed');
      assert.equal(result.keywords[0].source, 'seed');
      assert.equal(result.keywords[0].search_volume, null);
    });

    it('does not duplicate seed keyword when it already exists in results', () => {
      const result = run(
        join(fixtures, 'related-raw.json'),
        join(fixtures, 'suggestions-raw.json'),
        'keyword recherche',
      );
      const seedEntries = result.keywords.filter(
        k => k.keyword.toLowerCase() === 'keyword recherche',
      );
      assert.equal(seedEntries.length, 1, 'seed must not be duplicated');
    });
  });

  describe('case-insensitive merging', () => {
    it('treats differently-cased keywords as the same', () => {
      const result = run(
        join(fixtures, 'related-raw.json'),
        join(fixtures, 'suggestions-raw.json'),
        'keyword recherche',
      );
      // "Keyword Planner" from related and no match in suggestions
      // "keyword recherche tool" from suggestions and no match in related
      // Both should appear exactly once
      const keywordSet = new Set(result.keywords.map(k => k.keyword.toLowerCase()));
      assert.ok(keywordSet.has('keyword planner'));
      assert.ok(keywordSet.has('keyword recherche tool'));
    });

    it('seed keyword matching is case-insensitive', () => {
      const result = run(
        join(fixtures, 'related-raw.json'),
        join(fixtures, 'suggestions-raw.json'),
        'Keyword Recherche',
      );
      // Seed "Keyword Recherche" matches "keyword recherche" in related results
      const seedEntries = result.keywords.filter(
        k => k.keyword.toLowerCase() === 'keyword recherche',
      );
      assert.equal(seedEntries.length, 1, 'case-insensitive seed should not create duplicate');
    });
  });

  describe('sorting', () => {
    it('sorts by search_volume descending', () => {
      const result = run(
        join(fixtures, 'related-raw.json'),
        join(fixtures, 'suggestions-raw.json'),
        'keyword recherche',
      );
      const volumes = result.keywords.map(k => k.search_volume ?? -1);
      for (let i = 1; i < volumes.length; i++) {
        assert.ok(
          volumes[i] <= volumes[i - 1] ||
          (volumes[i] === volumes[i - 1]),
          `volume at index ${i} (${volumes[i]}) should be <= volume at index ${i - 1} (${volumes[i - 1]})`,
        );
      }
    });

    it('uses alphabetical tie-break for equal volumes', () => {
      const result = run(
        join(fixtures, 'related-raw.json'),
        join(fixtures, 'suggestions-raw.json'),
        'keyword recherche',
      );
      // Find keywords with equal volume and verify alphabetical order
      for (let i = 1; i < result.keywords.length; i++) {
        const prev = result.keywords[i - 1];
        const curr = result.keywords[i];
        if ((prev.search_volume ?? -1) === (curr.search_volume ?? -1)) {
          assert.ok(
            prev.keyword.toLowerCase().localeCompare(curr.keyword.toLowerCase()) <= 0,
            `alphabetical tie-break: "${prev.keyword}" should come before "${curr.keyword}"`,
          );
        }
      }
    });
  });

  describe('empty and malformed responses', () => {
    it('handles both endpoints returning empty results', () => {
      const result = run(
        join(fixtures, 'related-empty.json'),
        join(fixtures, 'suggestions-empty.json'),
        'empty test',
      );
      assert.equal(result.total_keywords, 1, 'only seed keyword should be present');
      assert.equal(result.keywords[0].keyword, 'empty test');
    });

    it('handles malformed items gracefully', () => {
      const result = run(
        join(fixtures, 'malformed-response.json'),
        join(fixtures, 'suggestions-empty.json'),
        'test seed',
      );
      // Should extract "valid keyword" (trimmed) and skip null/missing keyword_data
      const keywords = result.keywords.map(k => k.keyword);
      assert.ok(keywords.includes('valid keyword'), 'valid keyword should be extracted and trimmed');
      assert.ok(keywords.includes('test seed'), 'seed should be present');
      assert.equal(result.total_keywords, 2);
    });
  });

  describe('output structure', () => {
    it('includes required fields in output', () => {
      const result = run(
        join(fixtures, 'related-raw.json'),
        join(fixtures, 'suggestions-raw.json'),
        'keyword recherche',
      );
      assert.ok('seed_keyword' in result);
      assert.ok('total_keywords' in result);
      assert.ok('keywords' in result);
      assert.ok(Array.isArray(result.keywords));
      assert.equal(result.total_keywords, result.keywords.length);
    });

    it('includes required fields per keyword', () => {
      const result = run(
        join(fixtures, 'related-raw.json'),
        join(fixtures, 'suggestions-raw.json'),
        'keyword recherche',
      );
      for (const kw of result.keywords) {
        assert.ok('keyword' in kw, 'keyword field required');
        assert.ok('search_volume' in kw, 'search_volume field required');
        assert.ok('cpc' in kw, 'cpc field required');
        assert.ok('monthly_searches' in kw, 'monthly_searches field required');
        assert.ok('source' in kw, 'source field required');
      }
    });
  });

  describe('determinism', () => {
    it('produces byte-identical output for identical input', () => {
      const run1 = execFileSync('node', [
        script,
        '--related', join(fixtures, 'related-raw.json'),
        '--suggestions', join(fixtures, 'suggestions-raw.json'),
        '--seed', 'keyword recherche',
      ], { encoding: 'utf-8' });

      const run2 = execFileSync('node', [
        script,
        '--related', join(fixtures, 'related-raw.json'),
        '--suggestions', join(fixtures, 'suggestions-raw.json'),
        '--seed', 'keyword recherche',
      ], { encoding: 'utf-8' });

      assert.equal(run1, run2, 'same input must produce byte-identical output');
    });
  });

  describe('CLI validation', () => {
    it('exits with error when --related is missing', () => {
      assert.throws(
        () => execFileSync('node', [
          script,
          '--suggestions', join(fixtures, 'suggestions-raw.json'),
          '--seed', 'test',
        ], { encoding: 'utf-8', stdio: 'pipe' }),
        (err) => {
          assert.equal(err.status, 1);
          assert.ok(err.stderr.includes('Usage'));
          return true;
        },
      );
    });

    it('exits with error when --seed is missing', () => {
      assert.throws(
        () => execFileSync('node', [
          script,
          '--related', join(fixtures, 'related-raw.json'),
          '--suggestions', join(fixtures, 'suggestions-raw.json'),
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
