import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'keywords', 'prepare-strategist-data.mjs');
const fixtures = join(__dirname, '..', 'fixtures', 'prepare-strategist-data');

function run(opts = {}) {
  const args = [script];
  args.push('--serp', opts.serp || join(fixtures, 'serp-processed.json'));
  args.push('--keywords', opts.keywords || join(fixtures, 'keywords-processed.json'));
  args.push('--seed', opts.seed || 'seo reporting');
  if (opts.competitorKws) {
    args.push('--competitor-kws', opts.competitorKws);
  }
  const stdout = execFileSync('node', args, { encoding: 'utf-8' });
  return JSON.parse(stdout);
}

function runRaw(opts = {}) {
  const args = [script];
  args.push('--serp', opts.serp || join(fixtures, 'serp-processed.json'));
  args.push('--keywords', opts.keywords || join(fixtures, 'keywords-processed.json'));
  args.push('--seed', opts.seed || 'seo reporting');
  if (opts.competitorKws) {
    args.push('--competitor-kws', opts.competitorKws);
  }
  return execFileSync('node', args, { encoding: 'utf-8' });
}

describe('prepare-strategist-data', () => {

  // --- Year normalization dedup ---------------------------------------------

  describe('dedup with year normalization', () => {
    it('merges keywords differing only by year', () => {
      const result = run();
      // "seo reporting 2025" and "seo reporting 2026" differ only by year
      // Should keep the one with higher volume (2025 has 200 vs 2026 has 150)
      const yearKws = result.all_keywords.filter(k =>
        k.keyword.toLowerCase().startsWith('seo reporting 202')
      );
      assert.equal(yearKws.length, 1, 'year variants should be merged into one');
      assert.equal(yearKws[0].keyword, 'seo reporting 2025');
      assert.equal(yearKws[0].search_volume, 200);
    });

    it('merges case-duplicate keywords', () => {
      const result = run();
      // "seo reporting" and "SEO Reporting" are case duplicates
      const matches = result.all_keywords.filter(k =>
        k.keyword.toLowerCase() === 'seo reporting'
      );
      assert.equal(matches.length, 1, 'case duplicates should be merged');
    });

    it('reports correct year_dedup_count in stats', () => {
      const result = run();
      // 8 raw -> 6 after dedup = 2 removed
      assert.equal(result.stats.year_dedup_count, 2);
    });
  });

  // --- Foreign-language filter ----------------------------------------------

  describe('foreign-language filter', () => {
    it('filters keywords with Cyrillic characters', () => {
      const result = run();
      const cyrillic = result.all_keywords.find(k =>
        k.keyword.includes('\u0441\u0435\u043e')
      );
      assert.equal(cyrillic, undefined, 'Cyrillic keywords should be filtered');
    });

    it('filters keywords with CJK characters', () => {
      const result = run();
      const cjk = result.all_keywords.find(k =>
        k.keyword.includes('\u5e7f\u544a')
      );
      assert.equal(cjk, undefined, 'CJK keywords should be filtered');
    });

    it('keeps Latin-script keywords including extended Latin', () => {
      const result = run();
      const kept = result.all_keywords.find(k => k.keyword === 'seo report erstellen');
      assert.ok(kept, 'Latin-script keywords should be kept');
    });

    it('reports correct foreign_filtered_count in stats', () => {
      const result = run();
      // 6 after dedup, 2 foreign removed = 4 remaining
      assert.equal(result.stats.foreign_filtered_count, 2);
    });
  });

  // --- PAA questions --------------------------------------------------------

  describe('PAA questions', () => {
    it('extracts questions from serp_features.people_also_ask', () => {
      const result = run();
      assert.equal(result.paa_questions.length, 3);
    });

    it('formats questions with question and answer fields', () => {
      const result = run();
      for (const paa of result.paa_questions) {
        assert.ok('question' in paa);
        assert.ok('answer' in paa);
        assert.equal(typeof paa.question, 'string');
        // answer may be null or a string depending on source data
        const validType = (paa.answer === null || typeof paa.answer === 'string');
        assert.ok(validType, 'answer must be null or string');
      }
    });

    it('preserves question text exactly', () => {
      const result = run();
      const questions = result.paa_questions.map(p => p.question);
      assert.ok(questions.includes('Was ist SEO Reporting?'));
      assert.ok(questions.includes('How to create an SEO report?'));
      assert.ok(questions.includes('Welche KPIs geh\u00f6ren in einen SEO Report?'));
    });

    it('returns empty array when no PAA in serp data', () => {
      const result = run({
        serp: join(fixtures, 'serp-processed-empty.json'),
        keywords: join(fixtures, 'keywords-processed-empty.json'),
        seed: 'empty test',
      });
      assert.equal(result.paa_questions.length, 0);
    });
  });

  // --- SERP snippets --------------------------------------------------------

  describe('SERP snippets', () => {
    it('extracts title and description from competitors', () => {
      const result = run();
      assert.equal(result.serp_snippets.length, 2);
      assert.equal(result.serp_snippets[0].title, 'SEO Reporting: Der ultimative Leitfaden 2025');
      assert.equal(result.serp_snippets[0].rank, 1);
    });

    it('includes url and domain in snippets', () => {
      const result = run();
      for (const snippet of result.serp_snippets) {
        assert.ok('url' in snippet);
        assert.ok('domain' in snippet);
        assert.ok('rank' in snippet);
        assert.ok('title' in snippet);
        assert.ok('description' in snippet);
      }
    });

    it('returns empty array when no competitors in serp data', () => {
      const result = run({
        serp: join(fixtures, 'serp-processed-empty.json'),
        keywords: join(fixtures, 'keywords-processed-empty.json'),
        seed: 'empty test',
      });
      assert.equal(result.serp_snippets.length, 0);
    });
  });

  // --- Empty inputs ---------------------------------------------------------

  describe('empty inputs', () => {
    it('handles empty keywords and empty serp gracefully', () => {
      const result = run({
        serp: join(fixtures, 'serp-processed-empty.json'),
        keywords: join(fixtures, 'keywords-processed-empty.json'),
        seed: 'empty test',
      });
      assert.equal(result.seed_keyword, 'empty test');
      assert.equal(result.all_keywords.length, 0);
      assert.equal(result.top_keywords.length, 0);
      assert.equal(result.paa_questions.length, 0);
      assert.equal(result.serp_snippets.length, 0);
      assert.equal(result.autocomplete.length, 0);
      assert.equal(result.content_ideas.length, 0);
      assert.equal(result.stats.total_keywords, 0);
    });

    it('has zero stats for empty inputs', () => {
      const result = run({
        serp: join(fixtures, 'serp-processed-empty.json'),
        keywords: join(fixtures, 'keywords-processed-empty.json'),
        seed: 'empty test',
      });
      assert.equal(result.stats.total_search_volume, 0);
      assert.equal(result.stats.avg_search_volume, 0);
      assert.equal(result.stats.avg_difficulty, null);
      assert.equal(result.stats.foreign_filtered_count, 0);
      assert.equal(result.stats.year_dedup_count, 0);
    });
  });

  // --- Competitor keywords (optional) ---------------------------------------

  describe('competitor keywords', () => {
    it('includes competitor keywords when file is provided', () => {
      const result = run({
        competitorKws: join(fixtures, 'competitor-kws.json'),
      });
      assert.equal(result.competitor_keywords.length, 2);
      // Sorted by volume desc
      assert.equal(result.competitor_keywords[0].keyword, 'seo monitoring tool');
      assert.equal(result.competitor_keywords[0].search_volume, 300);
    });

    it('returns empty array when no competitor-kws flag', () => {
      const result = run();
      assert.equal(result.competitor_keywords.length, 0);
    });
  });

  // --- Output structure -----------------------------------------------------

  describe('output structure', () => {
    it('has all required top-level sections', () => {
      const result = run();
      const requiredKeys = [
        'seed_keyword', 'top_keywords', 'all_keywords',
        'autocomplete', 'content_ideas', 'paa_questions',
        'serp_snippets', 'competitor_keywords', 'stats',
      ];
      for (const key of requiredKeys) {
        assert.ok(key in result, `missing top-level key: ${key}`);
      }
    });

    it('top_keywords is at most 20 entries', () => {
      const result = run();
      assert.ok(result.top_keywords.length <= 20);
    });

    it('top_keywords entries have required fields', () => {
      const result = run();
      for (const kw of result.top_keywords) {
        assert.ok('keyword' in kw);
        assert.ok('search_volume' in kw);
        assert.ok('difficulty' in kw);
        assert.ok('intent' in kw);
        assert.ok('opportunity_score' in kw);
      }
    });

    it('stats has all required fields', () => {
      const result = run();
      const statsKeys = [
        'total_keywords', 'keywords_with_volume', 'total_search_volume',
        'avg_search_volume', 'avg_difficulty', 'paa_count',
        'serp_snippet_count', 'competitor_keyword_count',
        'foreign_filtered_count', 'year_dedup_count',
      ];
      for (const key of statsKeys) {
        assert.ok(key in result.stats, `missing stats key: ${key}`);
      }
    });
  });

  // --- Autocomplete and content ideas ---------------------------------------

  describe('autocomplete and content ideas', () => {
    it('autocomplete contains keywords that include the seed', () => {
      const result = run();
      for (const kw of result.autocomplete) {
        assert.ok(
          kw.toLowerCase().includes('seo reporting'),
          `autocomplete "${kw}" should contain the seed`,
        );
      }
    });

    it('content ideas do not contain the seed phrase', () => {
      const result = run();
      for (const kw of result.content_ideas) {
        // content ideas should NOT contain the seed as a substring
        assert.ok(
          kw.toLowerCase().includes('seo reporting') === false,
          `content idea "${kw}" should not contain the seed`,
        );
      }
    });

    it('seed keyword itself is excluded from both lists', () => {
      const result = run();
      assert.ok(
        result.autocomplete.includes('seo reporting') === false,
        'seed should not be in autocomplete',
      );
      assert.ok(
        result.content_ideas.includes('seo reporting') === false,
        'seed should not be in content ideas',
      );
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
        serp: join(fixtures, 'serp-processed-empty.json'),
        keywords: join(fixtures, 'keywords-processed-empty.json'),
        seed: 'empty test',
      });
      const run2 = runRaw({
        serp: join(fixtures, 'serp-processed-empty.json'),
        keywords: join(fixtures, 'keywords-processed-empty.json'),
        seed: 'empty test',
      });
      assert.equal(run1, run2, 'same input must produce byte-identical output');
    });

    it('produces byte-identical output with competitor keywords', () => {
      const run1 = runRaw({ competitorKws: join(fixtures, 'competitor-kws.json') });
      const run2 = runRaw({ competitorKws: join(fixtures, 'competitor-kws.json') });
      assert.equal(run1, run2, 'same input must produce byte-identical output');
    });
  });

  // --- CLI validation -------------------------------------------------------

  describe('CLI validation', () => {
    it('exits with error when --serp is missing', () => {
      assert.throws(
        () => execFileSync('node', [
          script,
          '--keywords', join(fixtures, 'keywords-processed.json'),
          '--seed', 'test',
        ], { encoding: 'utf-8', stdio: 'pipe' }),
        (err) => {
          assert.equal(err.status, 1);
          assert.ok(err.stderr.includes('Usage'));
          return true;
        },
      );
    });

    it('exits with error when --keywords is missing', () => {
      assert.throws(
        () => execFileSync('node', [
          script,
          '--serp', join(fixtures, 'serp-processed.json'),
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
          '--serp', join(fixtures, 'serp-processed.json'),
          '--keywords', join(fixtures, 'keywords-processed.json'),
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
