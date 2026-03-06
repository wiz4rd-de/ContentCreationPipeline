import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'keywords', 'process-keywords.mjs');
const fixtures = join(__dirname, '..', 'fixtures', 'process-keywords');

function run(opts = {}) {
  const args = [script];
  args.push('--related', opts.related || join(fixtures, 'related-raw.json'));
  args.push('--suggestions', opts.suggestions || join(fixtures, 'suggestions-raw.json'));
  args.push('--seed', opts.seed || 'keyword recherche');
  if (opts.difficulty) {
    args.push('--difficulty', opts.difficulty);
  }
  if (opts.brands) {
    args.push('--brands', opts.brands);
  }
  const stdout = execFileSync('node', args, { encoding: 'utf-8' });
  return JSON.parse(stdout);
}

function runRaw(opts = {}) {
  const args = [script];
  args.push('--related', opts.related || join(fixtures, 'related-raw.json'));
  args.push('--suggestions', opts.suggestions || join(fixtures, 'suggestions-raw.json'));
  args.push('--seed', opts.seed || 'keyword recherche');
  if (opts.difficulty) {
    args.push('--difficulty', opts.difficulty);
  }
  if (opts.brands) {
    args.push('--brands', opts.brands);
  }
  return execFileSync('node', args, { encoding: 'utf-8' });
}

// Helper: flatten all keywords from clusters
function allKeywords(result) {
  return result.clusters.flatMap(c => c.keywords);
}

