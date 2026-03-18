import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { writeFileSync, readFileSync, mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'analysis', 'merge-qualitative.mjs');

function makeTmpDir() {
  const dir = join(tmpdir(), 'merge-qualitative-' + randomBytes(4).toString('hex'));
  mkdirSync(dir, { recursive: true });
  return dir;
}

const MINIMAL_BRIEFING = {
  meta: { seed_keyword: 'test', date: '2026-01-01', current_year: 2026, pipeline_version: '0.2.0' },
  qualitative: {
    entity_clusters: null,
    unique_angles: null,
    content_format_recommendation: null,
    geo_audit: null,
    aio_strategy: null,
    briefing: null,
  },
};

describe('merge-qualitative', () => {

  it('exits with usage error when --dir is missing', () => {
    try {
      execFileSync('node', [script], { encoding: 'utf-8', stdio: 'pipe' });
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
    }
  });

  it('errors gracefully when briefing-data.json is missing', () => {
    const dir = makeTmpDir();
    try {
      writeFileSync(join(dir, 'qualitative.json'), JSON.stringify({ entity_clusters: [] }));
      try {
        execFileSync('node', [script, '--dir', dir], { encoding: 'utf-8', stdio: 'pipe' });
        assert.fail('should have exited with non-zero code');
      } catch (err) {
        assert.ok(err.status > 0, 'exit code must be non-zero');
        assert.ok(err.stderr.includes('briefing-data.json not found'), 'stderr must mention missing file');
      }
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('errors gracefully when qualitative.json is missing', () => {
    const dir = makeTmpDir();
    try {
      writeFileSync(join(dir, 'briefing-data.json'), JSON.stringify(MINIMAL_BRIEFING));
      try {
        execFileSync('node', [script, '--dir', dir], { encoding: 'utf-8', stdio: 'pipe' });
        assert.fail('should have exited with non-zero code');
      } catch (err) {
        assert.ok(err.status > 0, 'exit code must be non-zero');
        assert.ok(err.stderr.includes('qualitative.json not found'), 'stderr must mention missing file');
      }
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('merges non-null qualitative fields into briefing-data.json (happy path)', () => {
    const dir = makeTmpDir();
    try {
      writeFileSync(join(dir, 'briefing-data.json'), JSON.stringify(MINIMAL_BRIEFING, null, 2) + '\n');
      const qualitative = {
        entity_clusters: [{ category: 'Orte', entities: ['Berlin'], synonyms: {} }],
        geo_audit: { must_haves: ['Eiffelturm'], hidden_gems: [], hallucination_risks: [], information_gaps: [] },
        content_format_recommendation: { format: 'Ratgeber', rationale: 'Most competitors use this format.' },
        unique_angles: [{ angle: 'Nachhaltigkeit', rationale: 'Underrepresented.' }],
        aio_strategy: { snippets: [{ topic: 'Kosten', pattern: 'X kostet Y', target_section: 'intro' }] },
      };
      writeFileSync(join(dir, 'qualitative.json'), JSON.stringify(qualitative, null, 2) + '\n');

      const stdout = execFileSync('node', [script, '--dir', dir], { encoding: 'utf-8' });
      assert.ok(stdout.includes('patched 5 field(s)'), 'stdout must confirm 5 fields patched');

      const result = JSON.parse(readFileSync(join(dir, 'briefing-data.json'), 'utf-8'));
      assert.deepEqual(result.qualitative.entity_clusters, qualitative.entity_clusters);
      assert.deepEqual(result.qualitative.geo_audit, qualitative.geo_audit);
      assert.deepEqual(result.qualitative.content_format_recommendation, qualitative.content_format_recommendation);
      assert.deepEqual(result.qualitative.unique_angles, qualitative.unique_angles);
      assert.deepEqual(result.qualitative.aio_strategy, qualitative.aio_strategy);
      assert.equal(result.qualitative.briefing, null, 'briefing field not in qualitative.json must remain null');
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('does not overwrite existing values with null fields from qualitative.json', () => {
    const dir = makeTmpDir();
    try {
      const existing = {
        ...MINIMAL_BRIEFING,
        qualitative: {
          ...MINIMAL_BRIEFING.qualitative,
          entity_clusters: [{ category: 'Existing', entities: ['Paris'], synonyms: {} }],
        },
      };
      writeFileSync(join(dir, 'briefing-data.json'), JSON.stringify(existing, null, 2) + '\n');

      // qualitative.json has entity_clusters: null — must not overwrite existing value
      const qualitative = {
        entity_clusters: null,
        geo_audit: { must_haves: ['Tour Eiffel'], hidden_gems: [], hallucination_risks: [], information_gaps: [] },
      };
      writeFileSync(join(dir, 'qualitative.json'), JSON.stringify(qualitative, null, 2) + '\n');

      execFileSync('node', [script, '--dir', dir], { encoding: 'utf-8' });

      const result = JSON.parse(readFileSync(join(dir, 'briefing-data.json'), 'utf-8'));
      assert.deepEqual(
        result.qualitative.entity_clusters,
        existing.qualitative.entity_clusters,
        'null field in qualitative.json must not overwrite existing value'
      );
      assert.deepEqual(result.qualitative.geo_audit, qualitative.geo_audit, 'non-null field must be merged');
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('produces byte-identical output for identical inputs (determinism)', () => {
    const dir = makeTmpDir();
    try {
      writeFileSync(join(dir, 'briefing-data.json'), JSON.stringify(MINIMAL_BRIEFING, null, 2) + '\n');
      const qualitative = {
        entity_clusters: [{ category: 'Test', entities: ['X'], synonyms: {} }],
        geo_audit: null,
      };
      writeFileSync(join(dir, 'qualitative.json'), JSON.stringify(qualitative, null, 2) + '\n');

      execFileSync('node', [script, '--dir', dir], { encoding: 'utf-8' });
      const first = readFileSync(join(dir, 'briefing-data.json'), 'utf-8');

      // Reset briefing-data.json to the original and run again
      writeFileSync(join(dir, 'briefing-data.json'), JSON.stringify(MINIMAL_BRIEFING, null, 2) + '\n');
      execFileSync('node', [script, '--dir', dir], { encoding: 'utf-8' });
      const second = readFileSync(join(dir, 'briefing-data.json'), 'utf-8');

      assert.equal(first, second, 'same inputs must produce byte-identical output');
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('preserves all non-qualitative fields in briefing-data.json unchanged', () => {
    const dir = makeTmpDir();
    try {
      const briefing = {
        ...MINIMAL_BRIEFING,
        stats: { total_keywords: 42, filtered_keywords: 30, total_clusters: 5, competitor_count: 8 },
        keyword_data: { clusters: [], total_keywords: 42, filtered_count: 30, removal_summary: null },
      };
      writeFileSync(join(dir, 'briefing-data.json'), JSON.stringify(briefing, null, 2) + '\n');
      writeFileSync(join(dir, 'qualitative.json'), JSON.stringify({ entity_clusters: [] }));

      execFileSync('node', [script, '--dir', dir], { encoding: 'utf-8' });

      const result = JSON.parse(readFileSync(join(dir, 'briefing-data.json'), 'utf-8'));
      assert.deepEqual(result.stats, briefing.stats, 'stats must be unchanged');
      assert.deepEqual(result.keyword_data, briefing.keyword_data, 'keyword_data must be unchanged');
      assert.deepEqual(result.meta, briefing.meta, 'meta must be unchanged');
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

});
