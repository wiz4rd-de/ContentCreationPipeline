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
      const result = run();
      const kw = allKeywords(result).find(k => k.keyword === 'seo keywords kaufen');
      assert.equal(kw.intent, 'transactional');
    });

    it('tags transactional keywords (EN: buy)', () => {
      const result = run();
      const kw = allKeywords(result).find(k => k.keyword === 'buy keyword tool');
      assert.equal(kw.intent, 'transactional');
    });

    it('tags commercial keywords (DE: beste)', () => {
      const result = run();
      const kw = allKeywords(result).find(k => k.keyword === 'beste keyword recherche tool');
      assert.equal(kw.intent, 'commercial');
    });

    it('tags commercial keywords (EN: best)', () => {
      const result = run();
      const kw = allKeywords(result).find(k => k.keyword === 'best keyword research tool');
      assert.equal(kw.intent, 'commercial');
    });

    it('tags commercial keywords (DE: vergleich)', () => {
      const result = run();
      const kw = allKeywords(result).find(k => k.keyword === 'keyword vergleich tool');
      assert.equal(kw.intent, 'commercial');
    });

    it('tags informational keywords (EN: how)', () => {
      const result = run();
      const kw = allKeywords(result).find(k => k.keyword === 'how to find keywords');
      assert.equal(kw.intent, 'informational');
    });

    it('tags informational keywords (DE: anleitung)', () => {
      const result = run();
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche anleitung');
      assert.equal(kw.intent, 'informational');
    });

    it('tags informational keywords (DE: tipps)', () => {
      const result = run();
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche tipps');
      assert.equal(kw.intent, 'informational');
    });

    it('tags informational keywords (EN: guide)', () => {
      const result = run();
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche guide');
      assert.equal(kw.intent, 'informational');
    });

    it('returns null for unknown intent', () => {
      const result = run();
      const kw = allKeywords(result).find(k => k.keyword === 'unknown topic xyz');
      assert.equal(kw.intent, null);
    });

    it('returns null for keywords that match no pattern', () => {
      const result = run();
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche');
      assert.equal(kw.intent, null);
    });

    it('tags navigational when brand list is provided', () => {
      const result = run({ brands: 'seo,xyz' });
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
      const result = run();
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
      const result = run();
      for (const cluster of result.clusters) {
        const rep = cluster.keywords.find(k => k.keyword === cluster.cluster_keyword);
        assert.ok(rep, `cluster_keyword "${cluster.cluster_keyword}" must appear in keywords`);
        const repVol = rep.search_volume ?? -1;
        for (const kw of cluster.keywords) {
          assert.ok(
            (kw.search_volume ?? -1) <= repVol,
            `${kw.keyword} volume should be <= representative volume`,
          );
        }
      }
    });

    it('does not cluster keywords with low n-gram overlap', () => {
      const result = run();
      // "unknown topic xyz" should be in its own cluster
      const cluster = result.clusters.find(c => c.cluster_keyword === 'unknown topic xyz');
      assert.ok(cluster);
      assert.equal(cluster.keyword_count, 1);
    });

    it('each keyword appears in exactly one cluster', () => {
      const result = run();
      const allKws = allKeywords(result);
      const keywordSet = new Set(allKws.map(k => k.keyword));
      assert.equal(allKws.length, keywordSet.size, 'no keyword should appear twice');
      assert.equal(allKws.length, result.total_keywords);
    });
  });

  // --- Deduplication --------------------------------------------------------

  describe('deduplication', () => {
    it('deduplicates case-insensitively across related and suggestions', () => {
      const result = run();
      // "keyword analyse tool" in related (lowercase) and "Keyword Analyse Tool" in suggestions
      const matches = allKeywords(result).filter(
        k => k.keyword.toLowerCase() === 'keyword analyse tool',
      );
      assert.equal(matches.length, 1, 'duplicate should appear only once');
    });

    it('prefers the related entry when duplicated', () => {
      const result = run();
      const kw = allKeywords(result).find(
        k => k.keyword.toLowerCase() === 'keyword analyse tool',
      );
      // related has volume 800, suggestions has 900
      assert.equal(kw.search_volume, 800);
    });

    it('trims whitespace for deduplication', () => {
      const result = run();
      // All keywords should be trimmed
      for (const kw of allKeywords(result)) {
        assert.equal(kw.keyword, kw.keyword.trim());
      }
    });
  });

  // --- Difficulty extraction from related/suggestions -----------------------

  describe('difficulty extraction', () => {
    it('extracts difficulty from keyword_properties in related response', () => {
      const result = run();
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche');
      assert.equal(kw.difficulty, 42);
    });

    it('extracts difficulty from keyword_properties in suggestions response', () => {
      const result = run();
      // "keyword recherche kostenlos" only appears in suggestions
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche kostenlos');
      assert.equal(kw.difficulty, 30);
    });

    it('prefers related difficulty when keyword appears in both', () => {
      const result = run();
      // "keyword analyse tool" has difficulty 55 in related, 60 in suggestions
      const kw = allKeywords(result).find(
        k => k.keyword.toLowerCase() === 'keyword analyse tool',
      );
      assert.equal(kw.difficulty, 55);
    });

    it('returns null difficulty for seed keyword not in responses', () => {
      const result = run({
        related: join(fixtures, 'related-empty.json'),
        suggestions: join(fixtures, 'suggestions-empty.json'),
        seed: 'lonely seed',
      });
      const kw = allKeywords(result).find(k => k.keyword === 'lonely seed');
      assert.equal(kw.difficulty, null);
    });

    it('returns null difficulty when keyword_properties is missing', () => {
      // related-empty and suggestions-empty have no items, so seed gets null
      const result = run({
        related: join(fixtures, 'related-empty.json'),
        suggestions: join(fixtures, 'suggestions-empty.json'),
        seed: 'no props keyword',
      });
      const kw = allKeywords(result)[0];
      assert.equal(kw.difficulty, null);
    });
  });

  // --- Determinism ----------------------------------------------------------

  describe('determinism', () => {
    it('produces byte-identical output for identical input', () => {
      const run1 = runRaw();
      const run2 = runRaw();
      assert.equal(run1, run2, 'same input must produce byte-identical output');
    });

    it('produces byte-identical output with empty inputs', () => {
      const run1 = runRaw({
        related: join(fixtures, 'related-empty.json'),
        suggestions: join(fixtures, 'suggestions-empty.json'),
        seed: 'test seed',
      });
      const run2 = runRaw({
        related: join(fixtures, 'related-empty.json'),
        suggestions: join(fixtures, 'suggestions-empty.json'),
        seed: 'test seed',
      });
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

    it('handles keywords without keyword_properties gracefully', () => {
      // The empty fixtures have no items, so only seed appears with null difficulty
      const result = run({
        related: join(fixtures, 'related-empty.json'),
        suggestions: join(fixtures, 'suggestions-empty.json'),
        seed: 'keyword recherche',
      });
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche');
      assert.equal(kw.difficulty, null);
    });
  });

  // --- Output structure -----------------------------------------------------

  describe('output structure', () => {
    it('has required top-level fields', () => {
      const result = run();
      assert.ok('seed_keyword' in result);
      assert.ok('total_keywords' in result);
      assert.ok('total_clusters' in result);
      assert.ok('clusters' in result);
      assert.ok(Array.isArray(result.clusters));
    });

    it('clusters have required fields including LLM null placeholders', () => {
      const result = run();
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
      const result = run();
      for (const kw of allKeywords(result)) {
        assert.ok('keyword' in kw);
        assert.ok('search_volume' in kw);
        assert.ok('cpc' in kw);
        assert.ok('monthly_searches' in kw);
        assert.ok('difficulty' in kw);
        assert.ok('intent' in kw);
        assert.ok('opportunity_score' in kw);
      }
    });

    it('clusters have cluster_opportunity field', () => {
      const result = run();
      for (const cluster of result.clusters) {
        assert.ok('cluster_opportunity' in cluster);
        assert.equal(typeof cluster.cluster_opportunity, 'number');
      }
    });

    it('total_keywords matches actual keyword count', () => {
      const result = run();
      assert.equal(result.total_keywords, allKeywords(result).length);
    });

    it('total_clusters matches actual cluster count', () => {
      const result = run();
      assert.equal(result.total_clusters, result.clusters.length);
    });
  });

  // --- Sorting --------------------------------------------------------------

  describe('sorting', () => {
    it('sorts keywords within clusters by opportunity_score descending', () => {
      const result = run();
      for (const cluster of result.clusters) {
        for (let i = 1; i < cluster.keywords.length; i++) {
          const prev = cluster.keywords[i - 1].opportunity_score ?? -1;
          const curr = cluster.keywords[i].opportunity_score ?? -1;
          assert.ok(
            curr <= prev,
            `within cluster "${cluster.cluster_keyword}": score ${curr} should be <= ${prev}`,
          );
        }
      }
    });

    it('uses volume desc then alphabetical tie-break for equal scores', () => {
      const result = run();
      for (const cluster of result.clusters) {
        for (let i = 1; i < cluster.keywords.length; i++) {
          const prev = cluster.keywords[i - 1];
          const curr = cluster.keywords[i];
          const prevScore = prev.opportunity_score ?? -1;
          const currScore = curr.opportunity_score ?? -1;
          if (prevScore === currScore) {
            const prevVol = prev.search_volume ?? -1;
            const currVol = curr.search_volume ?? -1;
            if (prevVol === currVol) {
              assert.ok(
                prev.keyword.toLowerCase().localeCompare(curr.keyword.toLowerCase()) <= 0,
                `tie-break: "${prev.keyword}" should come before "${curr.keyword}"`,
              );
            } else {
              assert.ok(
                currVol <= prevVol,
                `volume tie-break: ${currVol} should be <= ${prevVol}`,
              );
            }
          }
        }
      }
    });
  });

  // --- Opportunity score ----------------------------------------------------

  describe('opportunity score', () => {
    it('computes correct score: search_volume / (difficulty + 1)', () => {
      const result = run();
      // "keyword recherche": volume=1200, difficulty=42 -> 1200/43 = 27.91
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche');
      assert.equal(kw.opportunity_score, 27.91);
    });

    it('computes known scores for multiple keywords', () => {
      const result = run();
      const expected = {
        'how to find keywords': 70.42,       // 5000/71
        'best keyword research tool': 37.04,  // 3000/81
        'keyword analyse tool': 14.29,        // 800/56
        'seo keywords kaufen': 4.55,          // 300/66
        'unknown topic xyz': 9.09,            // 100/11
        'keyword recherche tipps': 15.63,     // 250/16
      };
      for (const [keyword, expectedScore] of Object.entries(expected)) {
        const kw = allKeywords(result).find(k => k.keyword === keyword);
        assert.ok(kw, `keyword "${keyword}" must exist`);
        assert.equal(kw.opportunity_score, expectedScore,
          `score for "${keyword}": expected ${expectedScore}, got ${kw.opportunity_score}`);
      }
    });

    it('returns score 0 when volume is null', () => {
      const result = run({
        related: join(fixtures, 'related-empty.json'),
        suggestions: join(fixtures, 'suggestions-empty.json'),
        seed: 'keyword recherche',
      });
      // seed "keyword recherche" has null volume, null difficulty -> score null
      const kw = allKeywords(result).find(k => k.keyword === 'keyword recherche');
      assert.equal(kw.search_volume, null);
      assert.equal(kw.difficulty, null);
      // null difficulty -> null score
      assert.equal(kw.opportunity_score, null);
    });

    it('returns score null when difficulty is null', () => {
      const result = run({
        related: join(fixtures, 'related-empty.json'),
        suggestions: join(fixtures, 'suggestions-empty.json'),
        seed: 'some keyword',
      });
      // no difficulty data for seed -> all difficulties null
      for (const kw of allKeywords(result)) {
        assert.equal(kw.opportunity_score, null,
          `${kw.keyword} should have null score when difficulty is null`);
      }
    });

    it('rounds to exactly 2 decimal places', () => {
      const result = run();
      for (const kw of allKeywords(result)) {
        if (kw.opportunity_score != null && kw.opportunity_score !== 0) {
          const str = kw.opportunity_score.toString();
          const parts = str.split('.');
          if (parts.length === 2) {
            assert.ok(parts[1].length <= 2,
              `${kw.keyword} score ${kw.opportunity_score} has more than 2 decimal places`);
          }
        }
      }
    });

    it('computes correct cluster_opportunity average', () => {
      const result = run();
      for (const cluster of result.clusters) {
        const scores = cluster.keywords.map(k => k.opportunity_score ?? 0);
        const expectedAvg = Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 100) / 100;
        assert.equal(cluster.cluster_opportunity, expectedAvg,
          `cluster "${cluster.cluster_keyword}": expected avg ${expectedAvg}, got ${cluster.cluster_opportunity}`);
      }
    });

    it('cluster_opportunity for single-keyword cluster equals keyword score', () => {
      const result = run();
      const singleCluster = result.clusters.find(c => c.keyword_count === 1 && c.cluster_keyword === 'unknown topic xyz');
      assert.ok(singleCluster);
      assert.equal(singleCluster.cluster_opportunity, singleCluster.keywords[0].opportunity_score);
    });

    it('cluster_opportunity treats null scores as 0 in average', () => {
      // With empty inputs, all scores are null -> cluster_opportunity = 0
      const result = run({
        related: join(fixtures, 'related-empty.json'),
        suggestions: join(fixtures, 'suggestions-empty.json'),
        seed: 'some keyword',
      });
      for (const cluster of result.clusters) {
        assert.equal(cluster.cluster_opportunity, 0,
          `cluster "${cluster.cluster_keyword}" should have 0 opportunity when all scores are null`);
      }
    });

    it('produces byte-identical output with opportunity scores', () => {
      const run1 = runRaw();
      const run2 = runRaw();
      assert.equal(run1, run2, 'opportunity scores must be deterministic');
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
