import test from 'node:test';
import assert from 'node:assert/strict';
import {bindProviderOrigin} from './origin_binding.mjs';

test('provider target must equal independently pinned product source before deployment', () => {
  const origin='https://qros-mobile-g12-test-only.expected.workers.dev';
  const source=`static const trustedOrigin =\n '${origin}';`;
  assert.equal(bindProviderOrigin(origin,source),origin);
  assert.throws(()=>bindProviderOrigin('https://qros-mobile-g12-test-only.other.workers.dev',source));
  assert.throws(()=>bindProviderOrigin(origin,'// no independently pinned product origin'));
  assert.throws(()=>bindProviderOrigin('http://qros-mobile-g12-test-only.expected.workers.dev',source));
});
