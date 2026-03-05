#!/usr/bin/env node
// Page extractor using @mozilla/readability + jsdom
// Usage: node extract-page.mjs <URL>
// Outputs JSON with page metadata, headings, word count, link counts, and content preview.

import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';

const url = process.argv[2];
if (!url) {
  console.log(JSON.stringify({ error: 'Usage: node extract-page.mjs <URL>' }));
  process.exit(1);
}

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
  const main_content_preview = mainText.replace(/\s+/g, ' ').trim().slice(0, 300);

  console.log(JSON.stringify({
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
    main_content_preview,
  }, null, 2));
} catch (err) {
  console.log(JSON.stringify({ error: err.message, url }));
  process.exit(1);
}
