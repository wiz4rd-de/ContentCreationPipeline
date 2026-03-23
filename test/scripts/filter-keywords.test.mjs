import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { readFileSync, rmSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'keywords', 'filter-keywords.mjs');
const fixtures = join(__dirname, '..', 'fixtures', 'filter-keywords');

function run(opts = {}) {
  const args = [script];
  args.push('--keywords', opts.keywords || join(fixtures, 'keywords-processed.json'));
  args.push('--serp', opts.serp || join(fixtures, 'serp-processed.json'));
  args.push('--seed', opts.seed || 'thailand urlaub');
  if (opts.blocklist) {
    args.push('--blocklist', opts.blocklist);
  }
  if (opts.brands) {
    args.push('--brands', opts.brands);
  }
  const stdout = execFileSync('node', args, { encoding: 'utf-8' });
  return JSON.parse(stdout);
}

function runRaw(opts = {}) {
  const args = [script];
  args.push('--keywords', opts.keywords || join(fixtures, 'keywords-processed.json'));
  args.push('--serp', opts.serp || join(fixtures, 'serp-processed.json'));
  args.push('--seed', opts.seed || 'thailand urlaub');
  if (opts.blocklist) {
    args.push('--blocklist', opts.blocklist);
  }
  if (opts.brands) {
    args.push('--brands', opts.brands);
  }
  return execFileSync('node', args, { encoding: 'utf-8' });
}

// Helper: find a keyword across all clusters
function findKeyword(result, kwText) {
  for (const cluster of result.clusters) {
    for (const kw of cluster.keywords) {
      if (kw.keyword === kwText) return kw;
    }
  }
  return undefined;
}

