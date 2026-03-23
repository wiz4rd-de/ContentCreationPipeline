import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { writeFileSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'analysis', 'summarize-briefing.mjs');
const fixture = join(
  __dirname, '..', 'fixtures', 'assemble-briefing-data',
  '2026-03-09_test-keyword', 'briefing-data.json'
);

function run(filePath) {
  return execFileSync('node', [script, '--file', filePath], {
    encoding: 'utf-8',
    stdio: 'pipe',
  });
}

function tmpFile(name) {
  return join(tmpdir(), (name || 'summarize-') + randomBytes(4).toString('hex') + '.json');
}

describe('summarize-briefing', () => {

  // 1. Exits non-zero when --file is missing
  it('exits non-zero with usage message when --file is missing', () => {
    try {
      execFileSync('node', [script], { encoding: 'utf-8', stdio: 'pipe' });
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
      assert.ok(err.stderr.includes('Usage:'), 'stderr must contain usage message');
    }
  });

  // 2. Exits non-zero when file does not exist
  it('exits non-zero when file does not exist', () => {
    try {
      execFileSync('node', [script, '--file', '/tmp/nonexistent-briefing.json'], {
        encoding: 'utf-8',
        stdio: 'pipe',
      });
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
      assert.ok(err.stderr.includes('File not found'), 'stderr must mention file not found');
    }
  });

  // 3. Prints summary containing seed keyword
  it('prints summary containing seed keyword from fixture', () => {
    const out = run(fixture);
    assert.ok(out.includes('test keyword'), 'must contain seed keyword "test keyword"');
    assert.ok(out.startsWith('Briefing Summary: test keyword'), 'must start with header');
  });

  // 4. Correct keyword count
  it('summary contains correct keyword count (10 total, 8 filtered)', () => {
    const out = run(fixture);
    assert.ok(out.includes('10 total, 8 after filtering'), 'must show 10 total, 8 filtered');
  });

  // 5. Correct cluster count
  it('summary contains correct cluster count (3)', () => {
    const out = run(fixture);
    assert.match(out, /Clusters:\s+3/);
  });

  // 6. Correct competitor count
  it('summary contains correct competitor count (3) and avg words (2100)', () => {
    const out = run(fixture);
    assert.ok(out.includes('3 (2100 avg words)'), 'must show 3 competitors with 2100 avg words');
  });

  // 7. Correct FAQ question count
  it('summary contains correct FAQ question count (2)', () => {
    const out = run(fixture);
    assert.match(out, /FAQ:\s+2 questions/);
  });

  // 8. Contains truthy SERP features
  it('summary contains SERP features that are true', () => {
    const out = run(fixture);
    assert.ok(out.includes('ai_overview'), 'must contain ai_overview');
    assert.ok(out.includes('people_also_ask'), 'must contain people_also_ask');
  });

  // 9. Does NOT contain falsy SERP features
  it('summary does NOT contain SERP features that are false', () => {
    const out = run(fixture);
    assert.ok(out.includes('SERP:'), 'must have SERP line');
    // Extract just the SERP line to avoid false positives from other content
    const serpLine = out.split('\n').find(l => l.startsWith('SERP:'));
    assert.ok(serpLine, 'SERP line must exist');
    assert.ok(!serpLine.includes('featured_snippet'), 'must not contain featured_snippet');
    assert.ok(!serpLine.includes('knowledge_graph'), 'must not contain knowledge_graph');
    assert.ok(!serpLine.includes('video'), 'must not contain video');
    assert.ok(!serpLine.includes('top_stories'), 'must not contain top_stories');
  });

  // 10. Contains AIO status
  it('summary contains AIO status (yes)', () => {
    const out = run(fixture);
    assert.match(out, /AIO:\s+yes/);
  });

  // 11. Contains common/rare modules
  it('summary contains common and rare modules', () => {
    const out = run(fixture);
    assert.ok(out.includes('common: list'), 'must show common modules');
    assert.ok(out.includes('rare: faq'), 'must show rare modules');
  });

  // 12. Handles minimal/empty briefing-data.json gracefully
  it('handles minimal/empty briefing-data.json gracefully (no crash)', () => {
    const path = tmpFile('empty-briefing-');
    try {
      writeFileSync(path, '{}');
      const out = run(path);
      assert.ok(out.includes('Briefing Summary: n/a'), 'must show n/a for missing seed keyword');
      assert.ok(out.includes('0 total, 0 after filtering'), 'must show 0 keywords');
      assert.match(out, /Clusters:\s+0/);
      assert.match(out, /Competitors:\s+0/);
      assert.match(out, /FAQ:\s+0 questions/);
      assert.match(out, /SERP:\s+none/);
      assert.match(out, /AIO:\s+no/);
      assert.ok(out.includes('common: n/a'), 'must show n/a for modules');
      assert.ok(out.includes('rare: n/a'), 'must show n/a for modules');
      assert.match(out, /Removals:\s+none/);
    } finally {
      rmSync(path, { force: true });
    }
  });

});
