// Deterministic slug generation from arbitrary strings.
// Replaces German umlauts, lowercases, normalises to hyphen-separated alphanumeric tokens.

const UMLAUT_MAP = [
  [/\u00e4/g, 'ae'], // ä
  [/\u00f6/g, 'oe'], // ö
  [/\u00fc/g, 'ue'], // ü
  [/\u00c4/g, 'Ae'], // Ä
  [/\u00d6/g, 'Oe'], // Ö
  [/\u00dc/g, 'Ue'], // Ü
  [/\u00df/g, 'ss'], // ß
];

/**
 * Convert a string to a URL-safe slug.
 * Umlaut replacement happens before lowercasing so that
 * capitalised umlauts produce the correct digraph casing
 * (which lowercase then normalises anyway).
 *
 * @param {string} input
 * @returns {string}
 */
export function slugify(input) {
  if (typeof input !== 'string') return '';

  let s = input;

  // Replace German umlauts before lowercasing
  for (const [re, rep] of UMLAUT_MAP) {
    s = s.replace(re, rep);
  }

  s = s.toLowerCase();

  // Replace any non-alphanumeric character with a hyphen
  s = s.replace(/[^a-z0-9]+/g, '-');

  // Trim leading/trailing hyphens
  s = s.replace(/^-+|-+$/g, '');

  return s;
}

export default slugify;
