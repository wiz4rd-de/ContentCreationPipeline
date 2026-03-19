import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

import {
  parseArgs,
  parseDateFromDirName,
  calculateAgeDays,
  formatAge,
  getMatchingDirs,
  filterOldDirs,
  cleanup,
} from '../../scripts/clean-output.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCRIPT = join(__dirname, '../../scripts/clean-output.mjs');

describe('clean-output: parseArgs', () => {
  it('parses --older-than flag', () => {
    const args = parseArgs(['--older-than', '14']);
    assert.equal(args.olderThan, '14');
  });

  it('parses --dry-run flag', () => {
    const args = parseArgs(['--dry-run']);
    assert.equal(args.dryRun, true);
  });

  it('parses --output-dir flag', () => {
    const args = parseArgs(['--output-dir', '/tmp/output']);
    assert.equal(args.outputDir, '/tmp/output');
  });

  it('parses multiple flags together', () => {
    const args = parseArgs(['--older-than', '7', '--dry-run', '--output-dir', '/tmp']);
    assert.equal(args.olderThan, '7');
    assert.equal(args.dryRun, true);
    assert.equal(args.outputDir, '/tmp');
  });

  it('ignores unknown flags', () => {
    const args = parseArgs(['--unknown', 'value', '--older-than', '30']);
    assert.equal(args.olderThan, '30');
    assert.equal(args.unknown, undefined);
  });
});

describe('clean-output: parseDateFromDirName', () => {
  it('parses valid YYYY-MM-DD_slug pattern', () => {
    const date = parseDateFromDirName('2026-03-19_test-keyword');
    assert.ok(date instanceof Date);
    assert.equal(date.getFullYear(), 2026);
    assert.equal(date.getMonth(), 2); // March = month 2 (0-indexed)
    assert.equal(date.getDate(), 19);
  });

  it('returns null for non-matching directory names', () => {
    assert.equal(parseDateFromDirName('2026-03_missing-day'), null);
    assert.equal(parseDateFromDirName('03-19-2026_reversed'), null);
    assert.equal(parseDateFromDirName('not-a-date'), null);
  });

  it('returns null for invalid dates like 9999-99-99', () => {
    const date = parseDateFromDirName('9999-99-99_invalid');
    assert.equal(date, null);
  });

  it('returns null for invalid February 30th', () => {
    const date = parseDateFromDirName('2026-02-30_invalid');
    assert.equal(date, null);
  });

  it('parses valid leap year date', () => {
    // 2024 is a leap year, 02-29 is valid
    const date = parseDateFromDirName('2024-02-29_leap');
    assert.ok(date instanceof Date);
    assert.equal(date.getFullYear(), 2024);
    assert.equal(date.getMonth(), 1);
    assert.equal(date.getDate(), 29);
  });

  it('returns null for invalid leap year date (non-leap year)', () => {
    // 2023 is not a leap year, 02-29 is invalid
    const date = parseDateFromDirName('2023-02-29_invalid');
    assert.equal(date, null);
  });
});

describe('clean-output: calculateAgeDays', () => {
  it('returns 0 for today', () => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const age = calculateAgeDays(today);
    assert.ok(age < 1, 'today should be less than 1 day old');
  });

  it('returns approximately 1 for a date 24 hours ago', () => {
    const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const age = calculateAgeDays(yesterday);
    assert.ok(age >= 0.99 && age <= 1.01, 'yesterday should be approximately 1 day old');
  });

  it('returns approximately N for a date N days ago', () => {
    const tenDaysAgo = new Date(Date.now() - 10 * 24 * 60 * 60 * 1000);
    const age = calculateAgeDays(tenDaysAgo);
    assert.ok(age >= 9.99 && age <= 10.01, '10 days ago should be approximately 10 days old');
  });
});

describe('clean-output: formatAge', () => {
  it('formats 1 day as singular', () => {
    assert.equal(formatAge(1.2), '1 day');
  });

  it('formats 2 days as plural', () => {
    assert.equal(formatAge(2.5), '2 days');
  });

  it('formats fractional days by flooring', () => {
    assert.equal(formatAge(5.9), '5 days');
  });
});

describe('clean-output: getMatchingDirs', () => {
  it('returns empty array for non-existent directory', () => {
    const dirs = getMatchingDirs('/nonexistent/path');
    assert.deepEqual(dirs, []);
  });

  it('finds directories matching YYYY-MM-DD_* pattern', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      mkdirSync(join(tmpDir, '2026-03-15_test1'));
      mkdirSync(join(tmpDir, '2026-03-16_test2'));
      mkdirSync(join(tmpDir, 'not-matching'));
      writeFileSync(join(tmpDir, 'plain-file.txt'), 'test');

      const dirs = getMatchingDirs(tmpDir);
      assert.equal(dirs.length, 2);
      assert.ok(dirs.some(d => d.name === '2026-03-15_test1'));
      assert.ok(dirs.some(d => d.name === '2026-03-16_test2'));
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('includes age property in returned objects', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      mkdirSync(join(tmpDir, '2026-03-15_test'));
      const dirs = getMatchingDirs(tmpDir);
      assert.equal(dirs.length, 1);
      assert.ok(typeof dirs[0].age === 'number');
      assert.ok(dirs[0].age > 0);
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });
});

