#!/usr/bin/env node
// Page extractor using @mozilla/readability + jsdom
// Usage: node extract-page.mjs <URL>
// Outputs JSON with page metadata, headings, word count, link counts, and content preview.

import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';
import { writeFileSync } from 'node:fs';

const args = process.argv.slice(2);
const url = args.find(a => !a.startsWith('--'));
const outputFlag = args.indexOf('--output');
const outputPath = outputFlag !== -1 ? args[outputFlag + 1] : null;

if (!url) {
  console.log(JSON.stringify({ error: 'Usage: node extract-page.mjs <URL> [--output <path>]' }));
  process.exit(1);
}

console.error(`Extracting: ${url} ...`);

try {
  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; ContentExtractor/1.0)' },
    redirect: 'follow',
    signal: AbortSignal.timeout(15000),
  });
  const html = await res.text();
  const dom = new JSDOM(html, { url });
  const doc = dom.window.document;

  // Title
  const title = doc.querySelector('title')?.textContent?.trim() || '';

  // Meta description
  const meta_description = doc.querySelector('meta[name="description"]')?.getAttribute('content')?.trim() || '';

  // Canonical URL
  const canonical_url = doc.querySelector('link[rel="canonical"]')?.getAttribute('href')?.trim() || '';

  // Open Graph
  const og_title = doc.querySelector('meta[property="og:title"]')?.getAttribute('content')?.trim() || '';
  const og_description = doc.querySelector('meta[property="og:description"]')?.getAttribute('content')?.trim() || '';

  // H1
  const h1 = doc.querySelector('h1')?.textContent?.trim().replace(/\s+/g, ' ') || '';

  // Headings in DOM order (h2–h4)
  const headings = [];
  doc.querySelectorAll('h2, h3, h4').forEach(el => {
    const level = parseInt(el.tagName[1], 10);
    headings.push({ level, text: el.textContent.trim().replace(/\s+/g, ' ') });
  });

  // Links
  const hostname = new URL(url).hostname;
  let internal = 0, external = 0;
  doc.querySelectorAll('a[href]').forEach(a => {
    try {
      const linkHost = new URL(a.href, url).hostname;
      if (linkHost === hostname) internal++; else external++;
    } catch { /* skip malformed URLs */ }
  });

  // Readability for main content
  const cloneDOM = new JSDOM(html, { url });
  const reader = new Readability(cloneDOM.window.document);
  const article = reader.parse();
  const mainText = article?.textContent || '';
  const word_count = mainText.split(/\s+/).filter(Boolean).length;
  const main_content_text = mainText.replace(/\s+/g, ' ').trim();
  const main_content_preview = main_content_text.slice(0, 300);
  const readability_title = article?.title || '';

  // HTML signals from Readability-parsed content
  const html_signals = { faq_sections: 0, tables: 0, ordered_lists: 0, unordered_lists: 0, video_embeds: 0, forms: 0, images_in_content: 0 };
  const articleHtml = article?.content || '';
  if (articleHtml.length > 0) {
    const contentDOM = new JSDOM(articleHtml);
    const contentDoc = contentDOM.window.document;
    html_signals.faq_sections = contentDoc.querySelectorAll('details, summary').length;
    html_signals.tables = contentDoc.querySelectorAll('table').length;
    html_signals.ordered_lists = contentDoc.querySelectorAll('ol').length;
    html_signals.unordered_lists = contentDoc.querySelectorAll('ul').length;
    html_signals.video_embeds = contentDoc.querySelectorAll('iframe, video').length;
    html_signals.forms = contentDoc.querySelectorAll('form').length;
    html_signals.images_in_content = contentDoc.querySelectorAll('img').length;
  }

  const json = JSON.stringify({
    url,
    title,
    meta_description,
    canonical_url,
    og_title,
    og_description,
    h1,
    headings,
    word_count,
    link_count: { internal, external },
    main_content_text,
    main_content_preview,
    readability_title,
    html_signals,
  }, null, 2);
  if (outputPath) {
    writeFileSync(outputPath, json);
  } else {
    console.log(json);
  }
} catch (err) {
  const errJson = JSON.stringify({ error: err.message, url });
  if (outputPath) {
    writeFileSync(outputPath, errJson);
  } else {
    console.log(errJson);
  }
  process.exit(1);
}
