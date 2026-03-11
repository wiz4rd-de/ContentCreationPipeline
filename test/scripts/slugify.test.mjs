import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { slugify } from '../../src/utils/slugify.mjs';

describe('slugify', () => {

  // --- Core transforms ---

  describe('core transforms', () => {
    it('converts spaces to hyphens and lowercases', () => {
      assert.equal(slugify('thailand urlaub'), 'thailand-urlaub');
    });

    it('replaces ae, oe, ue umlauts', () => {
      assert.equal(slugify('sch\u00f6nste Str\u00e4nde Thailand'), 'schoenste-straende-thailand');
    });

    it('replaces uppercase umlauts', () => {
      assert.equal(slugify('\u00c4rger \u00d6ffnung \u00dcbung'), 'aerger-oeffnung-uebung');
    });

    it('replaces Eszett (\u00df) with ss', () => {
      assert.equal(slugify('Stra\u00dfe'), 'strasse');
    });

    it('handles mixed German and English input', () => {
      assert.equal(slugify('Urlaub Mallorca'), 'urlaub-mallorca');
    });
  });

  // --- Edge cases ---

  describe('edge cases', () => {
    it('returns empty string for empty input', () => {
      assert.equal(slugify(''), '');
    });

    it('returns empty string for non-string input', () => {
      assert.equal(slugify(undefined), '');
      assert.equal(slugify(null), '');
      assert.equal(slugify(42), '');
    });

    it('returns empty string when input is only special characters', () => {
      assert.equal(slugify('!!!@@@###$$$'), '');
    });

    it('handles numeric-only input', () => {
      assert.equal(slugify('2026'), '2026');
      assert.equal(slugify('123 456'), '123-456');
    });

    it('collapses consecutive hyphens', () => {
      assert.equal(slugify('a   b'), 'a-b');
      assert.equal(slugify('a---b'), 'a-b');
      assert.equal(slugify('a - b'), 'a-b');
    });

    it('trims leading and trailing hyphens', () => {
      assert.equal(slugify('--hello--'), 'hello');
      assert.equal(slugify(' hello '), 'hello');
    });

    it('is idempotent (re-slugifying produces same result)', () => {
      const once = slugify('sch\u00f6nste Str\u00e4nde Thailand');
      const twice = slugify(once);
      assert.equal(once, twice);
    });
  });

  // --- Determinism ---

  describe('determinism', () => {
    it('produces identical output for identical input across multiple calls', () => {
      const input = 'AI-driven Development & SEO Reporting 2026';
      const results = Array.from({ length: 100 }, () => slugify(input));
      const unique = new Set(results);
      assert.equal(unique.size, 1, 'all 100 calls must return the same value');
    });
  });

  // --- Regression against existing directory names ---

  describe('regression: existing directory names', () => {
    const cases = [
      ['thailand urlaub', 'thailand-urlaub'],
      ['sch\u00f6nste Str\u00e4nde Thailand', 'schoenste-straende-thailand'],
      ['keyword recherche', 'keyword-recherche'],
      ['Urlaub Mallorca', 'urlaub-mallorca'],
      ['AI-driven development', 'ai-driven-development'],
      ['SEO Reporting', 'seo-reporting'],
    ];

    for (const [input, expected] of cases) {
      it(`slugify("${input}") === "${expected}"`, () => {
        assert.equal(slugify(input), expected);
      });
    }
  });

});
