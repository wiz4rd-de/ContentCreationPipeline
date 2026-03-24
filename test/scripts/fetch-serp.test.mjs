import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

import {
  parseArgs,
  loadEnv,
  resolveLocation,
  extractTaskId,
  isTaskReady,
  calculateBackoff,
  checkCache,
  deriveOutdir,
  buildLiveUrl,
  shouldFallback,
} from '../../src/serp/fetch-serp.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixtures = join(__dirname, '..', 'fixtures', 'fetch-serp');

function loadFixture(name) {
  return JSON.parse(readFileSync(join(fixtures, name), 'utf-8'));
}

function makeTmpDir() {
  const dir = join(tmpdir(), 'fetch-serp-test-' + randomBytes(4).toString('hex'));
  mkdirSync(dir, { recursive: true });
  return dir;
}

describe('fetch-serp', () => {

  // --- parseArgs ---

  describe('parseArgs', () => {
    it('extracts keyword from positional argument', () => {
      const result = parseArgs(['urlaub mallorca', '--market', 'de', '--language', 'de', '--outdir', '/tmp/out']);
      assert.equal(result.keyword, 'urlaub mallorca');
    });

    it('extracts --market, --language, --outdir flags', () => {
      const result = parseArgs(['test keyword', '--market', 'de', '--language', 'en', '--outdir', '/tmp/test']);
      assert.equal(result.market, 'de');
      assert.equal(result.language, 'en');
      assert.equal(result.outdir, '/tmp/test');
    });

    it('uses default depth of 10 when not specified', () => {
      const result = parseArgs(['kw', '--market', 'de', '--language', 'de', '--outdir', '/tmp/o']);
      assert.equal(result.depth, 10);
    });

    it('uses default timeout of 120 when not specified', () => {
      const result = parseArgs(['kw', '--market', 'de', '--language', 'de', '--outdir', '/tmp/o']);
      assert.equal(result.timeout, 120);
    });

    it('returns custom depth when --depth is provided', () => {
      const result = parseArgs(['kw', '--market', 'de', '--language', 'de', '--outdir', '/tmp/o', '--depth', '50']);
      assert.equal(result.depth, 50);
    });

    it('returns custom timeout when --timeout is provided', () => {
      const result = parseArgs(['kw', '--market', 'de', '--language', 'de', '--outdir', '/tmp/o', '--timeout', '300']);
      assert.equal(result.timeout, 300);
    });

    it('sets force to false when --force is not present', () => {
      const result = parseArgs(['kw', '--market', 'de', '--language', 'de', '--outdir', '/tmp/o']);
      assert.equal(result.force, false);
    });

    it('sets force to true when --force is included', () => {
      const result = parseArgs(['kw', '--market', 'de', '--language', 'de', '--outdir', '/tmp/o', '--force']);
      assert.equal(result.force, true);
    });

    it('returns undefined for outdir when --outdir is omitted', () => {
      const result = parseArgs(['kw', '--market', 'de', '--language', 'de']);
      assert.equal(result.outdir, undefined);
    });

    it('returns default maxAge of 7 when --max-age is not provided', () => {
      const result = parseArgs(['kw', '--market', 'de', '--language', 'de']);
      assert.equal(result.maxAge, 7);
    });

    it('returns custom maxAge when --max-age is provided', () => {
      const result = parseArgs(['kw', '--market', 'de', '--language', 'de', '--max-age', '14']);
      assert.equal(result.maxAge, 14);
    });
  });

  // --- parseArgs - fallbackTimeout ---

  describe('parseArgs - fallbackTimeout', () => {
    it('returns default fallbackTimeout of 300 when not specified', () => {
      const result = parseArgs(['kw', '--market', 'de', '--language', 'de']);
      assert.equal(result.fallbackTimeout, 300);
    });

    it('returns custom fallbackTimeout when --fallback-timeout is provided', () => {
      const result = parseArgs(['kw', '--market', 'de', '--language', 'de', '--fallback-timeout', '600']);
      assert.equal(result.fallbackTimeout, 600);
    });

    it('returns 0 when --fallback-timeout 0 is provided (disabled)', () => {
      const result = parseArgs(['kw', '--market', 'de', '--language', 'de', '--fallback-timeout', '0']);
      assert.equal(result.fallbackTimeout, 0);
    });
  });

  // --- loadEnv ---

  describe('loadEnv', () => {
    it('parses valid api.env content', () => {
      const dir = makeTmpDir();
      const envFile = join(dir, 'api.env');
      try {
        writeFileSync(envFile, 'DATAFORSEO_AUTH=abc123\nDATAFORSEO_BASE=https://api.example.com\n');
        const result = loadEnv(envFile);
        assert.equal(result.auth, 'abc123');
        assert.equal(result.base, 'https://api.example.com');
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('skips comment lines and empty lines', () => {
      const dir = makeTmpDir();
      const envFile = join(dir, 'api.env');
      try {
        writeFileSync(envFile, '# This is a comment\n\nDATAFORSEO_AUTH=secret\n\n# Another comment\nDATAFORSEO_BASE=https://api.test.com\n');
        const result = loadEnv(envFile);
        assert.equal(result.auth, 'secret');
        assert.equal(result.base, 'https://api.test.com');
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('throws when DATAFORSEO_AUTH is missing', () => {
      const dir = makeTmpDir();
      const envFile = join(dir, 'api.env');
      try {
        writeFileSync(envFile, 'DATAFORSEO_BASE=https://api.test.com\n');
        assert.throws(
          () => loadEnv(envFile),
          (err) => {
            assert.ok(err.message.includes('DATAFORSEO_AUTH'));
            return true;
          },
        );
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('throws when DATAFORSEO_BASE is missing', () => {
      const dir = makeTmpDir();
      const envFile = join(dir, 'api.env');
      try {
        writeFileSync(envFile, 'DATAFORSEO_AUTH=secret\n');
        assert.throws(
          () => loadEnv(envFile),
          (err) => {
            assert.ok(err.message.includes('DATAFORSEO_BASE'));
            return true;
          },
        );
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });
  });

  // --- resolveLocation ---

  describe('resolveLocation', () => {
    it('resolves de to 2276', () => {
      assert.equal(resolveLocation('de'), 2276);
    });

    it('resolves us to 2840', () => {
      assert.equal(resolveLocation('us'), 2840);
    });

    it('handles case-insensitive input', () => {
      assert.equal(resolveLocation('DE'), 2276);
      assert.equal(resolveLocation('De'), 2276);
      assert.equal(resolveLocation('US'), 2840);
    });

    it('throws for unknown market code', () => {
      assert.throws(
        () => resolveLocation('zz'),
        (err) => {
          assert.ok(err.message.includes('Unknown market'));
          assert.ok(err.message.includes('zz'));
          return true;
        },
      );
    });
  });

  // --- extractTaskId ---

  describe('extractTaskId', () => {
    it('extracts UUID from successful task_post response', () => {
      const fixture = loadFixture('task-post-success.json');
      const taskId = extractTaskId(fixture);
      assert.equal(taskId, '03101504-6886-0139-0000-3d651db5c686');
    });

    it('throws for error response', () => {
      const fixture = loadFixture('task-post-error.json');
      assert.throws(
        () => extractTaskId(fixture),
        (err) => {
          assert.ok(err.message.includes('40501'));
          return true;
        },
      );
    });

    it('throws when tasks array is empty', () => {
      const response = { tasks: [] };
      assert.throws(
        () => extractTaskId(response),
        (err) => {
          assert.ok(err.message.includes('no tasks'));
          return true;
        },
      );
    });
  });

  // --- isTaskReady ---

  describe('isTaskReady', () => {
    const TARGET_TASK_ID = '03101504-6886-0139-0000-3d651db5c686';

    it('returns true when task ID is in tasks_ready response', () => {
      const fixture = loadFixture('tasks-ready-with-target.json');
      const result = isTaskReady(fixture, TARGET_TASK_ID);
      assert.ok(result !== false, 'should find the task');
      assert.equal(result.ready, true);
    });

    it('returns false when task ID is not present', () => {
      const fixture = loadFixture('tasks-ready-without-target.json');
      const result = isTaskReady(fixture, TARGET_TASK_ID);
      assert.equal(result, false);
    });

    it('returns endpoint_advanced URL when task is found', () => {
      const fixture = loadFixture('tasks-ready-with-target.json');
      const result = isTaskReady(fixture, TARGET_TASK_ID);
      assert.ok(result !== false);
      assert.ok(typeof result.endpoint_advanced === 'string');
      assert.ok(result.endpoint_advanced.includes(TARGET_TASK_ID));
    });
  });

  // --- calculateBackoff ---

  describe('calculateBackoff', () => {
    const opts = { initialDelay: 5000, factor: 1.5, maxDelay: 30000 };

    it('returns initialDelay (5000ms) for attempt 0', () => {
      assert.equal(calculateBackoff(0, opts), 5000);
    });

    it('returns initialDelay * factor for attempt 1 (7500ms for factor 1.5)', () => {
      assert.equal(calculateBackoff(1, opts), 7500);
    });

    it('caps at maxDelay (30000ms) for high attempt numbers', () => {
      assert.equal(calculateBackoff(100, opts), 30000);
      assert.equal(calculateBackoff(50, opts), 30000);
    });

    it('produces deterministic output for same inputs (run twice, compare)', () => {
      const run1 = calculateBackoff(0, opts);
      const run2 = calculateBackoff(0, opts);
      assert.equal(run1, run2, 'same input must produce identical output');

      const run3 = calculateBackoff(3, opts);
      const run4 = calculateBackoff(3, opts);
      assert.equal(run3, run4, 'same input must produce identical output');

      const run5 = calculateBackoff(100, opts);
      const run6 = calculateBackoff(100, opts);
      assert.equal(run5, run6, 'same input must produce identical output');
    });
  });

  // --- checkCache ---

  describe('checkCache', () => {
    it('returns hit:false with reason when file does not exist', () => {
      const dir = makeTmpDir();
      try {
        const result = checkCache(join(dir, 'nonexistent.json'));
        assert.equal(result.hit, false);
        assert.equal(result.reason, 'file not found');
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('returns hit:false with reason when file contains malformed JSON', () => {
      const dir = makeTmpDir();
      try {
        writeFileSync(join(dir, 'serp-raw.json'), '{broken');
        const result = checkCache(join(dir, 'serp-raw.json'));
        assert.equal(result.hit, false);
        assert.equal(result.reason, 'invalid JSON');
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('returns hit:false when tasks array is empty', () => {
      const dir = makeTmpDir();
      try {
        writeFileSync(join(dir, 'serp-raw.json'), JSON.stringify({ tasks: [] }));
        const result = checkCache(join(dir, 'serp-raw.json'));
        assert.equal(result.hit, false);
        assert.equal(result.reason, 'missing or empty tasks array');
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('returns hit:false when result key is missing from first task', () => {
      const dir = makeTmpDir();
      try {
        const data = { tasks: [{ id: 'abc', status_code: 20000 }] };
        writeFileSync(join(dir, 'serp-raw.json'), JSON.stringify(data));
        const result = checkCache(join(dir, 'serp-raw.json'));
        assert.equal(result.hit, false);
        assert.equal(result.reason, 'missing or empty result array');
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('returns hit:false when items array is empty', () => {
      const dir = makeTmpDir();
      try {
        const data = { tasks: [{ result: [{ items: [] }] }] };
        writeFileSync(join(dir, 'serp-raw.json'), JSON.stringify(data));
        const result = checkCache(join(dir, 'serp-raw.json'));
        assert.equal(result.hit, false);
        assert.equal(result.reason, 'missing or empty items array');
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('returns hit:true with data for a valid fixture', () => {
      const fixturePath = join(fixtures, 'task-get-success.json');
      const result = checkCache(fixturePath);
      assert.equal(result.hit, true);
      assert.ok(result.data !== undefined && result.data !== null);
      // Verify the keyword is accessible in the returned data
      const keyword = result.data.tasks[0].data.keyword;
      assert.equal(keyword, 'Urlaub Mallorca');
    });

    it('returns hit:true when keyword parameter matches cached keyword', () => {
      const fixturePath = join(fixtures, 'task-get-success.json');
      const result = checkCache(fixturePath, 'Urlaub Mallorca');
      assert.equal(result.hit, true);
    });

    it('returns hit:false with keyword mismatch reason when keywords differ', () => {
      const fixturePath = join(fixtures, 'task-get-success.json');
      const result = checkCache(fixturePath, 'schönste strände thailand');
      assert.equal(result.hit, false);
      assert.ok(result.reason.includes('keyword mismatch'));
      assert.ok(result.reason.includes('Urlaub Mallorca'));
      assert.ok(result.reason.includes('schönste strände thailand'));
    });

    it('returns hit:true when keyword parameter is omitted (backwards compat)', () => {
      const fixturePath = join(fixtures, 'task-get-success.json');
      const result = checkCache(fixturePath);
      assert.equal(result.hit, true);
    });

    it('returns hit:true when _pipeline_fetched_at is 3 days ago and TTL is 7 days', () => {
      const dir = makeTmpDir();
      try {
        const fetchedAt = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
        const data = {
          _pipeline_fetched_at: fetchedAt,
          tasks: [{ data: { keyword: 'test' }, result: [{ datetime: fetchedAt, items: [{ type: 'organic' }] }] }],
        };
        writeFileSync(join(dir, 'serp-raw.json'), JSON.stringify(data));
        const result = checkCache(join(dir, 'serp-raw.json'), undefined, 7);
        assert.equal(result.hit, true);
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('returns hit:false with reason "expired" when _pipeline_fetched_at is 10 days ago and TTL is 7 days', () => {
      const dir = makeTmpDir();
      try {
        const fetchedAt = new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString();
        const data = {
          _pipeline_fetched_at: fetchedAt,
          tasks: [{ data: { keyword: 'test' }, result: [{ datetime: fetchedAt, items: [{ type: 'organic' }] }] }],
        };
        writeFileSync(join(dir, 'serp-raw.json'), JSON.stringify(data));
        const result = checkCache(join(dir, 'serp-raw.json'), undefined, 7);
        assert.equal(result.hit, false);
        assert.equal(result.reason, 'expired');
        assert.ok(typeof result.ageDays === 'number', 'ageDays should be a number');
        assert.ok(result.ageDays >= 10, `Expected ageDays >= 10, got ${result.ageDays}`);
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('falls back to tasks[0].result[0].datetime when _pipeline_fetched_at is absent and entry is fresh', () => {
      const dir = makeTmpDir();
      try {
        const datetime = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString().replace('T', ' ').replace('Z', ' +00:00');
        const data = {
          tasks: [{ data: { keyword: 'test' }, result: [{ datetime, items: [{ type: 'organic' }] }] }],
        };
        writeFileSync(join(dir, 'serp-raw.json'), JSON.stringify(data));
        const result = checkCache(join(dir, 'serp-raw.json'), undefined, 7);
        assert.equal(result.hit, true);
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('treats cache as valid when no timestamp is present (backward compatibility)', () => {
      const dir = makeTmpDir();
      try {
        const data = {
          tasks: [{ data: { keyword: 'test' }, result: [{ items: [{ type: 'organic' }] }] }],
        };
        writeFileSync(join(dir, 'serp-raw.json'), JSON.stringify(data));
        const result = checkCache(join(dir, 'serp-raw.json'), undefined, 7);
        assert.equal(result.hit, true);
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('TTL validation is skipped when maxAgeDays is not provided', () => {
      // Use the fixture with a known old timestamp — should still be a hit without TTL arg
      const fixturePath = join(fixtures, 'serp-raw-with-timestamp.json');
      const result = checkCache(fixturePath, 'Urlaub Mallorca');
      assert.equal(result.hit, true);
    });
  });

  // --- buildLiveUrl ---

  describe('buildLiveUrl', () => {
    it('returns the correct live/advanced endpoint URL', () => {
      const result = buildLiveUrl('https://api.dataforseo.com/v3');
      assert.equal(result, 'https://api.dataforseo.com/v3/serp/google/organic/live/advanced');
    });
  });

  // --- shouldFallback ---

  describe('shouldFallback', () => {
    it('returns false when elapsed time is below threshold', () => {
      assert.equal(shouldFallback(299999, 300), false);
    });

    it('returns true when elapsed time equals threshold', () => {
      assert.equal(shouldFallback(300000, 300), true);
    });

    it('returns true when elapsed time exceeds threshold', () => {
      assert.equal(shouldFallback(400000, 300), true);
    });

    it('returns false when fallback is disabled (timeout = 0)', () => {
      assert.equal(shouldFallback(999999, 0), false);
    });
  });

  // --- pipeline source annotation ---

  describe('pipeline source annotation', () => {
    const mockResponse = {
      tasks: [{ data: { keyword: 'test' }, result: [{ datetime: '2026-03-24', items: [{ type: 'organic' }] }] }],
    };

    it('async path produces object with _pipeline_source "async"', () => {
      const result = { _pipeline_fetched_at: '2026-03-24T00:00:00.000Z', _pipeline_source: 'async', ...mockResponse };
      assert.equal(result._pipeline_source, 'async');
      assert.equal(result._pipeline_fetched_at, '2026-03-24T00:00:00.000Z');
      assert.ok(Array.isArray(result.tasks), 'tasks array preserved');
    });

    it('live_fallback path produces object with _pipeline_source "live_fallback"', () => {
      const result = { _pipeline_fetched_at: '2026-03-24T00:00:00.000Z', _pipeline_source: 'live_fallback', ...mockResponse };
      assert.equal(result._pipeline_source, 'live_fallback');
      assert.equal(result._pipeline_fetched_at, '2026-03-24T00:00:00.000Z');
      assert.ok(Array.isArray(result.tasks), 'tasks array preserved');
    });

    it('checkCache still validates files containing _pipeline_source correctly', () => {
      const dir = makeTmpDir();
      try {
        const data = {
          _pipeline_fetched_at: new Date().toISOString(),
          _pipeline_source: 'async',
          tasks: [{ data: { keyword: 'test' }, result: [{ datetime: '2026-03-24', items: [{ type: 'organic' }] }] }],
        };
        writeFileSync(join(dir, 'serp-raw.json'), JSON.stringify(data));
        const result = checkCache(join(dir, 'serp-raw.json'), 'test', 7);
        assert.equal(result.hit, true, '_pipeline_source field must not interfere with cache validation');
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('checkCache validates files with _pipeline_source "live_fallback" correctly', () => {
      const dir = makeTmpDir();
      try {
        const data = {
          _pipeline_fetched_at: new Date().toISOString(),
          _pipeline_source: 'live_fallback',
          tasks: [{ data: { keyword: 'search term' }, result: [{ datetime: '2026-03-24', items: [{ type: 'organic' }] }] }],
        };
        writeFileSync(join(dir, 'serp-raw.json'), JSON.stringify(data));
        const result = checkCache(join(dir, 'serp-raw.json'), 'search term', 7);
        assert.equal(result.hit, true, '_pipeline_source "live_fallback" must not interfere with cache validation');
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });
  });

  // --- deriveOutdir ---

  describe('deriveOutdir', () => {
    it('produces path matching YYYY-MM-DD_<slug> pattern', () => {
      const result = deriveOutdir('thailand urlaub', '/base');
      const dirName = result.split('/').pop();
      assert.ok(/^\d{4}-\d{2}-\d{2}_[a-z0-9]+(-[a-z0-9]+)*$/.test(dirName),
        `Expected YYYY-MM-DD_<slug> pattern, got: ${dirName}`);
    });

    it('slugifies umlauts correctly (ae, oe, ue, ss)', () => {
      const result = deriveOutdir('schönste strände für übernachtung mit straße', '/base');
      const dirName = result.split('/').pop();
      // Extract the slug part after the date
      const slug = dirName.replace(/^\d{4}-\d{2}-\d{2}_/, '');
      assert.ok(slug.includes('schoenste'), `Expected "schoenste" in slug, got: ${slug}`);
      assert.ok(slug.includes('straende'), `Expected "straende" in slug, got: ${slug}`);
      assert.ok(slug.includes('uebernachtung'), `Expected "uebernachtung" in slug, got: ${slug}`);
      assert.ok(slug.includes('strasse'), `Expected "strasse" in slug, got: ${slug}`);
    });

    it('is deterministic: same input produces identical output', () => {
      const run1 = deriveOutdir('thailand urlaub', '/output');
      const run2 = deriveOutdir('thailand urlaub', '/output');
      assert.equal(run1, run2, 'same input must produce identical output');
    });

    it('uses the provided baseDir as parent', () => {
      const result = deriveOutdir('test keyword', '/my/base/dir');
      assert.ok(result.startsWith('/my/base/dir/'),
        `Expected path to start with /my/base/dir/, got: ${result}`);
    });

    it('includes today date in the path', () => {
      const today = new Date();
      const yyyy = String(today.getFullYear());
      const mm = String(today.getMonth() + 1).padStart(2, '0');
      const dd = String(today.getDate()).padStart(2, '0');
      const expected = `${yyyy}-${mm}-${dd}`;
      const result = deriveOutdir('some keyword', '/base');
      assert.ok(result.includes(expected),
        `Expected date ${expected} in path, got: ${result}`);
    });
  });

});
