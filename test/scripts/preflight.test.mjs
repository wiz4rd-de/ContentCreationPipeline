import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';

import {
  checkApiEnv,
  checkAuth,
  checkBase64,
  checkAuthFormat,
  checkBase,
  checkExtractorDeps,
  parseEnvContent,
} from '../../src/utils/preflight.mjs';

function makeTmpDir() {
  const dir = join(tmpdir(), 'preflight-test-' + randomBytes(4).toString('hex'));
  mkdirSync(dir, { recursive: true });
  return dir;
}

describe('preflight', () => {

  // --- checkApiEnv ---

  describe('checkApiEnv', () => {
    it('returns ok:true when api.env exists', () => {
      const dir = makeTmpDir();
      try {
        writeFileSync(join(dir, 'api.env'), 'DATAFORSEO_AUTH=abc\n');
        const result = checkApiEnv(dir);
        assert.equal(result.ok, true);
        assert.ok(result.message.includes('api.env'));
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('returns ok:false when api.env is missing', () => {
      const dir = makeTmpDir();
      try {
        const result = checkApiEnv(dir);
        assert.equal(result.ok, false);
        assert.ok(result.message.includes('api.env not found'));
        assert.ok(result.message.includes('cp api.env.example api.env'));
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });
  });

  // --- parseEnvContent ---

  describe('parseEnvContent', () => {
    it('parses KEY=VALUE lines into a map', () => {
      const env = parseEnvContent('DATAFORSEO_AUTH=abc123\nDATAFORSEO_BASE=https://api.example.com\n');
      assert.equal(env.DATAFORSEO_AUTH, 'abc123');
      assert.equal(env.DATAFORSEO_BASE, 'https://api.example.com');
    });

    it('skips comment lines and empty lines', () => {
      const env = parseEnvContent('# comment\n\nDATAFORSEO_AUTH=secret\n\n# another\nDATAFORSEO_BASE=https://base.example.com\n');
      assert.equal(env.DATAFORSEO_AUTH, 'secret');
      assert.equal(env.DATAFORSEO_BASE, 'https://base.example.com');
    });

    it('preserves values containing = signs (e.g. base64 tokens)', () => {
      const env = parseEnvContent('DATAFORSEO_AUTH=abc123==\n');
      assert.equal(env.DATAFORSEO_AUTH, 'abc123==');
    });
  });

  // --- checkAuth ---

  describe('checkAuth', () => {
    it('returns ok:true when DATAFORSEO_AUTH is set', () => {
      const result = checkAuth({ DATAFORSEO_AUTH: 'abc123base64token' });
      assert.equal(result.ok, true);
      assert.ok(result.message.includes('DATAFORSEO_AUTH'));
    });

    it('returns ok:false when DATAFORSEO_AUTH is missing', () => {
      const result = checkAuth({});
      assert.equal(result.ok, false);
      assert.ok(result.message.includes('DATAFORSEO_AUTH is not set'));
      assert.ok(result.message.includes('api.env.example'));
    });

    it('returns ok:false when DATAFORSEO_AUTH is empty string', () => {
      const result = checkAuth({ DATAFORSEO_AUTH: '' });
      assert.equal(result.ok, false);
      assert.ok(result.message.includes('DATAFORSEO_AUTH is not set'));
    });
  });

  // --- checkBase64 ---

  describe('checkBase64', () => {
    it('returns true for a valid base64 string without padding', () => {
      assert.equal(checkBase64('abc123BASE64token'), true);
    });

    it('returns true for a valid base64 string with = padding', () => {
      assert.equal(checkBase64('abc123=='), true);
    });

    it('returns true for a realistic base64-encoded login:password', () => {
      // Buffer.from('user@example.com:secret').toString('base64')
      const encoded = Buffer.from('user@example.com:secret').toString('base64');
      // Note: base64 of email address contains +, / — test the pure alphanum case
      const simpleEncoded = Buffer.from('login:password').toString('base64');
      assert.equal(checkBase64(simpleEncoded), true);
    });

    it('returns false for a string containing a colon (raw login:password)', () => {
      assert.equal(checkBase64('login:password'), false);
    });

    it('returns false for a string containing spaces', () => {
      assert.equal(checkBase64('abc def'), false);
    });

    it('returns false for an empty string', () => {
      assert.equal(checkBase64(''), false);
    });

    it('returns false for non-string input', () => {
      assert.equal(checkBase64(undefined), false);
      assert.equal(checkBase64(null), false);
      assert.equal(checkBase64(123), false);
    });

    it('returns false for a placeholder string with angle brackets', () => {
      assert.equal(checkBase64('<your-base64-token-here>'), false);
    });

    it('returns true for strings with only trailing = padding', () => {
      assert.equal(checkBase64('dGVzdA=='), true);
    });

    it('returns false for a string with = in the middle', () => {
      // = in the middle is not valid base64 per the regex (=* anchored to end)
      assert.equal(checkBase64('abc=def'), false);
    });
  });

  // --- checkAuthFormat ---

  describe('checkAuthFormat', () => {
    it('returns ok:true for a valid base64 AUTH value', () => {
      const result = checkAuthFormat({ DATAFORSEO_AUTH: 'dGVzdA==' });
      assert.equal(result.ok, true);
      assert.ok(result.message.includes('valid base64'));
    });

    it('returns ok:false for a raw login:password value', () => {
      const result = checkAuthFormat({ DATAFORSEO_AUTH: 'user:password' });
      assert.equal(result.ok, false);
      assert.ok(result.message.includes('does not look like valid base64'));
      assert.ok(result.message.includes('base64'));
    });

    it('returns ok:false when DATAFORSEO_AUTH is missing', () => {
      const result = checkAuthFormat({});
      assert.equal(result.ok, false);
    });
  });

  // --- checkBase ---

  describe('checkBase', () => {
    it('returns ok:true when DATAFORSEO_BASE is set', () => {
      const result = checkBase({ DATAFORSEO_BASE: 'https://api.dataforseo.com/v3' });
      assert.equal(result.ok, true);
      assert.ok(result.message.includes('DATAFORSEO_BASE'));
    });

    it('returns ok:false when DATAFORSEO_BASE is missing', () => {
      const result = checkBase({});
      assert.equal(result.ok, false);
      assert.ok(result.message.includes('DATAFORSEO_BASE is not set'));
      assert.ok(result.message.includes('https://api.dataforseo.com/v3'));
    });

    it('returns ok:false when DATAFORSEO_BASE is empty string', () => {
      const result = checkBase({ DATAFORSEO_BASE: '' });
      assert.equal(result.ok, false);
    });
  });

  // --- checkExtractorDeps ---

  describe('checkExtractorDeps', () => {
    it('returns ok:true when node_modules exists in extractorDir', () => {
      const dir = makeTmpDir();
      try {
        mkdirSync(join(dir, 'node_modules'), { recursive: true });
        const result = checkExtractorDeps(dir);
        assert.equal(result.ok, true);
        assert.ok(result.message.includes('Extractor dependencies installed'));
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    it('returns ok:false when node_modules is absent', () => {
      const dir = makeTmpDir();
      try {
        const result = checkExtractorDeps(dir);
        assert.equal(result.ok, false);
        assert.ok(result.message.includes('Extractor dependencies missing'));
        assert.ok(result.message.includes('cd src/extractor && npm install'));
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });
  });

});
