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
  });

});
