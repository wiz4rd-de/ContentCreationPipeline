#!/usr/bin/env node
// Deterministic page structure analyzer.
// Detects content modules (FAQ, table, list, video, form, image gallery),
// computes per-section word/sentence counts and depth scores,
// and produces cross-competitor module frequency analysis.
//
// Usage: node analyze-page-structure.mjs --pages-dir <pages/>
// Outputs JSON to stdout. Same inputs always produce byte-identical output.

import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

// --- CLI parsing ---
const args = process.argv.slice(2);
function flag(name) {
  const idx = args.indexOf(name);
  if (idx === -1 || idx + 1 >= args.length) return undefined;
  return args[idx + 1];
}

const pagesDir = flag('--pages-dir');
const outputPath = flag('--output') || null;

if (pagesDir === undefined) {
  console.error('Usage: node analyze-page-structure.mjs --pages-dir <pages/>');
  process.exit(1);
}

// --- Load page files (sorted for determinism) ---
const pageFiles = readdirSync(pagesDir)
  .filter(f => f.endsWith('.json'))
  .sort();

if (pageFiles.length === 0) {
  const json = JSON.stringify({ competitors: [], cross_competitor: { common_modules: [], rare_modules: [], module_frequency: {}, avg_word_count: 0, avg_sections: 0 } }, null, 2);
  if (outputPath) {
    writeFileSync(outputPath, json);
  } else {
    console.log(json);
  }
  process.exit(0);
}

// --- Helpers ---

function countWords(text) {
  return text.split(/\s+/).filter(Boolean).length;
}

function countSentences(text) {
  // Split on sentence-ending punctuation followed by space or end-of-string
  const sentences = text.split(/[.?!]+/).filter(s => s.trim().length > 0);
  return sentences.length;
}

function hasNumbers(text) {
  return /\d/.test(text);
}

function hasLists(signals) {
  return (signals.ordered_lists > 0 || signals.unordered_lists > 0);
}

function computeDepthScore(sentenceCount) {
  if (sentenceCount <= 2) return 'shallow';
  if (sentenceCount <= 6) return 'basic';
  return 'detailed';
}

// FAQ heading patterns (German + English)
const FAQ_HEADING_RE = /\b(faq|fragen|haeufig|frequently\s+asked|h.ufig)\b/i;

// Block/error page heading patterns — conservative: only clear bot-wall and error pages
const BLOCK_HEADING_RE = /why have i been blocked|access denied|403 forbidden|please verify|checking your browser|just a moment|enable javascript and cookies|attention required/i;

const MIN_WORD_COUNT = 200;

// Returns a string reason if the page should be excluded, or null if it's acceptable.
function blockReason(mainText, headingTexts) {
  if (mainText.length === 0) return 'missing main_content_text';
  const wc = countWords(mainText);
  if (wc < MIN_WORD_COUNT) return `too few words (${wc} < ${MIN_WORD_COUNT})`;
  const blockedHeading = headingTexts.find(t => BLOCK_HEADING_RE.test(t));
  if (blockedHeading) return `block/error heading: "${blockedHeading}"`;
  return null;
}

function detectModules(signals, headingTexts) {
  const modules = [];

  // FAQ: heading text match or html_signals.faq_sections > 0
  const hasFaqHeading = headingTexts.some(t => FAQ_HEADING_RE.test(t));
  if (hasFaqHeading || signals.faq_sections > 0) {
    modules.push('faq');
  }

  if (signals.tables > 0) modules.push('table');
  if (signals.ordered_lists > 0 || signals.unordered_lists > 0) modules.push('list');
  if (signals.video_embeds > 0) modules.push('video');
  if (signals.images_in_content > 3) modules.push('image_gallery');
  if (signals.forms > 0) modules.push('form');

  // Sort for deterministic output
  modules.sort();
  return modules;
}

