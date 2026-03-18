import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = join(__dirname, '..', '..', 'src', 'analysis', 'analyze-page-structure.mjs');
const fixturePages = join(__dirname, '..', 'fixtures', 'analyze-page-structure', 'pages');

function run(opts = {}) {
  const args = [script];
  args.push('--pages-dir', opts.pagesDir || fixturePages);
  return execFileSync('node', args, { encoding: 'utf-8' });
}

function runParsed(opts = {}) {
  return JSON.parse(run(opts));
}

function makeTmpDir() {
  const dir = join(tmpdir(), 'aps-test-' + randomBytes(4).toString('hex'));
  const pagesDir = join(dir, 'pages');
  mkdirSync(pagesDir, { recursive: true });
  return { dir, pagesDir };
}

describe('analyze-page-structure', () => {

  it('exits with usage error when --pages-dir is missing', () => {
    try {
      execFileSync('node', [script], { encoding: 'utf-8', stdio: 'pipe' });
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      assert.ok(err.status > 0, 'exit code must be non-zero');
    }
  });

  it('produces valid JSON with competitors and cross_competitor', () => {
    const result = runParsed();
    assert.ok(Array.isArray(result.competitors), 'competitors must be an array');
    assert.ok(result.cross_competitor, 'cross_competitor must exist');
    assert.equal(result.competitors.length, 3, 'fixture has 3 page files');
  });

  it('extracts URL and domain for each competitor', () => {
    const result = runParsed();
    for (const comp of result.competitors) {
      assert.ok(typeof comp.url === 'string', 'url must be a string');
      assert.ok(typeof comp.domain === 'string', 'domain must be a string');
      assert.ok(comp.domain.length > 0, 'domain must be non-empty');
    }
  });

  it('computes total_word_count and section_count per competitor', () => {
    const result = runParsed();
    for (const comp of result.competitors) {
      assert.ok(typeof comp.total_word_count === 'number', 'total_word_count must be a number');
      assert.ok(comp.total_word_count > 0, 'total_word_count must be positive');
      assert.ok(typeof comp.section_count === 'number', 'section_count must be a number');
      assert.ok(comp.section_count > 0, 'section_count must be positive');
    }
  });

  it('detects FAQ module from heading text patterns', () => {
    const result = runParsed();
    // page-alpha has "Haeufig gestellte Fragen" heading + faq_sections: 2
    const alpha = result.competitors.find(c => c.domain === 'alpha.example.com');
    assert.ok(alpha.detected_modules.includes('faq'), 'alpha must detect faq');
    // page-beta has "FAQ zu Mallorca" heading + faq_sections: 1
    const beta = result.competitors.find(c => c.domain === 'beta.example.com');
    assert.ok(beta.detected_modules.includes('faq'), 'beta must detect faq');
  });

  it('detects FAQ module from html_signals even without heading match', () => {
    const tmp = makeTmpDir();
    try {
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({
        url: 'https://example.com/test',
        main_content_text: 'Some content without FAQ heading. Answer to a question here. ' + 'content '.repeat(190),
        headings: [{ level: 2, text: 'Introduction' }],
        html_signals: { faq_sections: 3, tables: 0, ordered_lists: 0, unordered_lists: 0, video_embeds: 0, forms: 0, images_in_content: 0 },
      }));
      const result = runParsed({ pagesDir: tmp.pagesDir });
      assert.ok(result.competitors[0].detected_modules.includes('faq'), 'faq must be detected via html_signals');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('detects table module from html_signals', () => {
    const result = runParsed();
    const alpha = result.competitors.find(c => c.domain === 'alpha.example.com');
    assert.ok(alpha.detected_modules.includes('table'), 'alpha has tables: 1');
  });

  it('detects list module from ordered_lists or unordered_lists', () => {
    const result = runParsed();
    const alpha = result.competitors.find(c => c.domain === 'alpha.example.com');
    assert.ok(alpha.detected_modules.includes('list'), 'alpha has unordered_lists: 2');
    const beta = result.competitors.find(c => c.domain === 'beta.example.com');
    assert.ok(beta.detected_modules.includes('list'), 'beta has ordered_lists: 1');
  });

  it('detects video module from video_embeds', () => {
    const result = runParsed();
    const beta = result.competitors.find(c => c.domain === 'beta.example.com');
    assert.ok(beta.detected_modules.includes('video'), 'beta has video_embeds: 1');
  });

  it('detects image_gallery when images_in_content > 3', () => {
    const result = runParsed();
    const alpha = result.competitors.find(c => c.domain === 'alpha.example.com');
    assert.ok(alpha.detected_modules.includes('image_gallery'), 'alpha has images_in_content: 5');
    const gamma = result.competitors.find(c => c.domain === 'gamma.example.com');
    assert.ok(gamma.detected_modules.indexOf('image_gallery') === -1, 'gamma has images_in_content: 1, no gallery');
  });

  it('detects form module from html_signals', () => {
    const result = runParsed();
    const gamma = result.competitors.find(c => c.domain === 'gamma.example.com');
    assert.ok(gamma.detected_modules.includes('form'), 'gamma has forms: 1');
  });

  it('detected_modules are sorted alphabetically', () => {
    const result = runParsed();
    for (const comp of result.competitors) {
      const sorted = [...comp.detected_modules].sort();
      assert.deepEqual(comp.detected_modules, sorted, 'modules must be sorted');
    }
  });

  it('splits text into sections with heading, level, word_count, sentence_count', () => {
    const result = runParsed();
    const alpha = result.competitors.find(c => c.domain === 'alpha.example.com');
    assert.ok(alpha.sections.length > 1, 'alpha must have multiple sections');
    for (const sec of alpha.sections) {
      assert.ok('heading' in sec, 'section must have heading');
      assert.ok('level' in sec, 'section must have level');
      assert.ok('word_count' in sec, 'section must have word_count');
      assert.ok('sentence_count' in sec, 'section must have sentence_count');
      assert.ok('has_numbers' in sec, 'section must have has_numbers');
      assert.ok('has_lists' in sec, 'section must have has_lists');
      assert.ok('depth_score' in sec, 'section must have depth_score');
    }
  });

  it('computes depth_score as shallow/basic/detailed based on sentence_count', () => {
    const tmp = makeTmpDir();
    try {
      // Create a page with known sections of varying depth
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({
        url: 'https://example.com/depth',
        // Pad intro with 175 filler words so total >= 200; section content is preserved for depth scoring
        main_content_text: ('filler '.repeat(175)) + 'Intro Section One Short text. Section Two This is a medium section. It has three sentences. And a third one here. Section Three First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence. Sixth sentence. Seventh sentence.',
        headings: [
          { level: 2, text: 'Section One' },
          { level: 2, text: 'Section Two' },
          { level: 2, text: 'Section Three' },
        ],
        html_signals: { faq_sections: 0, tables: 0, ordered_lists: 0, unordered_lists: 0, video_embeds: 0, forms: 0, images_in_content: 0 },
      }));
      const result = runParsed({ pagesDir: tmp.pagesDir });
      const sections = result.competitors[0].sections;
      // Section One has 1 sentence -> shallow
      const s1 = sections.find(s => s.heading === 'Section One');
      assert.equal(s1.depth_score, 'shallow', 'section with <= 2 sentences is shallow');
      // Section Two has 3 sentences -> basic
      const s2 = sections.find(s => s.heading === 'Section Two');
      assert.equal(s2.depth_score, 'basic', 'section with 3-6 sentences is basic');
      // Section Three has 7 sentences -> detailed
      const s3 = sections.find(s => s.heading === 'Section Three');
      assert.equal(s3.depth_score, 'detailed', 'section with 7+ sentences is detailed');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('includes intro section (before first heading) with level 0', () => {
    const result = runParsed();
    const alpha = result.competitors.find(c => c.domain === 'alpha.example.com');
    const intro = alpha.sections[0];
    assert.equal(intro.level, 0, 'intro section level must be 0');
    assert.equal(intro.heading, '', 'intro section heading must be empty');
    assert.ok(intro.word_count > 0, 'intro section must have words');
  });

  it('computes cross_competitor common_modules (>= 70%)', () => {
    const result = runParsed();
    const cc = result.cross_competitor;
    // faq: alpha + beta = 2/3 = 67% -> NOT common (< 70%)
    // table: alpha + beta = 2/3 = 67% -> NOT common
    // list: all 3 = 100% -> common
    assert.ok(cc.common_modules.includes('list'), 'list present in all 3 competitors must be common');
  });

  it('computes cross_competitor rare_modules (<= 20%)', () => {
    const result = runParsed();
    const cc = result.cross_competitor;
    // video: only beta = 1/3 = 33% -> NOT rare (> 20%)
    // image_gallery: only alpha = 1/3 = 33% -> NOT rare
    // form: only gamma = 1/3 = 33% -> NOT rare
    // With 3 competitors, <= 20% means 0 occurrences (0.6 threshold), so nothing is rare
    assert.ok(Array.isArray(cc.rare_modules), 'rare_modules must be an array');
  });

  it('computes module_frequency with sorted keys', () => {
    const result = runParsed();
    const mf = result.cross_competitor.module_frequency;
    assert.ok(typeof mf === 'object', 'module_frequency must be an object');
    const keys = Object.keys(mf);
    const sorted = [...keys].sort();
    assert.deepEqual(keys, sorted, 'module_frequency keys must be sorted');
    // faq appears in alpha + beta
    assert.equal(mf.faq, 2, 'faq in 2 competitors');
    // list appears in all 3
    assert.equal(mf.list, 3, 'list in 3 competitors');
  });

  it('computes avg_word_count and avg_sections', () => {
    const result = runParsed();
    const cc = result.cross_competitor;
    assert.ok(typeof cc.avg_word_count === 'number', 'avg_word_count must be a number');
    assert.ok(cc.avg_word_count > 0, 'avg_word_count must be positive');
    assert.ok(typeof cc.avg_sections === 'number', 'avg_sections must be a number');
    assert.ok(cc.avg_sections > 0, 'avg_sections must be positive');
  });

  it('handles empty pages directory', () => {
    const tmp = makeTmpDir();
    try {
      const result = runParsed({ pagesDir: tmp.pagesDir });
      assert.deepEqual(result.competitors, []);
      assert.deepEqual(result.cross_competitor.common_modules, []);
      assert.deepEqual(result.cross_competitor.rare_modules, []);
      assert.deepEqual(result.cross_competitor.module_frequency, {});
      assert.equal(result.cross_competitor.avg_word_count, 0);
      assert.equal(result.cross_competitor.avg_sections, 0);
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('handles page with missing html_signals gracefully', () => {
    const tmp = makeTmpDir();
    try {
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({
        url: 'https://example.com/minimal',
        main_content_text: 'Just some text without any signals. ' + 'word '.repeat(195),
        headings: [],
      }));
      const result = runParsed({ pagesDir: tmp.pagesDir });
      assert.equal(result.competitors.length, 1);
      assert.deepEqual(result.competitors[0].detected_modules, []);
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('handles page with missing headings (single section)', () => {
    const tmp = makeTmpDir();
    try {
      writeFileSync(join(tmp.pagesDir, 'p1.json'), JSON.stringify({
        url: 'https://example.com/noheadings',
        main_content_text: 'All the content is in one big block without any headings at all. ' + 'word '.repeat(195),
        html_signals: { faq_sections: 0, tables: 0, ordered_lists: 0, unordered_lists: 0, video_embeds: 0, forms: 0, images_in_content: 0 },
      }));
      const result = runParsed({ pagesDir: tmp.pagesDir });
      assert.equal(result.competitors[0].section_count, 1, 'no headings means 1 section');
      assert.equal(result.competitors[0].sections[0].heading, '', 'single section has empty heading');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('detects at least 6 distinct module types across fixtures', () => {
    const result = runParsed();
    const allModules = new Set();
    for (const comp of result.competitors) {
      for (const mod of comp.detected_modules) {
        allModules.add(mod);
      }
    }
    assert.ok(allModules.size >= 6, `must detect at least 6 module types, got ${allModules.size}: ${[...allModules].join(', ')}`);
  });

  it('produces byte-identical output on repeated runs (determinism)', () => {
    const run1 = run();
    const run2 = run();
    assert.equal(run1, run2, 'same inputs must produce byte-identical output');
  });

  it('has_numbers is true when section text contains digits', () => {
    const result = runParsed();
    const alpha = result.competitors.find(c => c.domain === 'alpha.example.com');
    // "Strände und Buchten" section mentions "200", "35" etc.
    const strandSection = alpha.sections.find(s => s.heading === 'Strände und Buchten');
    assert.equal(strandSection.has_numbers, true, 'section with numbers must have has_numbers true');
  });

  it('filters out blocked pages with block/error heading patterns', () => {
    const result = runParsed();
    // page-blocked.json has heading "Why have I been blocked?" and must be excluded
    const blocked = result.competitors.find(c => c.domain === 'blocked.example.com');
    assert.equal(blocked, undefined, 'blocked page must not appear in competitors');
    // The 3 valid fixture pages must still be present
    assert.equal(result.competitors.length, 3, 'only the 3 valid fixture pages must be in output');
  });

  it('filters out pages with fewer than 200 words', () => {
    const tmp = makeTmpDir();
    try {
      writeFileSync(join(tmp.pagesDir, 'p-thin.json'), JSON.stringify({
        url: 'https://thin.example.com/page',
        main_content_text: 'Short content. Only a few words here.',
        headings: [{ level: 2, text: 'Short Section' }],
        html_signals: { faq_sections: 0, tables: 0, ordered_lists: 0, unordered_lists: 0, video_embeds: 0, forms: 0, images_in_content: 0 },
      }));
      // 200-word page that must not be filtered
      const substantialText = 'word '.repeat(200).trim();
      writeFileSync(join(tmp.pagesDir, 'p-substantial.json'), JSON.stringify({
        url: 'https://substantial.example.com/page',
        main_content_text: substantialText,
        headings: [],
        html_signals: { faq_sections: 0, tables: 0, ordered_lists: 0, unordered_lists: 0, video_embeds: 0, forms: 0, images_in_content: 0 },
      }));
      const result = runParsed({ pagesDir: tmp.pagesDir });
      assert.equal(result.competitors.length, 1, 'only the substantial page must pass the filter');
      assert.equal(result.competitors[0].domain, 'substantial.example.com');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('cross-competitor aggregates exclude filtered pages', () => {
    const tmp = makeTmpDir();
    try {
      // One valid page and one blocked page
      const validText = 'word '.repeat(300).trim();
      writeFileSync(join(tmp.pagesDir, 'p-valid.json'), JSON.stringify({
        url: 'https://valid.example.com/page',
        main_content_text: validText,
        headings: [{ level: 2, text: 'Main Section' }],
        html_signals: { faq_sections: 0, tables: 1, ordered_lists: 0, unordered_lists: 0, video_embeds: 0, forms: 0, images_in_content: 0 },
      }));
      writeFileSync(join(tmp.pagesDir, 'p-blocked.json'), JSON.stringify({
        url: 'https://errored.example.com/page',
        main_content_text: 'Just a moment... please wait while we check your browser.',
        headings: [{ level: 1, text: 'Just a moment' }],
        html_signals: { faq_sections: 0, tables: 0, ordered_lists: 0, unordered_lists: 0, video_embeds: 0, forms: 0, images_in_content: 0 },
      }));
      const result = runParsed({ pagesDir: tmp.pagesDir });
      assert.equal(result.competitors.length, 1, 'blocked page excluded from competitors');
      // avg_word_count should be based only on the valid page (300 words), not the blocked one
      assert.equal(result.cross_competitor.avg_word_count, 300, 'avg_word_count computed from valid pages only');
      // table module is only in the valid page; blocked page has no modules
      assert.equal(result.cross_competitor.module_frequency.table, 1, 'module_frequency based on valid pages only');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });

  it('logs competitor count to stderr before processing', () => {
    const proc = spawnSync('node', [script, '--pages-dir', fixturePages], { encoding: 'utf-8' });
    assert.ok(proc.stderr.includes('Analyzing page structure for'), 'stderr must include progress message');
    assert.ok(proc.stderr.includes('competitors'), 'stderr must mention competitors');
  });

  it('logs excluded pages to stderr', () => {
    const tmp = makeTmpDir();
    try {
      writeFileSync(join(tmp.pagesDir, 'p-blocked.json'), JSON.stringify({
        url: 'https://captcha.example.com/page',
        main_content_text: 'Please verify you are a human to continue.',
        headings: [{ level: 1, text: 'Please verify' }],
        html_signals: { faq_sections: 0, tables: 0, ordered_lists: 0, unordered_lists: 0, video_embeds: 0, forms: 0, images_in_content: 0 },
      }));
      const proc = spawnSync('node', [script, '--pages-dir', tmp.pagesDir], { encoding: 'utf-8' });
      assert.ok(proc.stderr.includes('Skipping'), 'must log "Skipping" to stderr for excluded page');
      assert.ok(proc.stderr.includes('captcha.example.com'), 'must include domain in stderr message');
    } finally {
      rmSync(tmp.dir, { recursive: true, force: true });
    }
  });
});
