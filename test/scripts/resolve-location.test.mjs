import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'utils', 'resolve-location.mjs');

function run(market) {
  return execFileSync('node', [script, market], { encoding: 'utf-8' }).trim();
}

describe('resolve-location', () => {
  it('resolves de → 2276', () => {
    assert.equal(run('de'), '2276');
  });

  it('resolves us → 2840', () => {
    assert.equal(run('us'), '2840');
  });

  it('resolves gb → 2826', () => {
    assert.equal(run('gb'), '2826');
  });

  it('handles uppercase input (DE → 2276)', () => {
    assert.equal(run('DE'), '2276');
  });

  it('handles mixed case input (De → 2276)', () => {
    assert.equal(run('De'), '2276');
  });

  it('exits with error for unknown market', () => {
    assert.throws(
      () => execFileSync('node', [script, 'zz'], { encoding: 'utf-8', stdio: 'pipe' }),
      (err) => {
        assert.equal(err.status, 1);
        assert.ok(err.stderr.includes('Unknown market'));
        return true;
      },
    );
  });

  it('exits with error when no argument is provided', () => {
    assert.throws(
      () => execFileSync('node', [script], { encoding: 'utf-8', stdio: 'pipe' }),
      (err) => {
        assert.equal(err.status, 1);
        assert.ok(err.stderr.includes('Usage'));
        return true;
      },
    );
  });

  it('produces deterministic output for identical input', () => {
    const run1 = run('de');
    const run2 = run('de');
    assert.equal(run1, run2, 'same input must produce identical output');
  });
});