// Split main_content_text into sections based on heading text markers.
// The text between consecutive heading texts forms a section.
function splitSections(mainText, headings) {
  if (headings.length === 0) {
    // No headings: entire text is one section
    return [{ heading: '', level: 0, text: mainText }];
  }

  const sections = [];

  // Find positions of each heading in the text
  const positions = [];
  for (const h of headings) {
    const idx = mainText.indexOf(h.text);
    if (idx >= 0) {
      positions.push({ heading: h.text, level: h.level, pos: idx });
    }
  }

  // Sort by position in text (should already be in order, but ensure determinism)
  positions.sort((a, b) => a.pos - b.pos);

  // Intro section (text before first heading)
  if (positions.length > 0 && positions[0].pos > 0) {
    const introText = mainText.slice(0, positions[0].pos).trim();
    if (introText.length > 0) {
      sections.push({ heading: '', level: 0, text: introText });
    }
  }

  // Sections between headings
  for (let i = 0; i < positions.length; i++) {
    const start = positions[i].pos + positions[i].heading.length;
    const end = (i + 1 < positions.length) ? positions[i + 1].pos : mainText.length;
    const sectionText = mainText.slice(start, end).trim();
    sections.push({
      heading: positions[i].heading,
      level: positions[i].level,
      text: sectionText,
    });
  }

  return sections;
}

// --- Process each page ---
console.error(`Analyzing page structure for ${pageFiles.length} competitors...`);
const competitors = [];

for (const file of pageFiles) {
  const page = JSON.parse(readFileSync(join(pagesDir, file), 'utf-8'));
  const mainText = page.main_content_text || '';
  const headings = page.headings || [];
  const signals = page.html_signals || {
    faq_sections: 0, tables: 0, ordered_lists: 0,
    unordered_lists: 0, video_embeds: 0, forms: 0, images_in_content: 0,
  };

  const headingTexts = headings.map(h => h.text);
  const detectedModules = detectModules(signals, headingTexts);

  const rawSections = splitSections(mainText, headings);
  const sections = rawSections.map(s => {
    const wc = countWords(s.text);
    const sc = countSentences(s.text);
    return {
      heading: s.heading,
      level: s.level,
      word_count: wc,
      sentence_count: sc,
      has_numbers: hasNumbers(s.text),
      has_lists: hasLists(signals),
      depth_score: computeDepthScore(sc),
    };
  });

  // Extract domain from URL
  let domain = '';
  try {
    domain = new URL(page.url).hostname;
  } catch { /* skip */ }

  // Quality filter: skip blocked/error/thin pages
  const reason = blockReason(mainText, headingTexts);
  if (reason !== null) {
    process.stderr.write(`Skipping ${domain || file}: ${reason}\n`);
    continue;
  }

  competitors.push({
    url: page.url || '',
    domain,
    total_word_count: countWords(mainText),
    section_count: sections.length,
    detected_modules: detectedModules,
    sections,
  });
}

// --- Cross-competitor analysis ---
const totalCompetitors = competitors.length;

// Count module occurrences across competitors
const moduleCounts = {};
for (const comp of competitors) {
  for (const mod of comp.detected_modules) {
    moduleCounts[mod] = (moduleCounts[mod] || 0) + 1;
  }
}

// Sort module_frequency keys for deterministic output
const sortedModuleKeys = Object.keys(moduleCounts).sort();
const module_frequency = {};
for (const k of sortedModuleKeys) {
  module_frequency[k] = moduleCounts[k];
}

// Common: present in >= 70% of competitors
// Rare: present in <= 20% of competitors
const commonThreshold = totalCompetitors * 0.7;
const rareThreshold = totalCompetitors * 0.2;

const common_modules = sortedModuleKeys
  .filter(k => moduleCounts[k] >= commonThreshold)
  .sort();

const rare_modules = sortedModuleKeys
  .filter(k => moduleCounts[k] <= rareThreshold)
  .sort();

const totalWordCount = competitors.reduce((sum, c) => sum + c.total_word_count, 0);
const totalSections = competitors.reduce((sum, c) => sum + c.section_count, 0);

const avg_word_count = Math.round(totalWordCount / totalCompetitors);
const avg_sections = Math.round(totalSections / totalCompetitors);

const output = {
  competitors,
  cross_competitor: {
    common_modules,
    rare_modules,
    module_frequency,
    avg_word_count,
    avg_sections,
  },
};

const json = JSON.stringify(output, null, 2);
if (outputPath) {
  writeFileSync(outputPath, json);
} else {
  console.log(json);
}
