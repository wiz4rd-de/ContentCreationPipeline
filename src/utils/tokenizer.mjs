// Shared tokenizer module.
// Provides pure, deterministic tokenization and stopword-removal utilities
// used by analyze-content-topics.mjs and the IDF build script.

import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Lowercase, strip punctuation (keeping letters including umlauts and digits),
 * split on whitespace, and filter single-character tokens.
 *
 * @param {string} text
 * @returns {string[]}
 */
export function tokenize(text) {
  const cleaned = text
    .toLowerCase()
    .replace(/[^a-z0-9\u00e4\u00f6\u00fc\u00df\u00e0-\u00ff]+/g, ' ')
    .trim();
  if (cleaned.length === 0) return [];
  return cleaned.split(/\s+/).filter(w => w.length > 1);
}

/**
 * Filter tokens not present in the given stopword Set.
 * Pure function — takes an explicit Set rather than closing over module state.
 *
 * @param {string[]} tokens
 * @param {Set<string>} stopwordSet
 * @returns {string[]}
 */
export function removeStopwords(tokens, stopwordSet) {
  return tokens.filter(t => stopwordSet.has(t) === false);
}

/**
 * Load stopwords.json from src/utils/ and return a combined Set.
 * For language 'de', combines both 'de' and 'en' arrays (matching the
 * original behavior in analyze-content-topics.mjs lines 35-38).
 * For other languages, returns only that language's set.
 *
 * @param {string} language
 * @returns {Set<string>}
 */
export function loadStopwordSet(language) {
  const stopwordsPath = join(__dirname, 'stopwords.json');
  const data = JSON.parse(readFileSync(stopwordsPath, 'utf-8'));
  const words = [
    ...(data[language] || []),
    ...(language === 'de' ? (data.en || []) : []),
  ];
  return new Set(words);
}
