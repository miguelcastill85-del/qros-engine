import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {randomBytes, createHash} from 'node:crypto';
import {Miniflare} from 'miniflare';

const token = n => randomBytes(n).toString('base64url');
const digest = x => createHash('sha256').update(x).digest('hex');

test('workerd sessions rotate and synthetic jobs resume after runtime restart', async () => {
  const origin = 'https://g12.example';
  const now = Math.floor(Date.now() / 1000);
  const bootstrap = token(36);
  assert.equal(bootstrap.length, 48);
  const device = 'device_' + token(32);
  const requestId = 'req_' + token(16);
  const grant = {
    sha256: digest(bootstrap),
    tenant: 'tenant_A',
    project: 'project_A',
    campaign: 'campaign_A',
    scope: 'session:bootstrap',
    nbf: now - 1,
    exp: now + 299,
  };
  const bindings = {
    ENABLED: 'true',
    PUBLIC_ORIGIN: origin,
    TENANT: 'tenant_A',
    PROJECT: 'project_A',
    CAMPAIGN: 'campaign_A',
    BOOTSTRAP_GRANTS_JSON: JSON.stringify([grant]),
  };
  const dir = mkdtempSync(join(tmpdir(), 'qros-g12-do-'));
  const opts = {
    modules: true,
    scriptPath: resolve('product/mobile/g12/worker/index.mjs'),
    compatibilityDate: '2026-07-30',
    bindings,
    durableObjects: {SESSION_BROKER: {className: 'SessionBroker', useSQLite: true}},
    durableObjectsPersist: dir,
  };
  let mf = new Miniflare(opts);
  const post = (path, bearer, body, headers = {}) =>
    mf.dispatchFetch(origin + path, {
      method: 'POST',
      headers: {
        Authorization: 'Bearer ' + bearer,
        'Content-Type': 'application/json',
        ...headers,
      },
      body: body === undefined ? '{}' : JSON.stringify(body),
    });
  const get = (path, bearer, headers = {}) =>
    mf.dispatchFetch(origin + path, {
      headers: {Authorization: 'Bearer ' + bearer, ...headers},
    });

  try {
    let r = await post('/v1/session/bootstrap', bootstrap, {device_id: device});
    assert.equal(r.status, 200);
    const session = await r.json();
    assert.equal(session.schema, 'QROS_G12_SESSION_V1');
    assert.equal(session.scientific_authority, 'NONE');
    assert.equal(typeof session.client_id, 'string');
    assert.equal(session.access_token.length, 43);
    assert.equal(session.refresh_token.length, 43);

    r = await post('/v1/session/bootstrap', bootstrap, {device_id: device});
    assert.equal(r.status, 409);

    const spec = {
      request_id: requestId,
      search_space_sha256: '1'.repeat(64),
      toy_enumeration_sha256: '2'.repeat(64),
      raw_births: 144,
    };
    r = await post('/v1/jobs/synthetic', session.access_token, spec,
      {'X-QROS-Device': device});
    assert.equal(r.status, 201);
    let job = await r.json();
    assert.equal(job.state, 'PREPARED');
    assert.equal(job.economic_tests, 0);
    assert.equal(job.scientific_approval, false);

    r = await post('/v1/jobs/synthetic', session.access_token, spec,
      {'X-QROS-Device': device});
    assert.equal(r.status, 200);
    assert.equal((await r.json()).job_id, job.job_id);

    r = await post('/v1/jobs/synthetic/' + job.job_id + '/resume',
      session.access_token, undefined, {'X-QROS-Device': device});
    assert.equal(r.status, 200);
    job = await r.json();
    assert.equal(job.state, 'VALIDATED');

    await mf.dispose();
    mf = new Miniflare(opts);

    r = await get('/v1/jobs/synthetic/' + job.job_id, session.access_token,
      {'X-QROS-Device': device});
    assert.equal(r.status, 200);
    assert.equal((await r.json()).state, 'VALIDATED');

    r = await post('/v1/session/refresh', session.refresh_token, undefined,
      {'X-QROS-Device': device});
    assert.equal(r.status, 200);
    const rotated = await r.json();
    assert.notEqual(rotated.refresh_token, session.refresh_token);
    assert.notEqual(rotated.access_token, session.access_token);

    r = await post('/v1/session/refresh', session.refresh_token, undefined,
      {'X-QROS-Device': device});
    assert.equal(r.status, 401);

    r = await get('/v1/jobs/synthetic/' + job.job_id, session.access_token,
      {'X-QROS-Device': device});
    assert.equal(r.status, 401);

    for (const expected of ['CHECKPOINTED', 'COMPLETE']) {
      r = await post('/v1/jobs/synthetic/' + job.job_id + '/resume',
        rotated.access_token, undefined, {'X-QROS-Device': device});
      assert.equal(r.status, 200);
      job = await r.json();
      assert.equal(job.state, expected);
    }
    assert.equal(job.progress, 100);
    assert.equal(job.result.classification, 'TEST_ONLY_SYNTHETIC_INFRASTRUCTURE');
    assert.equal(job.result.economic_tests, 0);
    assert.equal(job.result.scientific_approval, false);
    assert.equal(job.result.holdout_open, false);
    assert.equal(job.result.ga2_open, false);
    assert.equal(job.result.mt5_executed, false);
    assert.equal(typeof job.result.result_sha256, 'string');
    assert.equal(job.result.result_sha256.length, 64);
    assert.equal(JSON.stringify(job).includes('pnl'), false);
  } finally {
    await mf.dispose();
    rmSync(dir, {recursive: true, force: true});
  }
});
