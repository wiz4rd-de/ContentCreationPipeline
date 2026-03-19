import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { tokenize, removeStopwords, loadStopwordSet } from '../../src/utils/tokenizer.mjs';

describe('tokenizer', () => {

  // --- tokenize ---

  describe('tokenize', () => {

    it('lowercases input', () => {
      assert.deepEqual(tokenize('Hello WORLD'), ['hello', 'world']);
    });

    it('preserves German umlauts', () => {
      // Input already uses lowercase umlaut code points; tokenizer must not strip them
      const result = tokenize('aerzte f\u00fcr \u00fcbergewicht');
      assert.ok(result.includes('f\u00fcr'), '"f\u00fcr" must be preserved');
      assert.ok(result.includes('\u00fcbergewicht'), '"\u00fcbergewicht" must be preserved');
    });

    it('replaces punctuation with spaces', () => {
      assert.deepEqual(tokenize('hello, world! test.'), ['hello', 'world', 'test']);
    });

    it('filters tokens with length <= 1', () => {
      assert.deepEqual(tokenize('a b cd ef'), ['cd', 'ef']);
    });

    it('returns empty array for empty string', () => {
      assert.deepEqual(tokenize(''), []);
    });

    it('returns empty array for punctuation-only input', () => {
      assert.deepEqual(tokenize('!!! ... ???'), []);
    });

    it('handles multiple whitespace', () => {
      assert.deepEqual(tokenize('  hello   world  '), ['hello', 'world']);
    });

    it('handles digits and alphanumeric tokens', () => {
      assert.deepEqual(tokenize('test123 42 hello'), ['test123', '42', 'hello']);
    });

  });

  // --- removeStopwords ---

  describe('removeStopwords', () => {

    it('filters stopwords from token list', () => {
      assert.deepEqual(
        removeStopwords(['hello', 'und', 'world'], new Set(['und'])),
        ['hello', 'world']
      );
    });

    it('returns all tokens when no stopwords match', () => {
      assert.deepEqual(
        removeStopwords(['hello', 'world'], new Set(['xyz'])),
        ['hello', 'world']
      );
    });

    it('returns empty array when all tokens are stopwords', () => {
      assert.deepEqual(
        removeStopwords(['und', 'der'], new Set(['und', 'der'])),
        []
      );
    });

    it('works with empty token array', () => {
      assert.deepEqual(
        removeStopwords([], new Set(['und'])),
        []
      );
    });

  });

  // --- loadStopwordSet ---

  describe('loadStopwordSet', () => {

    it('returns a Set for "de"', () => {
      const result = loadStopwordSet('de');
      assert.ok(result instanceof Set, 'must return a Set instance');
      assert.ok(result.size > 0, 'DE set must not be empty');
    });

    it('DE set includes both DE stopwords and EN stopwords', () => {
      const result = loadStopwordSet('de');
      assert.ok(result.has('und'), 'DE set must contain "und" (German stopword)');
      assert.ok(result.has('the'), 'DE set must contain "the" (English stopword, merged for de)');
    });

    it('EN set includes EN stopwords but not DE-only stopwords', () => {
      const result = loadStopwordSet('en');
      assert.ok(result.has('the'), 'EN set must contain "the"');
      assert.ok(result.has('und') === false, 'EN set must not contain "und" (DE-only stopword)');
    });

    it('returns empty Set for unknown language', () => {
      const result = loadStopwordSet('xx');
      assert.ok(result instanceof Set, 'must return a Set instance');
      assert.equal(result.size, 0, 'unknown language must yield empty Set');
    });

  });

  // --- Determinism ---

  describe('determinism', () => {

    it('tokenize produces identical output on repeated calls', () => {
      const input = 'Aerzte f\u00fcr \u00dcbergewicht und Ern\u00e4hrung';
      const results = Array.from({ length: 50 }, () => tokenize(input).join('|'));
      const unique = new Set(results);
      assert.equal(unique.size, 1, 'tokenize must be deterministic across 50 calls');
    });

    it('loadStopwordSet returns the same Set contents on repeated calls', () => {
      const s1 = loadStopwordSet('de');
      const s2 = loadStopwordSet('de');
      assert.equal(s1.size, s2.size, 'Set size must be identical across calls');
      for (const word of s1) {
        assert.ok(s2.has(word), `word "${word}" must be present in second call result`);
      }
    });

  });

});
