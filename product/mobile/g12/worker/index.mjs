import {DurableObject} from 'cloudflare:workers';
import {handle, canonical, sha, validDevice} from './core.mjs';

function token() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes)).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');
}

function clientId() {
  return 'client_' + crypto.randomUUID();
}

function jobId() {
  return crypto.randomUUID();
}

export class SessionBroker extends DurableObject {
  async _auth(storage, accessHash, deviceId, now) {
    const cid = await storage.get('access:' + accessHash);
    if (!cid) return null;
    const session = await storage.get('session:' + cid);
    if (!session || session.revoked || session.device_id !== deviceId ||
        !Number.isSafeInteger(session.access_exp) || now >= session.access_exp) return null;
    return {cid, session};
  }

  async bootstrap(grantHash, grant, deviceId, now) {
    if (!validDevice(deviceId)) return {status: 400};
    return this.ctx.storage.transaction(async tx => {
      if (await tx.get('used:' + grantHash)) return {status: 409};
      const cid = clientId();
      const access = token();
      const refresh = token();
      const accessHash = await sha(access);
      const refreshHash = await sha(refresh);
      const session = {
        tenant: grant.tenant, project: grant.project, campaign: grant.campaign,
        device_id: deviceId, access_hash: accessHash, access_exp: now + 900,
        refresh_hash: refreshHash, refresh_exp: now + 2592000, revoked: false,
      };
      await tx.put('used:' + grantHash, grant.exp);
      await tx.put('session:' + cid, session);
      await tx.put('access:' + accessHash, cid);
      await tx.put('refresh:' + refreshHash, cid);
      return {status: 200, payload: {
        schema: 'QROS_G12_SESSION_V1', client_id: cid,
        access_token: access, access_expires_at: session.access_exp,
        refresh_token: refresh, refresh_expires_at: session.refresh_exp,
        scope: 'synthetic:jobs', scientific_authority: 'NONE',
      }};
    });
  }

  async refresh(refreshHash, deviceId, now) {
    return this.ctx.storage.transaction(async tx => {
      const cid = await tx.get('refresh:' + refreshHash);
      if (!cid) return {status: 401};
      const session = await tx.get('session:' + cid);
      if (!session || session.revoked || session.device_id !== deviceId ||
          session.refresh_hash !== refreshHash || now >= session.refresh_exp) return {status: 401};
      const access = token();
      const refresh = token();
      const nextAccessHash = await sha(access);
      const nextRefreshHash = await sha(refresh);
      await tx.delete('access:' + session.access_hash);
      await tx.delete('refresh:' + refreshHash);
      session.access_hash = nextAccessHash;
      session.access_exp = now + 900;
      session.refresh_hash = nextRefreshHash;
      session.refresh_exp = now + 2592000;
      await tx.put('session:' + cid, session);
      await tx.put('access:' + nextAccessHash, cid);
      await tx.put('refresh:' + nextRefreshHash, cid);
      return {status: 200, payload: {
        schema: 'QROS_G12_SESSION_V1', client_id: cid,
        access_token: access, access_expires_at: session.access_exp,
        refresh_token: refresh, refresh_expires_at: session.refresh_exp,
        scope: 'synthetic:jobs', scientific_authority: 'NONE',
      }};
    });
  }

  async revoke(refreshHash, deviceId, now) {
    return this.ctx.storage.transaction(async tx => {
      const cid = await tx.get('refresh:' + refreshHash);
      if (!cid) return 401;
      const session = await tx.get('session:' + cid);
      if (!session || session.device_id !== deviceId || session.refresh_hash !== refreshHash) return 401;
      session.revoked = true;
      session.revoked_at = now;
      await tx.delete('access:' + session.access_hash);
      await tx.delete('refresh:' + refreshHash);
      await tx.put('session:' + cid, session);
      return 204;
    });
  }

  async createJob(accessHash, deviceId, body, now) {
    return this.ctx.storage.transaction(async tx => {
      const auth = await this._auth(tx, accessHash, deviceId, now);
      if (!auth) return {status: 401};
      const requestKey = 'request:' + auth.cid + ':' + body.request_id;
      const existing = await tx.get(requestKey);
      if (existing) {
        const job = await tx.get('job:' + existing);
        return job ? {status: 200, payload: job} : {status: 503};
      }
      const id = jobId();
      const job = {
        schema: 'QROS_G12_SYNTHETIC_JOB_V1',
        job_id: id,
        client_id: auth.cid,
        request_id: body.request_id,
        state: 'PREPARED',
        phase: 0,
        progress: 0,
        created_at: now,
        updated_at: now,
        input: {
          search_space_sha256: body.search_space_sha256,
          toy_enumeration_sha256: body.toy_enumeration_sha256,
          raw_births: body.raw_births,
        },
        result: null,
        economic_tests: 0,
        scientific_approval: false,
        holdout_open: false,
        ga2_open: false,
        mt5_executed: false,
      };
      await tx.put(requestKey, id);
      await tx.put('job:' + id, job);
      return {status: 201, payload: job};
    });
  }

  async getJob(accessHash, deviceId, id, now) {
    const auth = await this._auth(this.ctx.storage, accessHash, deviceId, now);
    if (!auth) return {status: 401};
    const job = await this.ctx.storage.get('job:' + id);
    if (!job || job.client_id !== auth.cid) return {status: 404};
    return {status: 200, payload: job};
  }

  async resumeJob(accessHash, deviceId, id, now) {
    return this.ctx.storage.transaction(async tx => {
      const auth = await this._auth(tx, accessHash, deviceId, now);
      if (!auth) return {status: 401};
      const job = await tx.get('job:' + id);
      if (!job || job.client_id !== auth.cid) return {status: 404};
      if (job.state === 'COMPLETE') return {status: 200, payload: job};
      job.phase += 1;
      job.updated_at = now;
      if (job.phase === 1) {
        job.state = 'VALIDATED';
        job.progress = 34;
      } else if (job.phase === 2) {
        job.state = 'CHECKPOINTED';
        job.progress = 67;
      } else {
        job.phase = 3;
        job.state = 'COMPLETE';
        job.progress = 100;
        const body = {
          schema: 'QROS_G12_SYNTHETIC_JOB_RESULT_V1',
          classification: 'TEST_ONLY_SYNTHETIC_INFRASTRUCTURE',
          job_id: job.job_id,
          search_space_sha256: job.input.search_space_sha256,
          toy_enumeration_sha256: job.input.toy_enumeration_sha256,
          raw_births: job.input.raw_births,
          work_units_completed: 3,
          economic_tests: 0,
          scientific_approval: false,
          holdout_open: false,
          ga2_open: false,
          mt5_executed: false,
        };
        job.result = {...body, result_sha256: await sha(canonical(body))};
      }
      await tx.put('job:' + id, job);
      return {status: 200, payload: job};
    });
  }
}

export default {
  async fetch(req, env) {
    return handle(req, env);
  },
};
