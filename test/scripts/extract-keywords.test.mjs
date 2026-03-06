import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { extractKeywords } from '../../src/keywords/extract-keywords.mjs';

// related_keywords shape: item.keyword_data.keyword / .keyword_info / .keyword_properties
const RELATED_RESPONSE = {
  tasks: [{
    result: [{
      items: [
        {
          keyword_data: {
            keyword: 'wrapped keyword',
            keyword_info: { search_volume: 1000, cpc: 2.5, monthly_searches: [] },
            keyword_properties: { keyword_difficulty: 42 },
          },
        },
        {
          keyword_data: {
            keyword: 'another wrapped',
            keyword_info: { search_volume: 500, cpc: 1.0, monthly_searches: [] },
            keyword_properties: { keyword_difficulty: 30 },
          },
        },
      ],
    }],
  }],
};

// keyword_suggestions shape: item.keyword / .keyword_info / .keyword_properties (no wrapper)
const SUGGESTIONS_RESPONSE = {
  tasks: [{
    result: [{
      items: [
        {
          se_type: 'google',
          keyword: 'flat keyword',
          keyword_info: { search_volume: 800, cpc: 1.8, monthly_searches: [] },
          keyword_properties: { keyword_difficulty: 55 },
        },
        {
          se_type: 'google',
          keyword: 'another flat',
          keyword_info: { search_volume: 300, cpc: 0.5, monthly_searches: [] },
          keyword_properties: { keyword_difficulty: 15 },
        },
      ],
    }],
  }],
};

describe('extractKeywords', () => {

  describe('related_keywords shape (keyword_data wrapper)', () => {
    it('extracts keywords from wrapped shape', () => {
      const result = extractKeywords(RELATED_RESPONSE);
      assert.equal(result.length, 2);
      assert.equal(result[0].keyword, 'wrapped keyword');
      assert.equal(result[0].search_volume, 1000);
      assert.equal(result[0].cpc, 2.5);
    });

    it('extracts difficulty when includeDifficulty is true', () => {
      const result = extractKeywords(RELATED_RESPONSE, { includeDifficulty: true });
      assert.equal(result[0].difficulty, 42);
      assert.equal(result[1].difficulty, 30);
    });

    it('omits difficulty when includeDifficulty is false', () => {
      const result = extractKeywords(RELATED_RESPONSE);
      assert.equal('difficulty' in result[0], false);
    });
  });

  describe('keyword_suggestions shape (no wrapper)', () => {
    it('extracts keywords from flat shape', () => {
      const result = extractKeywords(SUGGESTIONS_RESPONSE);
      assert.equal(result.length, 2);
      assert.equal(result[0].keyword, 'flat keyword');
      assert.equal(result[0].search_volume, 800);
      assert.equal(result[0].cpc, 1.8);
    });

    it('extracts difficulty from flat shape when includeDifficulty is true', () => {
      const result = extractKeywords(SUGGESTIONS_RESPONSE, { includeDifficulty: true });
      assert.equal(result[0].difficulty, 55);
      assert.equal(result[1].difficulty, 15);
    });

    it('omits difficulty from flat shape when includeDifficulty is false', () => {
      const result = extractKeywords(SUGGESTIONS_RESPONSE);
      assert.equal('difficulty' in result[0], false);
    });
  });

  describe('edge cases', () => {
    it('returns empty array for null input', () => {
      assert.deepEqual(extractKeywords(null), []);
    });

    it('returns empty array for missing items', () => {
      assert.deepEqual(extractKeywords({ tasks: [{ result: [{}] }] }), []);
    });

    it('returns empty array for empty items array', () => {
      assert.deepEqual(extractKeywords({ tasks: [{ result: [{ items: [] }] }] }), []);
    });

    it('skips items with no keyword in either shape', () => {
      const raw = {
        tasks: [{
          result: [{
            items: [
              { keyword_data: { keyword_info: {} } },
              { keyword_info: {} },
              { se_type: 'google' },
              null,
            ],
          }],
        }],
      };
      assert.deepEqual(extractKeywords(raw), []);
    });

    it('handles mixed shapes in a single response', () => {
      const raw = {
        tasks: [{
          result: [{
            items: [
              { keyword_data: { keyword: 'wrapped', keyword_info: { search_volume: 100 } } },
              { keyword: 'flat', keyword_info: { search_volume: 200 } },
            ],
          }],
        }],
      };
      const result = extractKeywords(raw);
      assert.equal(result.length, 2);
      assert.equal(result[0].keyword, 'wrapped');
      assert.equal(result[1].keyword, 'flat');
    });

    it('trims whitespace from keywords', () => {
      const raw = {
        tasks: [{
          result: [{
            items: [
              { keyword: '  spaced keyword  ', keyword_info: {} },
            ],
          }],
        }],
      };
      const result = extractKeywords(raw);
      assert.equal(result[0].keyword, 'spaced keyword');
    });

    it('clamps difficulty to 0-100 range', () => {
      const raw = {
        tasks: [{
          result: [{
            items: [
              { keyword: 'high', keyword_info: {}, keyword_properties: { keyword_difficulty: 150 } },
              { keyword: 'low', keyword_info: {}, keyword_properties: { keyword_difficulty: -10 } },
            ],
          }],
        }],
      };
      const result = extractKeywords(raw, { includeDifficulty: true });
      assert.equal(result[0].difficulty, 100);
      assert.equal(result[1].difficulty, 0);
    });

    it('returns null for missing search_volume and cpc', () => {
      const raw = {
        tasks: [{
          result: [{
            items: [
              { keyword: 'minimal', keyword_info: {} },
            ],
          }],
        }],
      };
      const result = extractKeywords(raw);
      assert.equal(result[0].search_volume, null);
      assert.equal(result[0].cpc, null);
      assert.equal(result[0].monthly_searches, null);
    });
  });

  describe('determinism', () => {
    it('produces identical output for identical input', () => {
      const run1 = JSON.stringify(extractKeywords(SUGGESTIONS_RESPONSE, { includeDifficulty: true }));
      const run2 = JSON.stringify(extractKeywords(SUGGESTIONS_RESPONSE, { includeDifficulty: true }));
      assert.equal(run1, run2);
    });
  });
});
