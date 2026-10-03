import {test} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {randomBytes, createHash} from 'node:crypto';
import {Miniflare} from 'miniflare';
import {readJson} from '../worker/core.mjs';

const token = n => randomBytes(n).toString('base64url');
const digest = s => createHash('sha256').update(s).digest('hex');
const origin = 'https://g12.example';

async function fixture(count = 1) {
  const now = Math.floor(Date.now() / 1000);
  const bootstraps = Array.from({length: count}, () => token(36));
  const grants = bootstraps.map(t => ({
    sha256: digest(t), tenant: 'tenant_A', project: 'project_A', campaign: 'campaign_A',
    scope: 'session:bootstrap', nbf: now - 1, exp: now + 299,
  }));
  const mf = new Miniflare({
    modules: true, scriptPath: resolve('product/mobile/g12/worker/index.mjs'),
    compatibilityDate: '2026-07-30',
    bindings: {
      ENABLED: 'true', PUBLIC_ORIGIN: origin, TENANT: 'tenant_A',
      PROJECT: 'project_A', CAMPAIGN: 'campaign_A',
      BOOTSTRAP_GRANTS_JSON: JSON.stringify(grants),
    },
    durableObjects: {SESSION_BROKER: {className: 'SessionBroker', useSQLite: true}},
  });
  const device = 'device_' + token(32);
  const post = (path, bearer, body = {}, extra = {}) => mf.dispatchFetch(origin + path, {
    method: 'POST', headers: {'Content-Type': 'application/json',
      Authorization: 'Bearer ' + bearer, 'X-QROS-Device': device, ...extra},
    body: JSON.stringify(body),
  });
  const enroll = i => post('/v1/session/bootstrap', bootstraps[i], {device_id: device});
  const spec = () => ({
    request_id: 'req_' + token(16), search_space_sha256: '1'.repeat(64),
    toy_enumeration_sha256: '2'.repeat(64), raw_births: 144,
  });
  return {mf, post, enroll, spec, device};
}

test('body is bounded by bytes before JSON parsing and rejects invalid UTF-8', async () => {
  const request = body => new Request(origin, {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body});
  await assert.rejects(readJson(request(JSON.stringify({x: 'é'.repeat(9000)}))), /too_large/);
  await assert.rejects(readJson(request(new Uint8Array([0xff]))));
  assert.deepEqual(await readJson(request('{"x":1}')), {x: 1});
  let cancelled = false;
  const body = new ReadableStream({
    pull(c) { c.enqueue(new Uint8Array(8192)); },
    cancel() { cancelled = true; },
  });
  const stream = new Request(origin, {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body, duplex: 'half'});
  await assert.rejects(readJson(stream), /too_large/);
  assert.equal(cancelled, true);
});

test('workerd rejects idempotency conflicts, wrong devices, CORS and query tokens', async () => {
  const f = await fixture(2);
  try {
    const s = await (await f.enroll(0)).json();
    const input = f.spec();
    const first = await f.post('/v1/jobs/synthetic', s.access_token, input);
    assert.equal(first.status, 201);
    const job = await first.json();
    assert.equal((await f.post('/v1/jobs/synthetic', s.access_token,
      {...input, raw_births: 145})).status, 409);
    assert.equal((await f.post('/v1/jobs/synthetic', s.access_token, input,
      {'X-QROS-Device': 'device_' + token(32)})).status, 401);
    const cors = await f.post('/v1/jobs/synthetic', s.access_token, input, {Origin: 'https://evil.example'});
    assert.equal(cors.status, 403);
    assert.equal(cors.headers.has('Access-Control-Allow-Origin'), false);
    assert.equal((await f.post('/v1/jobs/synthetic?token=x', s.access_token, input)).status, 403);
    const second = await (await f.enroll(1)).json();
    assert.equal((await f.post('/v1/jobs/synthetic/' + job.job_id + '/resume',
      second.access_token)).status, 404);
    const rotated = await Promise.all([
      f.post('/v1/session/refresh', s.refresh_token),
      f.post('/v1/session/refresh', s.refresh_token),
    ]);
    assert.deepEqual(rotated.map(r => r.status).sort(), [200, 401]);
  } finally { await f.mf.dispose(); }
});

test('workerd enforces atomic per-client job budget and permits exact retry at capacity', async () => {
  const f = await fixture();
  try {
    const s = await (await f.enroll(0)).json();
    const input = f.spec();
    const first = await f.post('/v1/jobs/synthetic', s.access_token, input);
    assert.equal(first.status, 201);
    const id = (await first.json()).job_id;
    const responses = await Promise.all(Array.from({length: 25}, () =>
      f.post('/v1/jobs/synthetic', s.access_token, f.spec())));
    assert.equal(responses.filter(r => r.status === 201).length, 19);
    assert.equal(responses.filter(r => r.status === 429).length, 6);
    const retry = await f.post('/v1/jobs/synthetic', s.access_token, input);
    assert.equal(retry.status, 200);
    assert.equal((await retry.json()).job_id, id);
  } finally { await f.mf.dispose(); }
});

test('workerd bounds issued sessions even under concurrent bootstrap requests', async () => {
  const f = await fixture(25);
  try {
    const results = await Promise.all(Array.from({length: 25}, (_, i) => f.enroll(i)));
    assert.equal(results.filter(r => r.status === 200).length, 20);
    assert.equal(results.filter(r => r.status === 429).length, 5);
  } finally { await f.mf.dispose(); }
});

test('workerd persists request budget and denies overflow without permissive CORS', async () => {
  const f = await fixture();
  try {
    const ns = await f.mf.getDurableObjectNamespace('SESSION_BROKER');
    const stub = ns.get(ns.idFromName('g12-session-broker-v1'));
    const fixed = 1800000000;
    const results = await Promise.all(Array.from({length: 205}, () => stub.admit(fixed)));
    assert.equal(results.filter(Boolean).length, 200);
    assert.equal(await stub.admit(fixed), false);
    assert.equal(await stub.admit(fixed + 60), true);
    for (let minute = 1; minute < 50; minute++) {
      const batch = await Promise.all(Array.from({length: minute === 1 ? 199 : 200},
        () => stub.admit(fixed + minute * 60)));
      assert.equal(batch.every(Boolean), true);
    }
    assert.equal(await stub.admit(fixed + 50 * 60), false);
    assert.equal(await stub.admit(fixed + 86400), true);
  } finally { await f.mf.dispose(); }
});
