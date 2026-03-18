import { describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';

import { calculateBackoff, callEndpoint } from '../../src/keywords/fetch-keywords.mjs';

describe('fetch-keywords', () => {

  // --- calculateBackoff ---

  describe('calculateBackoff', () => {
    const opts = { initialDelay: 1000, factor: 2, maxDelay: 8000 };

    it('returns initialDelay (1000ms) for attempt 0', () => {
      assert.equal(calculateBackoff(0, opts), 1000);
    });

    it('returns initialDelay * factor for attempt 1 (2000ms for factor 2)', () => {
      assert.equal(calculateBackoff(1, opts), 2000);
    });

    it('returns initialDelay * factor^2 for attempt 2 (4000ms)', () => {
      assert.equal(calculateBackoff(2, opts), 4000);
    });

    it('caps at maxDelay (8000ms) for attempt 3 and beyond', () => {
      assert.equal(calculateBackoff(3, opts), 8000);
      assert.equal(calculateBackoff(100, opts), 8000);
    });

    it('produces deterministic output: same attempt number always returns same delay', () => {
      const run1 = calculateBackoff(0, opts);
      const run2 = calculateBackoff(0, opts);
      assert.equal(run1, run2, 'attempt 0 must be deterministic');

      const run3 = calculateBackoff(2, opts);
      const run4 = calculateBackoff(2, opts);
      assert.equal(run3, run4, 'attempt 2 must be deterministic');

      const run5 = calculateBackoff(100, opts);
      const run6 = calculateBackoff(100, opts);
      assert.equal(run5, run6, 'high attempt numbers must be deterministic');
    });
  });

  // --- callEndpoint retry logic ---

  describe('callEndpoint retry behaviour', () => {
    const AUTH = 'dummytoken';
    const LABEL = 'test_endpoint';
    const URL = 'https://api.example.com/test';
    const BODY = [{ keyword: 'test' }];

    // Helper: create a mock fetch that returns HTTP responses in sequence.
    // Each entry is either a { status, body } object or an Error to throw.
    function makeFetch(sequence) {
      let callCount = 0;
      return async (_url, _opts) => {
        const entry = sequence[callCount];
        callCount += 1;
        if (entry instanceof Error) throw entry;
        const text = JSON.stringify(entry.body);
        return {
          status: entry.status,
          ok: entry.status >= 200 && entry.status < 300,
          text: async () => text,
          json: async () => entry.body,
        };
      };
    }

    it('returns parsed JSON on first successful call', async () => {
      const fetchMock = makeFetch([
        { status: 200, body: { result: 'ok' } },
      ]);
      const result = await callEndpoint(URL, BODY, AUTH, LABEL, fetchMock);
      assert.deepEqual(result, { result: 'ok' });
    });

    it('retries on HTTP 500 and succeeds on second attempt', async () => {
      const fetchMock = makeFetch([
        { status: 500, body: 'Server Error' },
        { status: 200, body: { result: 'ok' } },
      ]);
      const result = await callEndpoint(URL, BODY, AUTH, LABEL, fetchMock);
      assert.deepEqual(result, { result: 'ok' });
    });

    it('retries on network error (TypeError) and succeeds on second attempt', async () => {
      const fetchMock = makeFetch([
        new TypeError('fetch failed'),
        { status: 200, body: { result: 'recovered' } },
      ]);
      const result = await callEndpoint(URL, BODY, AUTH, LABEL, fetchMock);
      assert.deepEqual(result, { result: 'recovered' });
    });

    it('does NOT retry on HTTP 4xx — throws immediately', async () => {
      let callCount = 0;
      const fetchMock = async () => {
        callCount += 1;
        return {
          status: 401,
          ok: false,
          text: async () => 'Unauthorized',
          json: async () => null,
        };
      };
      await assert.rejects(
        () => callEndpoint(URL, BODY, AUTH, LABEL, fetchMock),
        (err) => {
          assert.ok(err.message.includes('401'), `Expected 401 in message, got: ${err.message}`);
          return true;
        },
      );
      assert.equal(callCount, 1, 'Should not have retried a 4xx response');
    });

    it('throws after exhausting all retries on persistent 500s', async () => {
      const fetchMock = makeFetch([
        { status: 500, body: 'err' },
        { status: 500, body: 'err' },
        { status: 500, body: 'err' },
        { status: 500, body: 'err' },
      ]);
      await assert.rejects(
        () => callEndpoint(URL, BODY, AUTH, LABEL, fetchMock),
        (err) => {
          assert.ok(err.message.includes('500'), `Expected 500 in message, got: ${err.message}`);
          return true;
        },
      );
    });

    it('throws after exhausting all retries on persistent network errors', async () => {
      const fetchMock = makeFetch([
        new TypeError('fetch failed'),
        new TypeError('fetch failed'),
        new TypeError('fetch failed'),
        new TypeError('fetch failed'),
      ]);
      await assert.rejects(
        () => callEndpoint(URL, BODY, AUTH, LABEL, fetchMock),
        (err) => {
          assert.ok(err instanceof TypeError, 'Should re-throw original TypeError');
          return true;
        },
      );
    });
  });

});
