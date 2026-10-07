import {test} from 'node:test';
import assert from 'node:assert/strict';
import {inspectProvider} from './provider_preflight.mjs';

const credentials = {accountId: 'a'.repeat(32), apiToken: 'SENSITIVE_TOKEN_FIXTURE', freeReported: 'true'};
const reply = (status, result, errors=[]) => new Response(JSON.stringify({success: status===200, result, errors}), {status});

test('missing credentials never contact the provider', async () => {
  const r = await inspectProvider({fetcher: () => {throw Error('must not call');}});
  assert.equal(r.reason, 'MISSING_PROVIDER_CONFIGURATION');
});
test('API rejection emits only numeric error codes and never tokens or provider messages', async () => {
  const r = await inspectProvider({...credentials, fetcher: async () => reply(403, null, [{code: 10000, message: credentials.apiToken}])});
  assert.equal(r.reason, 'PROVIDER_ACCESS_NOT_ESTABLISHED');
  assert.deepEqual(r.checks[0].error_codes, [10000]);
  assert(!JSON.stringify(r).includes(credentials.apiToken));
  assert(!JSON.stringify(r).includes(credentials.accountId));
});
test('network failure and hostile subdomain fail closed', async () => {
  for (const fetcher of [async () => {throw Error(credentials.apiToken);}, async () => reply(200, {subdomain: 'host.example/path?token'})]) {
    const r = await inspectProvider({...credentials, fetcher});
    assert.equal(r.provider_access, 'NOT_CHECKED');
    assert.equal(r.deployment, 'NOT_ATTEMPTED');
  }
});
test('successful read remains deployment-gated; usage model never certifies Free plan', async () => {
  const calls=[];
  const r = await inspectProvider({...credentials, fetcher: async (url, options) => {
    calls.push({url, options});
    if(url.endsWith('/workers/subdomain')) return reply(200, {subdomain:'test-account'});
    if(url.endsWith('/workers/account-settings')) return reply(200, {default_usage_model:'standard'});
    return reply(404,null);
  }});
  assert.equal(r.provider_access, 'VERIFICADO');
  assert.equal(r.public_origin, 'https://qros-mobile-g12-test-only.test-account.workers.dev');
  assert.equal(r.free_plan, 'REPORTADO_EXISTING_GITHUB_GATE');
  assert.equal(r.existing_g12, 'NOT_ESTABLISHED');
  assert(calls.every(c => !c.options.method && c.options.redirect==='error'));
  assert.equal(r.deployment, 'NOT_ATTEMPTED');
});
test('paid, unknown or truncated subscriptions block deployment while an empty authenticated list permits the prior Free gate', async () => {
  for(const subscriptions of [[], [{rate_plan:{id:'workers_paid'}}], Array.from({length:50},()=>({})), null]) {
    const r = await inspectProvider({...credentials, fetcher: async url => {
      if(url.endsWith('/workers/subdomain')) return reply(200,{subdomain:'test-account'});
      if(url.includes('/subscriptions?')) return subscriptions===null ? reply(403,null) : reply(200,subscriptions);
      return reply(404,null);
    }});
    assert.equal(r.status==='READY_FOR_REVIEWED_FREE_DEPLOYMENT', Array.isArray(subscriptions) && subscriptions.length===0);
  }
});