describe('filter-keywords', () => {

  // --- Blocklist filtering ---------------------------------------------------

  describe('blocklist filtering', () => {
    it('removes ethics keywords (sextourismus)', () => {
      const result = run();
      const kw = findKeyword(result, 'sextourismus thailand');
      assert.ok(kw, 'keyword should still exist in output');
      assert.equal(kw.filter_status, 'removed');
      assert.equal(kw.filter_reason, 'ethics');
    });

    it('removes ethics keywords (elefantenreiten)', () => {
      const result = run();
      const kw = findKeyword(result, 'elefantenreiten thailand');
      assert.ok(kw, 'keyword should still exist in output');
      assert.equal(kw.filter_status, 'removed');
      assert.equal(kw.filter_reason, 'ethics');
    });

    it('removes booking portal keywords as off_topic', () => {
      const result = run();
      const kw1 = findKeyword(result, 'thailand check24');
      assert.ok(kw1);
      assert.equal(kw1.filter_status, 'removed');
      assert.equal(kw1.filter_reason, 'off_topic');

      const kw2 = findKeyword(result, 'thailand booking.com angebote');
      assert.ok(kw2);
      assert.equal(kw2.filter_status, 'removed');
      assert.equal(kw2.filter_reason, 'off_topic');
    });

    it('removes spam pattern keywords as off_topic', () => {
      const result = run();
      const kw = findKeyword(result, 'download free thailand guide torrent');
      assert.ok(kw);
      assert.equal(kw.filter_status, 'removed');
      assert.equal(kw.filter_reason, 'off_topic');
    });

    it('keeps clean keywords', () => {
      const result = run();
      const kw = findKeyword(result, 'thailand urlaub');
      assert.ok(kw);
      assert.equal(kw.filter_status, 'keep');
      assert.equal(kw.filter_reason, null);
    });

    it('uses custom blocklist when --blocklist is provided', () => {
      const result = run({ blocklist: join(fixtures, 'custom-blocklist.json') });
      // Default blocklist terms should not match with custom blocklist
      const kw = findKeyword(result, 'sextourismus thailand');
      assert.ok(kw);
      // Custom blocklist does not have "sextourismus", so it should be kept
      // (unless foreign language filter catches it, which it should not for Latin text)
      assert.equal(kw.filter_status, 'keep');
    });
  });

  // --- Brand filtering -------------------------------------------------------

  describe('brand filtering', () => {
    it('removes keywords matching brand names', () => {
      const result = run({ brands: 'agoda,klook' });
      // None of our test keywords contain these brands, so all non-blocklist
      // keywords should be kept. Let's test with a brand that matches.
      const result2 = run({ brands: 'tui' });
      const kw = findKeyword(result2, 'thailand reise tui');
      assert.ok(kw);
      // tui is also in the default blocklist (booking_portals), so it may
      // be caught by blocklist first. Let's use custom blocklist to isolate brand filter.
      const result3 = run({
        brands: 'tui',
        blocklist: join(fixtures, 'custom-blocklist.json'),
      });
      const kw3 = findKeyword(result3, 'thailand reise tui');
      assert.ok(kw3);
      assert.equal(kw3.filter_status, 'removed');
      assert.equal(kw3.filter_reason, 'brand');
    });

    it('brand match is case-insensitive', () => {
      const result = run({
        brands: 'TUI',
        blocklist: join(fixtures, 'custom-blocklist.json'),
      });
      const kw = findKeyword(result, 'thailand reise tui');
      assert.ok(kw);
      assert.equal(kw.filter_status, 'removed');
      assert.equal(kw.filter_reason, 'brand');
    });

    it('does not filter when no brands specified', () => {
      const result = run({ blocklist: join(fixtures, 'custom-blocklist.json') });
      // With custom blocklist (no matching terms) and no brands,
      // "thailand reise tui" should be kept
      const kw = findKeyword(result, 'thailand reise tui');
      assert.ok(kw);
      assert.equal(kw.filter_status, 'keep');
    });
  });

  // --- Foreign-language filter -----------------------------------------------

  describe('foreign-language filter', () => {
    it('removes keywords with Thai characters', () => {
      const result = run();
      const kw = findKeyword(result, '\u0e17\u0e48\u0e2d\u0e07\u0e40\u0e17\u0e35\u0e48\u0e22\u0e27\u0e44\u0e17\u0e22');
      assert.ok(kw, 'Thai keyword should still exist in output');
      assert.equal(kw.filter_status, 'removed');
      assert.equal(kw.filter_reason, 'foreign_language');
    });

    it('keeps German/Latin keywords', () => {
      const result = run();
      const kw = findKeyword(result, 'thailand wetter');
      assert.ok(kw);
      assert.equal(kw.filter_status, 'keep');
    });
  });

  // --- Tagging (audit trail) -------------------------------------------------

  describe('keyword tagging', () => {
    it('tags every keyword with filter_status', () => {
      const result = run();
      for (const cluster of result.clusters) {
        for (const kw of cluster.keywords) {
          assert.ok(
            kw.filter_status === 'keep' || kw.filter_status === 'removed',
            `keyword "${kw.keyword}" should have filter_status`,
          );
        }
      }
    });

    it('removed keywords have filter_reason, kept have null', () => {
      const result = run();
      for (const cluster of result.clusters) {
        for (const kw of cluster.keywords) {
          if (kw.filter_status === 'removed') {
            assert.ok(kw.filter_reason, `removed keyword "${kw.keyword}" needs filter_reason`);
          } else {
            assert.equal(kw.filter_reason, null);
          }
        }
      }
    });

    it('preserves original keyword data alongside filter tags', () => {
      const result = run();
      const kw = findKeyword(result, 'thailand urlaub');
      assert.ok(kw);
      assert.equal(kw.search_volume, 5000);
      assert.equal(kw.difficulty, 40);
      assert.equal(kw.opportunity_score, 121.95);
    });
  });

  // --- Removal summary -------------------------------------------------------

  describe('removal summary', () => {
    it('counts removals by reason', () => {
      const result = run();
      assert.equal(result.removal_summary.ethics, 2); // sextourismus, elefantenreiten
      assert.equal(result.removal_summary.foreign_language, 1); // Thai text
      // check24, booking.com, tui, torrent (spam) -> off_topic
      assert.equal(result.removal_summary.off_topic, 4);
      assert.equal(result.removal_summary.brand, 0); // no brands specified
    });

    it('total_keywords equals sum of filtered + removed', () => {
      const result = run();
      assert.equal(result.total_keywords, result.filtered_keywords + result.removed_count);
    });

    it('removed_count matches sum of removal_summary values', () => {
      const result = run();
      const summaryTotal = result.removal_summary.ethics +
        result.removal_summary.brand +
        result.removal_summary.off_topic +
        result.removal_summary.foreign_language;
      assert.equal(result.removed_count, summaryTotal);
    });
  });

  // --- FAQ prioritization ----------------------------------------------------

  describe('FAQ scoring', () => {
    it('scores PAA questions by keyword overlap', () => {
      const result = run();
      assert.ok(Array.isArray(result.faq_selection));
      assert.ok(result.faq_selection.length > 0);
      for (const faq of result.faq_selection) {
        assert.ok('question' in faq);
        assert.ok('priority' in faq);
        assert.ok('relevance_score' in faq);
        assert.equal(typeof faq.relevance_score, 'number');
      }
    });

    it('sorts FAQs by relevance score descending', () => {
      const result = run();
      for (let i = 1; i < result.faq_selection.length; i++) {
        assert.ok(
          result.faq_selection[i].relevance_score <= result.faq_selection[i - 1].relevance_score,
          'FAQs should be sorted by relevance_score descending',
        );
      }
    });

    it('assigns priority tiers: pflicht, empfohlen, optional', () => {
      const result = run();
      const priorities = new Set(result.faq_selection.map(f => f.priority));
      // With 5 questions, we expect at least pflicht and optional
      for (const p of priorities) {
        assert.ok(
          p === 'pflicht' || p === 'empfohlen' || p === 'optional',
          `priority "${p}" must be pflicht, empfohlen, or optional`,
        );
      }
    });

    it('questions with more keyword overlaps score higher', () => {
      const result = run();
      // "Was kostet ein Urlaub in Thailand?" contains "urlaub" and "thailand"
      // which are both keep tokens -> should score well
      const urlaubQ = result.faq_selection.find(f =>
        f.question.includes('Urlaub in Thailand')
      );
      assert.ok(urlaubQ, 'urlaub question should be in faq_selection');
      assert.ok(urlaubQ.relevance_score >= 2, 'should match at least urlaub and thailand');
    });

    it('returns empty faq_selection for empty serp', () => {
      const result = run({
        serp: join(fixtures, 'serp-processed-empty.json'),
      });
      assert.equal(result.faq_selection.length, 0);
    });
  });

  // --- Output structure ------------------------------------------------------

  describe('output structure', () => {
    it('has all required top-level fields', () => {
      const result = run();
      const requiredKeys = [
        'seed_keyword', 'total_keywords', 'filtered_keywords',
        'removed_count', 'removal_summary', 'clusters', 'faq_selection',
      ];
      for (const key of requiredKeys) {
        assert.ok(key in result, `missing top-level key: ${key}`);
      }
    });

    it('preserves cluster structure', () => {
      const result = run();
      assert.equal(result.clusters.length, 3);
      for (const cluster of result.clusters) {
        assert.ok('cluster_keyword' in cluster);
        assert.ok('keywords' in cluster);
        assert.ok(Array.isArray(cluster.keywords));
      }
    });

    it('seed_keyword matches input', () => {
      const result = run();
      assert.equal(result.seed_keyword, 'thailand urlaub');
    });
  });

  // --- Empty inputs ----------------------------------------------------------

  describe('empty inputs', () => {
    it('handles empty keywords gracefully', () => {
      const result = run({
        keywords: join(fixtures, 'keywords-processed-empty.json'),
        serp: join(fixtures, 'serp-processed-empty.json'),
        seed: 'empty test',
      });
      assert.equal(result.seed_keyword, 'empty test');
      assert.equal(result.total_keywords, 0);
      assert.equal(result.filtered_keywords, 0);
      assert.equal(result.removed_count, 0);
      assert.equal(result.clusters.length, 0);
      assert.equal(result.faq_selection.length, 0);
    });
  });

  // --- Determinism -----------------------------------------------------------

  describe('determinism', () => {
    it('produces byte-identical output for identical input', () => {
      const run1 = runRaw();
      const run2 = runRaw();
      assert.equal(run1, run2, 'same input must produce byte-identical output');
    });

    it('produces byte-identical output with brands', () => {
      const run1 = runRaw({ brands: 'agoda,klook' });
      const run2 = runRaw({ brands: 'agoda,klook' });
      assert.equal(run1, run2, 'same input must produce byte-identical output');
    });

    it('produces byte-identical output with custom blocklist', () => {
      const run1 = runRaw({ blocklist: join(fixtures, 'custom-blocklist.json') });
      const run2 = runRaw({ blocklist: join(fixtures, 'custom-blocklist.json') });
      assert.equal(run1, run2, 'same input must produce byte-identical output');
    });

    it('produces byte-identical output with empty inputs', () => {
      const run1 = runRaw({
        keywords: join(fixtures, 'keywords-processed-empty.json'),
        serp: join(fixtures, 'serp-processed-empty.json'),
        seed: 'empty test',
      });
      const run2 = runRaw({
        keywords: join(fixtures, 'keywords-processed-empty.json'),
        serp: join(fixtures, 'serp-processed-empty.json'),
        seed: 'empty test',
      });
      assert.equal(run1, run2, 'same input must produce byte-identical output');
    });
  });

  // --- --output flag ----------------------------------------------------------

  describe('--output flag', () => {
    it('writes JSON to file when --output is provided', () => {
      const dir = join(tmpdir(), 'fk-test-' + randomBytes(4).toString('hex'));
      mkdirSync(dir, { recursive: true });
      const outFile = join(dir, 'result.json');
      try {
        const proc = spawnSync('node', [
          script,
          '--keywords', join(fixtures, 'keywords-processed.json'),
          '--serp', join(fixtures, 'serp-processed.json'),
          '--seed', 'thailand urlaub',
          '--output', outFile,
        ], { encoding: 'utf-8' });
        assert.equal(proc.status, 0, 'must exit with code 0');
        assert.equal(proc.stdout, '', 'stdout must be empty when --output is used');
        const written = JSON.parse(readFileSync(outFile, 'utf-8'));
        assert.equal(written.seed_keyword, 'thailand urlaub');
        assert.ok(Array.isArray(written.clusters), 'file must contain clusters');
        assert.ok(Array.isArray(written.faq_selection), 'file must contain faq_selection');
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('still writes to stdout when --output is omitted', () => {
      const stdout = runRaw();
      const parsed = JSON.parse(stdout);
      assert.equal(parsed.seed_keyword, 'thailand urlaub');
    });
  });

  // --- CLI validation --------------------------------------------------------

  describe('CLI validation', () => {
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

    it('exits with error when --seed is missing', () => {
      assert.throws(
        () => execFileSync('node', [
          script,
          '--keywords', join(fixtures, 'keywords-processed.json'),
          '--serp', join(fixtures, 'serp-processed.json'),
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