describe('process-keywords', () => {

  // --- Intent tagging -------------------------------------------------------

  describe('intent tagging', () => {
    it('tags transactional keywords (DE: kaufen)', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const kw = allKeywords(result).find(k => k.keyword === 'seo keywords kaufen');
      assert.equal(kw.intent, 'transactional');
    });

    it('tags transactional keywords (EN: buy)', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const kw = allKeywords(result).find(k => k.keyword === 'buy keyword tool');
      assert.equal(kw.intent, 'transactional');
    });

    it('tags commercial keywords (DE: beste)', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const kw = allKeywords(result).find(k => k.keyword === 'beste keyword recherche tool');
      assert.equal(kw.intent, 'commercial');
    });

    it('tags commercial keywords (EN: best)', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const kw = allKeywords(result).find(k => k.keyword === 'best keyword research tool');
      assert.equal(kw.intent, 'commercial');
    });

    it('tags commercial keywords (DE: vergleich)', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const kw = allKeywords(result).find(k => k.keyword === 'keyword vergleich tool');
      assert.equal(kw.intent, 'commercial');
    });

    it('tags informational keywords (EN: how)', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const kw = allKeywords(result).find(k => k.keyword === 'how to find keywords');
      assert.equal(kw.intent, 'informational');
    });

    it('tags informational keywords (DE: anleitung)', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche anleitung');
      assert.equal(kw.intent, 'informational');
    });

    it('tags informational keywords (DE: tipps)', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche tipps');
      assert.equal(kw.intent, 'informational');
    });

    it('tags informational keywords (EN: guide)', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche guide');
      assert.equal(kw.intent, 'informational');
    });

    it('returns null for unknown intent', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const kw = allKeywords(result).find(k => k.keyword === 'unknown topic xyz');
      assert.equal(kw.intent, null);
    });

    it('returns null for keywords that match no pattern', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche');
      assert.equal(kw.intent, null);
    });

    it('tags navigational when brand list is provided', () => {
      const result = run({
        difficulty: join(fixtures, 'difficulty-raw.json'),
        brands: 'seo,xyz',
      });
      // "seo keywords kaufen" contains "seo" as brand, so navigational wins
      const kw = allKeywords(result).find(k => k.keyword === 'seo keywords kaufen');
      assert.equal(kw.intent, 'navigational');
      // "unknown topic xyz" contains "xyz" as brand
      const kw2 = allKeywords(result).find(k => k.keyword === 'unknown topic xyz');
      assert.equal(kw2.intent, 'navigational');
    });
  });

  // --- Clustering -----------------------------------------------------------

  describe('clustering', () => {
    it('groups keywords with high n-gram overlap into the same cluster', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      // "keyword recherche" cluster should contain "keyword recherche anleitung",
      // "keyword recherche kostenlos", "keyword recherche tipps", etc.
      const cluster = result.clusters.find(c => c.cluster_keyword === 'keyword recherche');
      assert.ok(cluster, 'keyword recherche cluster must exist');
      const kwNames = cluster.keywords.map(k => k.keyword);
      assert.ok(kwNames.includes('keyword recherche anleitung'));
      assert.ok(kwNames.includes('keyword recherche kostenlos'));
      assert.ok(kwNames.includes('keyword recherche tipps'));
    });

    it('assigns cluster representative as the highest-volume keyword', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      for (const cluster of result.clusters) {
        const repVol = cluster.keywords[0].search_volume ?? -1;
        for (const kw of cluster.keywords) {
          assert.ok(
            (kw.search_volume ?? -1) <= repVol,
            `${kw.keyword} volume should be <= representative volume`,
          );
        }
      }
    });

    it('does not cluster keywords with low n-gram overlap', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      // "unknown topic xyz" should be in its own cluster
      const cluster = result.clusters.find(c => c.cluster_keyword === 'unknown topic xyz');
      assert.ok(cluster);
      assert.equal(cluster.keyword_count, 1);
    });

    it('each keyword appears in exactly one cluster', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const allKws = allKeywords(result);
      const keywordSet = new Set(allKws.map(k => k.keyword));
      assert.equal(allKws.length, keywordSet.size, 'no keyword should appear twice');
      assert.equal(allKws.length, result.total_keywords);
    });
  });

  // --- Deduplication --------------------------------------------------------

  describe('deduplication', () => {
    it('deduplicates case-insensitively across related and suggestions', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      // "keyword analyse tool" in related (lowercase) and "Keyword Analyse Tool" in suggestions
      const matches = allKeywords(result).filter(
        k => k.keyword.toLowerCase() === 'keyword analyse tool',
      );
      assert.equal(matches.length, 1, 'duplicate should appear only once');
    });

    it('prefers the related entry when duplicated', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const kw = allKeywords(result).find(
        k => k.keyword.toLowerCase() === 'keyword analyse tool',
      );
      // related has volume 800, suggestions has 900
      assert.equal(kw.search_volume, 800);
    });

    it('trims whitespace for deduplication', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      // All keywords should be trimmed
      for (const kw of allKeywords(result)) {
        assert.equal(kw.keyword, kw.keyword.trim());
      }
    });
  });

  // --- Determinism ----------------------------------------------------------

  describe('determinism', () => {
    it('produces byte-identical output for identical input', () => {
      const run1 = runRaw({ difficulty: join(fixtures, 'difficulty-raw.json') });
      const run2 = runRaw({ difficulty: join(fixtures, 'difficulty-raw.json') });
      assert.equal(run1, run2, 'same input must produce byte-identical output');
    });

    it('produces byte-identical output without difficulty file', () => {
      const run1 = runRaw({});
      const run2 = runRaw({});
      assert.equal(run1, run2, 'same input must produce byte-identical output');
    });
  });

  // --- Edge cases -----------------------------------------------------------

  describe('edge cases', () => {
    it('handles single keyword', () => {
      const result = run({
        related: join(fixtures, 'related-single.json'),
        suggestions: join(fixtures, 'suggestions-empty.json'),
        seed: 'single keyword',
      });
      assert.equal(result.total_keywords, 1);
      assert.equal(result.total_clusters, 1);
      assert.equal(result.clusters[0].keyword_count, 1);
      assert.equal(result.clusters[0].cluster_keyword, 'single keyword');
    });

    it('handles empty inputs (only seed keyword)', () => {
      const result = run({
        related: join(fixtures, 'related-empty.json'),
        suggestions: join(fixtures, 'suggestions-empty.json'),
        seed: 'lonely seed',
      });
      assert.equal(result.total_keywords, 1);
      assert.equal(result.total_clusters, 1);
      const kw = allKeywords(result)[0];
      assert.equal(kw.keyword, 'lonely seed');
      assert.equal(kw.search_volume, null);
      assert.equal(kw.difficulty, null);
      assert.equal(kw.intent, null);
    });

    it('handles all-null difficulty values', () => {
      const result = run({
        difficulty: join(fixtures, 'difficulty-all-null.json'),
      });
      // Keywords that match null-difficulty entries should get null
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche');
      assert.equal(kw.difficulty, null);
      const kw2 = allKeywords(result).find(k => k.keyword === 'keyword analyse tool');
      assert.equal(kw2.difficulty, null);
    });

    it('handles missing difficulty file gracefully', () => {
      const result = run({});
      // No --difficulty flag: all difficulties should be null
      for (const kw of allKeywords(result)) {
        assert.equal(kw.difficulty, null, `${kw.keyword} should have null difficulty`);
      }
    });
  });

  // --- Output structure -----------------------------------------------------

  describe('output structure', () => {
    it('has required top-level fields', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      assert.ok('seed_keyword' in result);
      assert.ok('total_keywords' in result);
      assert.ok('total_clusters' in result);
      assert.ok('clusters' in result);
      assert.ok(Array.isArray(result.clusters));
    });

    it('clusters have required fields including LLM null placeholders', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      for (const cluster of result.clusters) {
        assert.ok('cluster_keyword' in cluster);
        assert.ok('cluster_label' in cluster);
        assert.equal(cluster.cluster_label, null, 'cluster_label must be null placeholder');
        assert.ok('strategic_notes' in cluster);
        assert.equal(cluster.strategic_notes, null, 'strategic_notes must be null placeholder');
        assert.ok('keyword_count' in cluster);
        assert.ok('keywords' in cluster);
        assert.equal(cluster.keyword_count, cluster.keywords.length);
      }
    });

    it('keywords have all required fields', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      for (const kw of allKeywords(result)) {
        assert.ok('keyword' in kw);
        assert.ok('search_volume' in kw);
        assert.ok('cpc' in kw);
        assert.ok('monthly_searches' in kw);
        assert.ok('difficulty' in kw);
        assert.ok('intent' in kw);
      }
    });

    it('total_keywords matches actual keyword count', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      assert.equal(result.total_keywords, allKeywords(result).length);
    });

    it('total_clusters matches actual cluster count', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      assert.equal(result.total_clusters, result.clusters.length);
    });
  });

  // --- Sorting --------------------------------------------------------------

  describe('sorting', () => {
    it('sorts keywords within clusters by volume descending', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      for (const cluster of result.clusters) {
        for (let i = 1; i < cluster.keywords.length; i++) {
          const prev = cluster.keywords[i - 1].search_volume ?? -1;
          const curr = cluster.keywords[i].search_volume ?? -1;
          assert.ok(
            curr <= prev,
            `within cluster "${cluster.cluster_keyword}": volume ${curr} should be <= ${prev}`,
          );
        }
      }
    });

    it('uses alphabetical tie-break for equal volumes', () => {
      const result = run({ difficulty: join(fixtures, 'difficulty-raw.json') });
      for (const cluster of result.clusters) {
        for (let i = 1; i < cluster.keywords.length; i++) {
          const prev = cluster.keywords[i - 1];
          const curr = cluster.keywords[i];
          if ((prev.search_volume ?? -1) === (curr.search_volume ?? -1)) {
            assert.ok(
              prev.keyword.toLowerCase().localeCompare(curr.keyword.toLowerCase()) <= 0,
              `tie-break: "${prev.keyword}" should come before "${curr.keyword}"`,
            );
          }
        }
      }
    });
  });

  // --- CLI validation -------------------------------------------------------

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
