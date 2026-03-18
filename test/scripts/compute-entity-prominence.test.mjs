import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'analysis', 'compute-entity-prominence.mjs');
const fixtures = join(__dirname, '..', 'fixtures', 'compute-entity-prominence');
const entitiesFixture = join(fixtures, 'entities.json');
const pagesFixture = join(fixtures, 'pages');

function run(opts = {}) {
  const args = [script];
  args.push('--entities', opts.entities || entitiesFixture);
  args.push('--pages-dir', opts.pagesDir || pagesFixture);
  return execFileSync('node', args, { encoding: 'utf-8' });
}

function runParsed(opts = {}) {
  return JSON.parse(run(opts));
}

// Create a temporary directory with custom entities and pages for isolated tests.
function makeTmpDir() {
  const dir = join(tmpdir(), 'cep-test-' + randomBytes(4).toString('hex'));
  const pagesDir = join(dir, 'pages');
  mkdirSync(pagesDir, { recursive: true });
  return { dir, pagesDir };
}

describe('compute-entity-prominence', () => {
  it('exits with usage error when args are missing', () => {
    try {
      execFileSync('node', [script], { encoding: 'utf-8', stdio: 'pipe' });
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
    }
  });

  it('produces valid JSON output with entity_clusters', () => {
    const result = runParsed();
    assert.ok(Array.isArray(result.entity_clusters), 'entity_clusters must be an array');
    assert.equal(result.entity_clusters.length, 2, 'fixture has 2 categories');
  });

  it('preserves category_name for each cluster', () => {
    const result = runParsed();
    const names = result.entity_clusters.map(c => c.category_name);
    assert.deepEqual(names, ['Aktivitaeten', 'Orte']);
  });

  it('sets prominence_source to "code" on every entity', () => {
    const result = runParsed();
    const allEntities = result.entity_clusters.flatMap(c => c.entities);
    for (const e of allEntities) {
      assert.equal(e.prominence_source, 'code', `${e.entity} must have prominence_source "code"`);
    }
  });

  it('preserves original LLM prominence as prominence_gemini', () => {
    const result = runParsed();
    const schnorcheln = result.entity_clusters[0].entities[0];
    assert.equal(schnorcheln.prominence_gemini, '8/10');
    const tauchen = result.entity_clusters[0].entities[1];
    assert.equal(tauchen.prominence_gemini, '5/10');
  });

  it('computes prominence as "count/total" from page text matching', () => {
    const result = runParsed();
    const allEntities = result.entity_clusters.flatMap(c => c.entities);
    for (const e of allEntities) {
      const match = e.prominence.match(/^(\d+)\/(\d+)$/);
      assert.ok(match, `${e.entity} prominence "${e.prominence}" must match N/M format`);
      assert.equal(match[2], '3', 'total must equal number of page files (3)');
    }
  });

  it('counts Schnorcheln in alpha and beta (2/3)', () => {
    const result = runParsed();
    const schnorcheln = result.entity_clusters[0].entities[0];
    assert.equal(schnorcheln.prominence, '2/3');
  });

  it('counts Tauchen only in alpha (1/3)', () => {
    const result = runParsed();
    const tauchen = result.entity_clusters[0].entities[1];
    assert.equal(tauchen.prominence, '1/3');
  });

  it('counts Riff in alpha and beta (2/3)', () => {
    const result = runParsed();
    const riff = result.entity_clusters[1].entities[0];
    assert.equal(riff.prominence, '2/3');
  });

  it('uses word-boundary matching for short synonym "spa" (<=4 chars)', () => {
    const result = runParsed();
    const spa = result.entity_clusters[1].entities[1];
    // "spa" appears in gamma as a standalone word (Spa-Bereich, Spa.)
    assert.equal(spa.prominence, '1/3');
  });

  it('short synonym word-boundary prevents false positives', () => {
    const tmp = makeTmpDir();
    try {
      const entities = {
        entity_clusters: [{
          category_name: 'Test',
          entities: [{
            entity: 'Map',
            prominence: '1/1',
            synonyms: ['map']
          }]
        }]
      };
      writeFileSync(join(tmp.dir, 'entities.json'), JSON.stringify(entities));
      // "mapper" contains "map" but word-boundary should prevent matching
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({
        main_content_text: 'The mapper tool is great for data transformation.'
      }));
      const result = runParsed({ entities: join(tmp.dir, 'entities.json'), pagesDir: tmp.pagesDir });
      assert.equal(result.entity_clusters[0].entities[0].prominence, '0/1',
        'short synonym "map" must not match "mapper" due to word-boundary');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('long synonym uses includes() (no word-boundary)', () => {
    const tmp = makeTmpDir();
    try {
      const entities = {
        entity_clusters: [{
          category_name: 'Test',
          entities: [{
            entity: 'Diving',
            prominence: '1/1',
            synonyms: ['diving']
          }]
        }]
      };
      writeFileSync(join(tmp.dir, 'entities.json'), JSON.stringify(entities));
      // "divingspot" contains "diving" — long synonym uses includes(), should match
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({
        main_content_text: 'The best divingspot in the area.'
      }));
      const result = runParsed({ entities: join(tmp.dir, 'entities.json'), pagesDir: tmp.pagesDir });
      assert.equal(result.entity_clusters[0].entities[0].prominence, '1/1',
        'long synonym "diving" (5 chars) should match via includes()');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('generates _debug.corrections for significant deviations (delta >= 2)', () => {
    const result = runParsed();
    assert.ok(result._debug, '_debug must exist when corrections are needed');
    assert.ok(Array.isArray(result._debug.corrections), '_debug.corrections must be an array');
    assert.ok(result._debug.corrections.length > 0, 'fixture data has deviations >= 2');

    // All fixture entities have large deltas (gemini counts were 8,5,9,3 vs code counts 2,1,2,1)
    const entityNames = result._debug.corrections.map(c => c.entity).sort();
    assert.deepEqual(entityNames, ['Riff', 'Schnorcheln', 'Spa', 'Tauchen'],
      'all 4 entities should have corrections (all have delta >= 2)');
  });

  it('corrections include entity, category, gemini, code, and delta fields', () => {
    const result = runParsed();
    for (const c of result._debug.corrections) {
      assert.ok('entity' in c, 'correction must have entity');
      assert.ok('category' in c, 'correction must have category');
      assert.ok('gemini' in c, 'correction must have gemini');
      assert.ok('code' in c, 'correction must have code');
      assert.ok('delta' in c, 'correction must have delta');
      assert.ok(c.delta >= 2, `delta must be >= 2, got ${c.delta}`);
    }
  });

  it('omits _debug when no corrections exist', () => {
    const tmp = makeTmpDir();
    try {
      const entities = {
        entity_clusters: [{
          category_name: 'Exact',
          entities: [{
            entity: 'Hello',
            prominence: '1/1',
            synonyms: ['hello']
          }]
        }]
      };
      writeFileSync(join(tmp.dir, 'entities.json'), JSON.stringify(entities));
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({
        main_content_text: 'Hello world.'
      }));
      const result = runParsed({ entities: join(tmp.dir, 'entities.json'), pagesDir: tmp.pagesDir });
      assert.equal(result.entity_clusters[0].entities[0].prominence, '1/1');
      assert.equal(result._debug, undefined, '_debug must be absent when no corrections');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('produces byte-identical output on repeated runs (determinism)', () => {
    const run1 = run();
    const run2 = run();
    assert.equal(run1, run2, 'same inputs must produce byte-identical output');
  });

  it('preserves synonyms array in output', () => {
    const result = runParsed();
    const schnorcheln = result.entity_clusters[0].entities[0];
    assert.deepEqual(schnorcheln.synonyms, ['schnorcheln', 'snorkeling', 'schnorchelausflug']);
  });

  it('handles pages with missing main_content_text gracefully', () => {
    const tmp = makeTmpDir();
    try {
      const entities = {
        entity_clusters: [{
          category_name: 'Test',
          entities: [{
            entity: 'Something',
            prominence: '0/1',
            synonyms: ['something']
          }]
        }]
      };
      writeFileSync(join(tmp.dir, 'entities.json'), JSON.stringify(entities));
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({ url: 'https://example.com' }));
      const result = runParsed({ entities: join(tmp.dir, 'entities.json'), pagesDir: tmp.pagesDir });
      assert.equal(result.entity_clusters[0].entities[0].prominence, '0/1');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('handles empty pages directory (0 pages)', () => {
    const tmp = makeTmpDir();
    try {
      const entities = {
        entity_clusters: [{
          category_name: 'Test',
          entities: [{
            entity: 'X',
            prominence: '5/10',
            synonyms: ['something']
          }]
        }]
      };
      writeFileSync(join(tmp.dir, 'entities.json'), JSON.stringify(entities));
      const result = runParsed({ entities: join(tmp.dir, 'entities.json'), pagesDir: tmp.pagesDir });
      assert.equal(result.entity_clusters[0].entities[0].prominence, '0/0');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('logs page count to stderr before processing', () => {
    const proc = spawnSync('node', [script, '--entities', entitiesFixture, '--pages-dir', pagesFixture], { encoding: 'utf-8' });
    assert.ok(proc.stderr.includes('Computing entity prominence across'), 'stderr must include progress message');
    assert.ok(proc.stderr.includes('pages'), 'stderr must mention pages');
  });

  it('case-insensitive matching works for mixed case text', () => {
    const tmp = makeTmpDir();
    try {
      const entities = {
        entity_clusters: [{
          category_name: 'Test',
          entities: [{
            entity: 'Yoga',
            prominence: '0/1',
            synonyms: ['yoga']
          }]
        }]
      };
      writeFileSync(join(tmp.dir, 'entities.json'), JSON.stringify(entities));
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({
        main_content_text: 'YOGA classes are available every morning.'
      }));
      const result = runParsed({ entities: join(tmp.dir, 'entities.json'), pagesDir: tmp.pagesDir });
      // "yoga" is 4 chars, word-boundary matching. "YOGA" as standalone word should match.
      assert.equal(result.entity_clusters[0].entities[0].prominence, '1/1');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });
});