describe('clean-output: filterOldDirs', () => {
  it('filters directories older than threshold', () => {
    const tenDaysAgo = new Date(Date.now() - 10 * 24 * 60 * 60 * 1000);
    const twentyDaysAgo = new Date(Date.now() - 20 * 24 * 60 * 60 * 1000);

    const dirs = [
      { name: 'dir1', date: tenDaysAgo, age: 10 },
      { name: 'dir2', date: twentyDaysAgo, age: 20 },
    ];

    const filtered = filterOldDirs(dirs, 15);
    assert.equal(filtered.length, 1);
    assert.equal(filtered[0].name, 'dir2');
  });

  it('returns empty array if no directories exceed threshold', () => {
    const fiveDaysAgo = new Date(Date.now() - 5 * 24 * 60 * 60 * 1000);
    const dirs = [{ name: 'dir1', date: fiveDaysAgo, age: 5 }];

    const filtered = filterOldDirs(dirs, 10);
    assert.equal(filtered.length, 0);
  });
});

describe('clean-output: cleanup', () => {
  it('removes old directories in real mode', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      const oldDirName = '2000-01-01_very-old';
      const newDirName = '2099-12-31_far-future';
      mkdirSync(join(tmpDir, oldDirName));
      mkdirSync(join(tmpDir, newDirName));

      const result = cleanup(tmpDir, 30, false);
      assert.equal(result.removed, 1, 'should remove 1 old directory');
      assert.equal(result.remaining, 1, 'should have 1 remaining directory');

      // Verify old dir is gone
      const dirs = getMatchingDirs(tmpDir);
      assert.ok(!dirs.some(d => d.name === oldDirName));
      assert.ok(dirs.some(d => d.name === newDirName));
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('does not remove directories in dry-run mode', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      const oldDirName = '2000-01-01_very-old';
      mkdirSync(join(tmpDir, oldDirName));

      const result = cleanup(tmpDir, 30, true);
      assert.equal(result.removed, 1);

      // Verify old dir still exists
      const dirs = getMatchingDirs(tmpDir);
      assert.ok(dirs.some(d => d.name === oldDirName));
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('does not remove non-matching directories', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      mkdirSync(join(tmpDir, 'non-matching-dir'));
      writeFileSync(join(tmpDir, 'plain-file.txt'), 'test');

      cleanup(tmpDir, 30, false);

      // Verify non-matching entries still exist
      assert.ok(getMatchingDirs(tmpDir).length === 0);
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('returns correct counts', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      mkdirSync(join(tmpDir, '2000-01-01_old1'));
      mkdirSync(join(tmpDir, '2000-01-02_old2'));
      mkdirSync(join(tmpDir, '2099-12-31_new'));

      const result = cleanup(tmpDir, 30, false);
      assert.equal(result.removed, 2);
      assert.equal(result.remaining, 1);
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });
});

// ---------------------------------------------------------------------------
// CLI-level integration tests
// ---------------------------------------------------------------------------

describe('clean-output: CLI', () => {
  function runCli(args, opts = {}) {
    return execFileSync('node', [SCRIPT, ...args], { encoding: 'utf-8', stdio: 'pipe', ...opts });
  }

  it('exits with error on invalid --older-than value', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      try {
        runCli(['--older-than', 'not-a-number', '--output-dir', tmpDir]);
        assert.fail('should have exited with non-zero code');
      } catch (err) {
        assert.ok(err.status > 0, 'exit code must be non-zero');
      }
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('defaults to 30-day retention', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      mkdirSync(join(tmpDir, '2000-01-01_very-old'));
      const output = runCli(['--dry-run', '--output-dir', tmpDir]);
      assert.ok(output.includes('Would remove'));
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('respects --older-than flag', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      mkdirSync(join(tmpDir, '2000-01-01_very-old'));
      const output = runCli(['--older-than', '50', '--dry-run', '--output-dir', tmpDir]);
      assert.ok(output.includes('Would remove'));
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('--dry-run outputs correct summary', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      mkdirSync(join(tmpDir, '2000-01-01_old'));
      mkdirSync(join(tmpDir, '2099-12-31_new'));
      const output = runCli(['--older-than', '30', '--dry-run', '--output-dir', tmpDir]);
      assert.ok(output.includes('Would remove 1'));
      assert.ok(output.includes('1 remaining'));
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('removes directories in real mode', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      const oldDir = join(tmpDir, '2000-01-01_old');
      mkdirSync(oldDir);
      mkdirSync(join(tmpDir, '2099-12-31_new'));

      const output = runCli(['--older-than', '30', '--output-dir', tmpDir]);
      assert.ok(output.includes('Removed 1'));

      // Verify old dir is gone
      const dirs = getMatchingDirs(tmpDir);
      assert.equal(dirs.length, 1);
      assert.ok(dirs[0].name.includes('2099'));
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('outputs summary with singular/plural correctly', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      // Create 1 old directory
      mkdirSync(join(tmpDir, '2000-01-01_old'));

      const output = runCli(['--older-than', '30', '--dry-run', '--output-dir', tmpDir]);
      assert.ok(output.includes('1 directory'));
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('outputs summary with plural when multiple directories removed', () => {
    const tmpDir = join(tmpdir(), 'clean-test-' + randomBytes(4).toString('hex'));
    mkdirSync(tmpDir, { recursive: true });
    try {
      // Create 2 old directories
      mkdirSync(join(tmpDir, '2000-01-01_old1'));
      mkdirSync(join(tmpDir, '2000-01-02_old2'));

      const output = runCli(['--older-than', '30', '--dry-run', '--output-dir', tmpDir]);
      assert.ok(output.includes('2 directories'));
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });
});
