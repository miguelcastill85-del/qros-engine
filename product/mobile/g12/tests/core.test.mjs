import {test} from 'node:test';
import assert from 'node:assert/strict';
import {canonical, sha, validDevice, validRequest, validOpaque} from '../worker/core.mjs';

test('canonical hashing is deterministic and validators are strict', async () => {
  const a = {b: 2, a: {y: false, x: 'z'}};
  const b = {a: {x: 'z', y: false}, b: 2};
  assert.equal(canonical(a), canonical(b));
  assert.equal(await sha(canonical(a)), await sha(canonical(b)));
  assert.equal(validDevice('device_' + 'A'.repeat(43)), true);
  assert.equal(validDevice('device_' + 'A'.repeat(42)), false);
  assert.equal(validRequest('req_' + 'B'.repeat(22)), true);
  assert.equal(validRequest('req_' + 'B'.repeat(21)), false);
  assert.equal(validOpaque('C'.repeat(43)), true);
  assert.equal(validOpaque('C'.repeat(42)), false);
});
