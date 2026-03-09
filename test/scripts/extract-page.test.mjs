import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import http from 'node:http';

const __dirname = dirname(fileURLToPath(import.meta.url));
const scriptPath = resolve(__dirname, '../../src/extractor/extract-page.mjs');

// Run extract-page.mjs as a child process (async to avoid blocking the server).
function runExtractor(url) {
  return new Promise((resolve, reject) => {
    execFile('node', [scriptPath, url], { timeout: 15000 }, (err, stdout, stderr) => {
      if (err) return reject(Object.assign(err, { stdout, stderr }));
      resolve(stdout);
    });
  });
}

// Serve fixture HTML on a random local port.
function createFixtureServer(html) {
  const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(html);
  });
  return new Promise((res) => {
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      res({ server, url: `http://127.0.0.1:${port}` });
    });
  });
}

const FIXTURE_HTML = `<!DOCTYPE html>
<html>
<head>
  <title>Test Page Title</title>
  <meta name="description" content="A test meta description">
  <link rel="canonical" href="https://example.com/test">
  <meta property="og:title" content="OG Test Title">
  <meta property="og:description" content="OG test description">
</head>
<body>
  <h1>Main Heading</h1>
  <h2>Section One</h2>
  <p>This is the first paragraph with enough text content to ensure that the main content text
  is significantly longer than the 300 character preview limit. We need multiple sentences here
  to make the test meaningful. The quick brown fox jumps over the lazy dog. Lorem ipsum dolor sit
  amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna
  aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.</p>
  <h3>Subsection A</h3>
  <p>More content in subsection A. This adds additional text to ensure we have well over 300
  characters of readable content for the preview comparison test.</p>
  <h2>Section Two</h2>
  <p>Final paragraph with some concluding remarks about the test page content.</p>
</body>
</html>`;

describe('extract-page.mjs', () => {
  it('outputs main_content_text, main_content_preview, and readability_title', async () => {
    const { server, url } = await createFixtureServer(FIXTURE_HTML);
    try {
      const stdout = await runExtractor(url);
      const result = JSON.parse(stdout);

      // main_content_text is present and non-empty
      assert.ok(typeof result.main_content_text === 'string', 'main_content_text must be a string');
      assert.ok(result.main_content_text.length > 0, 'main_content_text must be non-empty');

      // main_content_preview is present and capped at 300 chars
      assert.ok(typeof result.main_content_preview === 'string', 'main_content_preview must be a string');
      assert.ok(result.main_content_preview.length <= 300, 'main_content_preview must be <= 300 chars');

      // main_content_text is longer than main_content_preview for non-trivial pages
      assert.ok(
        result.main_content_text.length > result.main_content_preview.length,
        `main_content_text (${result.main_content_text.length}) must exceed main_content_preview (${result.main_content_preview.length})`
      );

      // main_content_preview is a prefix of main_content_text
      assert.equal(
        result.main_content_preview,
        result.main_content_text.slice(0, 300),
        'main_content_preview must be the first 300 chars of main_content_text'
      );

      // readability_title is present
      assert.ok(typeof result.readability_title === 'string', 'readability_title must be a string');

      // whitespace normalization: no runs of multiple spaces
      assert.ok(
        result.main_content_text.indexOf('  ') === -1,
        'main_content_text must have no consecutive spaces (whitespace-normalized)'
      );
    } finally {
      server.close();
    }
  });

  it('produces identical output for identical input (determinism)', async () => {
    const { server, url } = await createFixtureServer(FIXTURE_HTML);
    try {
      const run1 = await runExtractor(url);
      const run2 = await runExtractor(url);
      assert.equal(run1, run2, 'same input must produce byte-identical output');
    } finally {
      server.close();
    }
  });

  it('preserves backward-compatible fields', async () => {
    const { server, url } = await createFixtureServer(FIXTURE_HTML);
    try {
      const stdout = await runExtractor(url);
      const result = JSON.parse(stdout);

      const requiredFields = [
        'url', 'title', 'meta_description', 'canonical_url',
        'og_title', 'og_description', 'h1', 'headings',
        'word_count', 'link_count', 'main_content_preview',
      ];
      for (const field of requiredFields) {
        assert.ok(field in result, `field "${field}" must be present`);
      }
    } finally {
      server.close();
    }
  });

  it('outputs html_signals with element counts from Readability content', async () => {
    const htmlWithSignals = `<!DOCTYPE html>
<html><head><title>Signals Test</title></head>
<body>
  <h1>Signals</h1>
  <p>Intro paragraph with enough text to be parsed by Readability as the main content area.
  We need enough content for Readability to consider this article worthy of extraction.</p>
  <table><tr><td>Row 1</td></tr></table>
  <table><tr><td>Row 2</td></tr></table>
  <ul><li>Bullet</li></ul>
  <ol><li>Numbered</li></ol>
  <details><summary>FAQ item</summary><p>Answer</p></details>
  <iframe src="https://youtube.com/embed/x"></iframe>
  <video src="video.mp4"></video>
  <form><input type="text"></form>
  <img src="a.jpg"><img src="b.jpg"><img src="c.jpg">
  <p>More text to ensure Readability keeps this content as the main article body.
  Additional sentences help Readability determine this is substantial content worth parsing.</p>
</body></html>`;
    const { server, url } = await createFixtureServer(htmlWithSignals);
    try {
      const stdout = await runExtractor(url);
      const result = JSON.parse(stdout);
      assert.ok(result.html_signals, 'html_signals must be present');
      const hs = result.html_signals;
      assert.ok(typeof hs.faq_sections === 'number', 'faq_sections must be a number');
      assert.ok(typeof hs.tables === 'number', 'tables must be a number');
      assert.ok(typeof hs.ordered_lists === 'number', 'ordered_lists must be a number');
      assert.ok(typeof hs.unordered_lists === 'number', 'unordered_lists must be a number');
      assert.ok(typeof hs.video_embeds === 'number', 'video_embeds must be a number');
      assert.ok(typeof hs.forms === 'number', 'forms must be a number');
      assert.ok(typeof hs.images_in_content === 'number', 'images_in_content must be a number');
    } finally {
      server.close();
    }
  });

  it('html_signals has all zero counts for plain text page', async () => {
    const plainHtml = `<!DOCTYPE html>
<html><head><title>Plain</title></head>
<body><h1>Plain Page</h1><p>Just plain text content with no special elements. This paragraph
is long enough for Readability to parse it as the main article content area.</p></body></html>`;
    const { server, url } = await createFixtureServer(plainHtml);
    try {
      const stdout = await runExtractor(url);
      const result = JSON.parse(stdout);
      const hs = result.html_signals;
      assert.equal(hs.faq_sections, 0, 'no faq_sections in plain page');
      assert.equal(hs.tables, 0, 'no tables in plain page');
      assert.equal(hs.ordered_lists, 0, 'no ordered_lists in plain page');
      assert.equal(hs.unordered_lists, 0, 'no unordered_lists in plain page');
      assert.equal(hs.video_embeds, 0, 'no video_embeds in plain page');
      assert.equal(hs.forms, 0, 'no forms in plain page');
      assert.equal(hs.images_in_content, 0, 'no images_in_content in plain page');
    } finally {
      server.close();
    }
  });

  it('exits with error JSON when no URL is provided', () => {
    try {
      execFileSync('node', [scriptPath], { encoding: 'utf8', timeout: 10000 });
      assert.fail('should have exited with non-zero code');
    } catch (err) {
      const output = JSON.parse(err.stdout);
      assert.ok(output.error, 'error field must be present');
    }
  });
});
