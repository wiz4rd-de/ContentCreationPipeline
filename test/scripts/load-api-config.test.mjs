import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { loadEnv } from '../../src/utils/load-api-config.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixtures = join(__dirname, '..', 'fixtures', 'load-api-config');

describe('load-api-config', () => {

  describe('loadEnv', () => {

    it('returns auth and base for a valid env file', () => {
      const result = loadEnv(join(fixtures, 'valid.env'));
      assert.equal(result.auth, 'abc123base64token');
      assert.equal(result.base, 'https://api.dataforseo.com/v3');
    });

    it('skips comment lines and blank lines, ignores extra keys', () => {
      const result = loadEnv(join(fixtures, 'with-comments.env'));
      assert.equal(result.auth, 'commenttest==');
      assert.equal(result.base, 'https://api.dataforseo.com/v3');
      // EXTRA_KEY must not appear on the returned object
      assert.equal(Object.keys(result).length, 2);
    });

    it('throws with DATAFORSEO_AUTH in message when auth key is missing', () => {
      assert.throws(
        () => loadEnv(join(fixtures, 'missing-auth.env')),
        (err) => {
          assert.ok(err.message.includes('DATAFORSEO_AUTH'));
          return true;
        },
      );
    });

    it('throws with DATAFORSEO_BASE in message when base key is missing', () => {
      assert.throws(
        () => loadEnv(join(fixtures, 'missing-base.env')),
        (err) => {
          assert.ok(err.message.includes('DATAFORSEO_BASE'));
          return true;
        },
      );
    });

    it('throws when both values are empty strings', () => {
      // The first validation (auth) fires first
      assert.throws(
        () => loadEnv(join(fixtures, 'empty-values.env')),
        (err) => {
          assert.ok(err.message.includes('DATAFORSEO_AUTH'));
          return true;
        },
      );
    });

    it('throws an fs error when file does not exist', () => {
      assert.throws(
        () => loadEnv(join(fixtures, 'nonexistent.env')),
        (err) => {
          assert.ok(err.code === 'ENOENT');
          return true;
        },
      );
    });

    it('is deterministic: same input produces identical output', () => {
      const run1 = loadEnv(join(fixtures, 'valid.env'));
      const run2 = loadEnv(join(fixtures, 'valid.env'));
      assert.deepEqual(run1, run2);
    });

    it('handles values containing = signs (e.g. base64 tokens)', () => {
      // with-comments.env has DATAFORSEO_AUTH=commenttest==
      // The trailing == must be preserved, not truncated
      const result = loadEnv(join(fixtures, 'with-comments.env'));
      assert.equal(result.auth, 'commenttest==');
    });

  });

});
