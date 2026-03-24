import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'analysis', 'extract-claims.mjs');
const fixtureDraft = join(__dirname, '..', 'fixtures', 'extract-claims', 'draft.md');

function run(opts = {}) {
  const args = [script];
  args.push('--draft', opts.draft || fixtureDraft);
  if (opts.output) args.push('--output', opts.output);
  return execFileSync('node', args, { encoding: 'utf-8' });
}

function runParsed(opts = {}) {
  return JSON.parse(run(opts));
}

function makeTmpDir() {
  const dir = join(tmpdir(), 'extract-claims-test-' + randomBytes(4).toString('hex'));
  mkdirSync(dir, { recursive: true });
  return dir;
}

describe('extract-claims', () => {

  // Test 1: usage error when --draft is missing
  it('exits with usage error when --draft is missing', () => {
    try {
      execFileSync('node', [script], { encoding: 'utf-8', stdio: 'pipe' });
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
    }
  });

  // Test 2: extracts height/distance claims
  it('extracts height/distance claims', () => {
    const result = runParsed();
    const hd = result.claims.filter(c => c.category === 'heights_distances');
    assert.ok(hd.length > 0, 'must have at least one heights_distances claim');
    const values = hd.map(c => c.value);
    assert.ok(values.some(v => v.includes('2.469 Metern')), 'must find 2.469 Metern');
    assert.ok(values.some(v => v.includes('8 km')), 'must find 8 km');
    assert.ok(values.some(v => v.includes('604 Meter')), 'must find 604 Meter');
  });

  // Test 3: extracts price claims
  it('extracts price claims', () => {
    const result = runParsed();
    const prices = result.claims.filter(c => c.category === 'prices_costs');
    assert.ok(prices.length > 0, 'must have at least one prices_costs claim');
    const values = prices.map(c => c.value);
    assert.ok(values.some(v => v.includes('790 NOK')), 'must find 790 NOK');
    assert.ok(values.some(v => v.includes('49 Euro')), 'must find 49 Euro');
    assert.ok(values.some(v => v.includes('150 EUR')), 'must find 150 EUR');
  });

  // Test 4: extracts date/year claims
  it('extracts date/year claims', () => {
    const result = runParsed();
    const dates = result.claims.filter(c => c.category === 'dates_years');
    assert.ok(dates.length > 0, 'must have at least one dates_years claim');
    const values = dates.map(c => c.value);
    assert.ok(values.some(v => v.includes('2015')), 'must find seit 2015');
    assert.ok(values.some(v => v.includes('1868')), 'must find im Jahr 1868');
    assert.ok(values.some(v => v.includes('1884')), 'must find im Jahr 1884');
  });

  // Test 5: extracts count claims
  it('extracts count claims', () => {
    const result = runParsed();
    const counts = result.claims.filter(c => c.category === 'counts');
    assert.ok(counts.length > 0, 'must have at least one counts claim');
    const values = counts.map(c => c.value);
    assert.ok(values.some(v => v.includes('550 Huetten')), 'must find ueber 550 Huetten');
    assert.ok(values.some(v => v.includes('28 Nationalparks')), 'must find 28 Nationalparks');
    assert.ok(values.some(v => v.includes('500 Routen')), 'must find rund 500 Routen');
  });

  // Test 6: extracts geographic relationship claims
  it('extracts geographic relationship claims', () => {
    const result = runParsed();
    const geo = result.claims.filter(c => c.category === 'geographic');
    assert.ok(geo.length > 0, 'must have at least one geographic claim');
    const values = geo.map(c => c.value);
    assert.ok(
      values.some(v => v.includes('zwischen') && v.includes('Lom') && v.includes('Gjendesheim')),
      'must find "zwischen Lom und Gjendesheim"'
    );
    assert.ok(
      values.some(v => v.includes('noerdlich') && v.includes('Polarkreises')),
      'must find "noerdlich des Polarkreises"'
    );
  });

  // Test 7: skips meta table content
  it('skips meta table content', () => {
    const result = runParsed();
    // The meta table contains "Reiseinteressierte" -- should not appear in claims
    const metaClaims = result.claims.filter(c =>
      c.value.includes('Reiseinteressierte') ||
      c.value.includes('wandern norwegen') ||
      c.sentence.includes('| Feld | Wert |')
    );
    assert.equal(metaClaims.length, 0, 'must not extract claims from meta table');
    // Also verify no claim comes from lines 1-6 (meta table range in fixture)
    const metaLineClaims = result.claims.filter(c => c.line <= 7);
    assert.equal(metaLineClaims.length, 0, 'no claims should come from meta table lines');
  });

  // Test 8: skips HTML comments
  it('skips HTML comments', () => {
    const result = runParsed();
    const commentClaims = result.claims.filter(c =>
      c.sentence.includes('TODO') || c.sentence.includes('VERIFY')
    );
    assert.equal(commentClaims.length, 0, 'must not extract claims from HTML comments');
  });

  // Test 9: produces deterministic output
  it('produces deterministic output (run twice, compare JSON)', () => {
    const run1 = runParsed();
    const run2 = runParsed();
    // extracted_at will differ, so compare claims only
    assert.deepStrictEqual(run1.claims, run2.claims, 'claims must be identical across runs');
    assert.equal(run1.meta.total_claims, run2.meta.total_claims, 'total_claims must match');
    assert.equal(run1.meta.draft, run2.meta.draft, 'draft path must match');
  });

  // Test 10: --output flag writes to file
  it('--output flag writes to file instead of stdout', () => {
    const dir = makeTmpDir();
    const outPath = join(dir, 'claims.json');
    try {
      const stdout = run({ output: outPath });
      // stdout should be empty when writing to file
      assert.equal(stdout.trim(), '', 'stdout must be empty when --output is used');
      const fileContent = readFileSync(outPath, 'utf-8');
      const parsed = JSON.parse(fileContent);
      assert.ok(parsed.meta, 'file must contain meta');
      assert.ok(Array.isArray(parsed.claims), 'file must contain claims array');
      assert.ok(parsed.claims.length > 0, 'claims must not be empty');
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  // Test 11: each claim has correct section from nearest heading
  it('each claim has correct section from nearest heading', () => {
    const result = runParsed();
    // Claims from Jotunheimen section
    const jotunClaims = result.claims.filter(c => c.value.includes('2.469 Metern'));
    assert.ok(jotunClaims.length > 0, 'must find Galdhopiggen claim');
    assert.equal(jotunClaims[0].section, 'Jotunheimen Nationalpark',
      'Galdhopiggen claim must be in Jotunheimen section');

    // Claims from Besseggen sub-section
    const besseggenClaims = result.claims.filter(c => c.value.includes('8 km'));
    assert.ok(besseggenClaims.length > 0, 'must find 8 km claim');
    assert.equal(besseggenClaims[0].section, 'Besseggen-Grat',
      '8 km claim must be in Besseggen-Grat section');

    // Claims from Hardangervidda section
    const hardangerClaims = result.claims.filter(c =>
      c.category === 'measurements' && c.value.includes('Quadratkilometer'));
    assert.ok(hardangerClaims.length > 0, 'must find Quadratkilometer claim');
    assert.equal(hardangerClaims[0].section, 'Hardangervidda',
      'Quadratkilometer claim must be in Hardangervidda section');

    // Claims from first section (Ueberblick)
    const overviewClaims = result.claims.filter(c =>
      c.value.includes('550 Huetten'));
    assert.ok(overviewClaims.length > 0, 'must find 550 Huetten claim');
    assert.equal(overviewClaims[0].section, 'Wandern in Norwegen: Ein Ueberblick',
      '550 Huetten claim must be in overview section');
  });

});
