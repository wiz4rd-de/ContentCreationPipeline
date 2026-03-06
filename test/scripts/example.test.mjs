import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

// Determinism verification pattern:
// Run the same pure function twice with identical input,
// assert byte-identical output. This is the standard template
// for all pipeline tests in this project.

function reverseString(s) {
  return s.split('').reverse().join('');
}

describe('example determinism test', () => {
  it('produces identical output for identical input', () => {
    const input = 'deterministic pipeline';
    const run1 = reverseString(input);
    const run2 = reverseString(input);
    assert.equal(run1, run2, 'same input must produce identical output');
    assert.equal(run1, 'enilepip citsinimreted');
  });

  it('handles empty input', () => {
    assert.equal(reverseString(''), '');
  });
});
