import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {randomBytes, createHash} from 'node:crypto';
import {mkdtempSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';

// Use only the already pinned G12 dependency, never a different test runtime.
const require = createRequire(resolve('product/mobile/g12/package.json'));
const {Miniflare} = require('miniflare');
const opaque = n => randomBytes(n).toString('base64url');
const digest = x => createHash('sha256').update(x).digest('hex');
const origin = 'https://g12.example';

async function fixture() {
  const now = Math.floor(Date.now() / 1000);
  const bootstrap = opaque(36), device = 'device_' + opaque(32);
  const grant = {sha256: digest(bootstrap), tenant: 'tenant_A',
    project: 'project_A', campaign: 'campaign_A', scope: 'session:bootstrap',
    nbf: now - 1, exp: now + 299};
  const dir = mkdtempSync(join(tmpdir(), 'qros-g12-auth-boundary-'));
  const options = {modules: true,
    scriptPath: resolve('product/mobile/g12/worker/index.mjs'),
    compatibilityDate: '2026-07-30',
    bindings: {ENABLED: 'true', PUBLIC_ORIGIN: origin, TENANT: 'tenant_A',
      PROJECT: 'project_A', CAMPAIGN: 'campaign_A',
      BOOTSTRAP_GRANTS_JSON: JSON.stringify([grant])},
    durableObjects: {SESSION_BROKER: {className: 'SessionBroker', useSQLite: true}},
    durableObjectsPersist: dir};
  let mf = new Miniflare(options);
  const post = (path, bearer, body = {}) => mf.dispatchFetch(origin + path, {
    method: 'POST', headers: {'Content-Type': 'application/json',
      Authorization: 'Bearer ' + bearer, 'X-QROS-Device': device},
    body: JSON.stringify(body)});
  const initial = await post('/v1/session/bootstrap', bootstrap, {device_id: device});
  assert.equal(initial.status, 200);
  const session = await initial.json();
  const spec = {request_id: 'req_' + opaque(16), search_space_sha256: '1'.repeat(64),
    toy_enumeration_sha256: '2'.repeat(64), raw_births: 144};
  const created = await post('/v1/jobs/synthetic', session.access_token, spec);
  assert.equal(created.status, 201);
  const job = await created.json();
  const stub = async () => {
    const ns = await mf.getDurableObjectNamespace('SESSION_BROKER');
    return ns.get(ns.idFromName('g12-session-broker-v1'));
  };
  return {session, job, device, post, stub,
    get: () => mf.dispatchFetch(origin + '/v1/jobs/synthetic/' + job.job_id,
      {headers: {Authorization: 'Bearer ' + session.access_token, 'X-QROS-Device': device}}),
    restart: async (scope = {}) => {
      await mf.dispose();
      mf = new Miniflare({...options, bindings: {...options.bindings, ...scope}});
    },
    close: async () => { await mf.dispose(); rmSync(dir, {recursive: true, force: true}); }};
}

test('access expiry is exclusive and does not prevent still-valid refresh', async () => {
  const f = await fixture();
  try {
    const b = await f.stub(), hash = digest(f.session.access_token);
    const limit = f.session.access_expires_at;
    assert.equal((await b.getJob(hash, f.device, f.job.job_id, limit - 1)).status, 200);
    assert.equal((await b.getJob(hash, f.device, f.job.job_id, limit)).status, 401);
    assert.equal((await b.resumeJob(hash, f.device, f.job.job_id, limit)).status, 401);
    assert.equal((await b.refresh(digest(f.session.refresh_token), f.device, limit)).status, 200);
  } finally { await f.close(); }
});

test('refresh expiry is exclusive; last valid rotation rejects both previous tokens', async () => {
  const f = await fixture();
  try {
    const b = await f.stub(), hash = digest(f.session.refresh_token);
    const limit = f.session.refresh_expires_at;
    assert.equal((await b.refresh(hash, f.device, limit)).status, 401);
    const rotated = await b.refresh(hash, f.device, limit - 1);
    assert.equal(rotated.status, 200);
    assert.equal((await b.refresh(hash, f.device, limit - 1)).status, 401);
    assert.equal((await b.getJob(digest(f.session.access_token),
      f.device, f.job.job_id, limit - 1)).status, 401);
    assert.equal((await b.getJob(digest(rotated.payload.access_token),
      f.device, f.job.job_id, limit - 1)).status, 200);
  } finally { await f.close(); }
});

for (const key of ['TENANT', 'PROJECT', 'CAMPAIGN']) {
  test('durable session rejects changed ' + key + ' after restart and preserves original job', async () => {
    const f = await fixture();
    try {
      await f.restart({[key]: 'cross_scope'});
      const b = await f.stub();
      const now = f.session.access_expires_at - 1;
      assert.equal((await b.getJob(digest(f.session.access_token), f.device, f.job.job_id, now)).status, 401);
      assert.equal((await b.refresh(digest(f.session.refresh_token), f.device, now)).status, 401);
      await f.restart();
      const original = await (await f.stub()).getJob(digest(f.session.access_token),
        f.device, f.job.job_id, now);
      assert.equal(original.status, 200);
      assert.deepEqual(original.payload, f.job);
    } finally { await f.close(); }
  });
}

test('authenticated GET is read-only; only explicit POST advances one phase', async () => {
  const f = await fixture();
  try {
    for (let i = 0; i < 3; i++) {
      const r = await f.get();
      assert.equal(r.status, 200);
      assert.deepEqual(await r.json(), f.job);
    }
    const advance = await f.post('/v1/jobs/synthetic/' + f.job.job_id + '/resume',
      f.session.access_token);
    assert.equal(advance.status, 200);
    const job = await advance.json();
    assert.equal(job.phase, 1);
    assert.equal(job.state, 'VALIDATED');
    const read = await f.get();
    assert.deepEqual(await read.json(), job);
    const serialized = JSON.stringify(job);
    for (const secret of [f.session.access_token, f.session.refresh_token]) {
      assert.equal(serialized.includes(secret), false);
    }
    assert.equal(job.scientific_approval, false);
    assert.equal(job.economic_tests, 0);
  } finally { await f.close(); }
});
