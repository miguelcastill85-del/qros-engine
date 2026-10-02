// G12 TEST_ONLY. Device-bound renewable sessions and resumable synthetic jobs.
// No scientific transitions, PnL, broker data, MT5 or trading actions.
export const encoder = new TextEncoder();

export function canonical(o) {
  if (o === null || typeof o === 'boolean' || typeof o === 'string') return JSON.stringify(o);
  if (typeof o === 'number' && Number.isSafeInteger(o)) return String(o);
  if (Array.isArray(o)) return '[' + o.map(canonical).join(',') + ']';
  if (o && Object.getPrototypeOf(o) === Object.prototype) {
    return '{' + Object.keys(o).sort().map(k => JSON.stringify(k) + ':' + canonical(o[k])).join(',') + '}';
  }
  throw new Error('invalid_canonical_type');
}

export async function sha(data) {
  const bytes = typeof data === 'string' ? encoder.encode(data) : data;
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
    x => x.toString(16).padStart(2, '0')).join('');
}

export function response(status, data) {
  return new Response(canonical(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store, max-age=0',
      'Pragma': 'no-cache',
      'X-Content-Type-Options': 'nosniff',
      'Content-Security-Policy': "default-src 'none'",
    },
  });
}

export const validIdent = x =>
  typeof x === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$/.test(x);
export const validHex = x => typeof x === 'string' && /^[0-9a-f]{64}$/.test(x);
export const validDevice = x => typeof x === 'string' && /^device_[A-Za-z0-9_-]{43}$/.test(x);
export const validRequest = x => typeof x === 'string' && /^req_[A-Za-z0-9_-]{22}$/.test(x);
export const validOpaque = x => typeof x === 'string' && /^[A-Za-z0-9_-]{43}$/.test(x);

export function exact(o, keys) {
  return o && typeof o === 'object' && !Array.isArray(o) &&
    Object.keys(o).sort().join(',') === keys.slice().sort().join(',');
}

async function readJson(req, max = 16384) {
  const type = (req.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
  if (type !== 'application/json') throw new Error('content_type');
  const length = Number(req.headers.get('Content-Length') || '0');
  if (Number.isFinite(length) && length > max) throw new Error('too_large');
  const text = await req.text();
  if (text.length > max) throw new Error('too_large');
  const parsed = JSON.parse(text);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('json_object');
  return parsed;
}

function bearer(req) {
  const value = req.headers.get('Authorization') || '';
  if (!/^Bearer [A-Za-z0-9_-]{43,128}$/.test(value)) return null;
  return value.slice(7);
}

function baseRequest(req, env) {
  const url = new URL(req.url);
  if (url.protocol !== 'https:' || url.origin !== env.PUBLIC_ORIGIN) return {status: 403};
  if (req.headers.has('Origin')) return {status: 403};
  return {status: 200, url};
}

async function bootstrapGrant(req, env, now) {
  const token = bearer(req);
  if (!token || token.length !== 48) return {status: 401};
  const registry = JSON.parse(env.BOOTSTRAP_GRANTS_JSON || '[]');
  if (!Array.isArray(registry) || registry.length > 100) throw new Error('registry');
  for (const g of registry) {
    if (!exact(g, ['sha256','tenant','project','campaign','scope','nbf','exp']) ||
        !validHex(g.sha256) || ![g.tenant,g.project,g.campaign].every(validIdent) ||
        g.scope !== 'session:bootstrap' || !Number.isSafeInteger(g.nbf) ||
        !Number.isSafeInteger(g.exp) || g.exp <= g.nbf || g.exp - g.nbf > 300) {
      throw new Error('registry');
    }
  }
  const hash = await sha(token);
  const found = registry.filter(g => g.sha256 === hash);
  if (found.length !== 1) return {status: 401};
  const grant = found[0];
  if (!(grant.nbf <= now && now < grant.exp)) return {status: 401};
  if (grant.tenant !== env.TENANT || grant.project !== env.PROJECT ||
      grant.campaign !== env.CAMPAIGN) return {status: 403};
  return {status: 200, grant, hash};
}

function broker(env) {
  return env.SESSION_BROKER.get(env.SESSION_BROKER.idFromName('g12-session-broker-v1'));
}

export async function handle(req, env, now = Math.floor(Date.now() / 1000)) {
  try {
    if (env.ENABLED !== 'true') return response(503, {error: 'unavailable'});
    const base = baseRequest(req, env);
    if (base.status !== 200) return response(base.status, {error: 'request_denied'});
    const url = base.url;
    const b = broker(env);

    if (url.pathname === '/v1/session/bootstrap' && req.method === 'POST') {
      const auth = await bootstrapGrant(req, env, now);
      if (auth.status !== 200) return response(auth.status, {error: 'request_denied'});
      const body = await readJson(req);
      if (!exact(body, ['device_id']) || !validDevice(body.device_id)) {
        return response(400, {error: 'invalid_request'});
      }
      const out = await b.bootstrap(auth.hash, auth.grant, body.device_id, now);
      return response(out.status, out.status === 200 ? out.payload : {error: 'request_denied'});
    }

    if (url.pathname === '/v1/session/refresh' && req.method === 'POST') {
      const token = bearer(req);
      const deviceId = req.headers.get('X-QROS-Device');
      if (!validOpaque(token) || !validDevice(deviceId)) return response(401, {error: 'request_denied'});
      const out = await b.refresh(await sha(token), deviceId, now);
      return response(out.status, out.status === 200 ? out.payload : {error: 'request_denied'});
    }

    if (url.pathname === '/v1/session/revoke' && req.method === 'POST') {
      const token = bearer(req);
      const deviceId = req.headers.get('X-QROS-Device');
      if (!validOpaque(token) || !validDevice(deviceId)) return response(401, {error: 'request_denied'});
      const status = await b.revoke(await sha(token), deviceId, now);
      return response(status, status === 200 ? {status: 'revoked'} : {error: 'request_denied'});
    }

    if (url.pathname === '/v1/jobs/synthetic' && req.method === 'POST') {
      const token = bearer(req);
      const deviceId = req.headers.get('X-QROS-Device');
      if (!validOpaque(token) || !validDevice(deviceId)) return response(401, {error: 'request_denied'});
      const body = await readJson(req);
      if (!exact(body, ['request_id','search_space_sha256','toy_enumeration_sha256','raw_births']) ||
          !validRequest(body.request_id) || !validHex(body.search_space_sha256) ||
          !validHex(body.toy_enumeration_sha256) || !Number.isSafeInteger(body.raw_births) ||
          body.raw_births < 1 || body.raw_births > 10000) {
        return response(400, {error: 'invalid_request'});
      }
      const out = await b.createJob(await sha(token), deviceId, body, now);
      return response(out.status, out.status === 200 || out.status === 201 ? out.payload : {error: 'request_denied'});
    }

    const jobMatch = url.pathname.match(/^\/v1\/jobs\/synthetic\/([A-Za-z0-9_-]{36})$/);
    if (jobMatch && req.method === 'GET') {
      const token = bearer(req);
      const deviceId = req.headers.get('X-QROS-Device');
      if (!validOpaque(token) || !validDevice(deviceId)) return response(401, {error: 'request_denied'});
      const out = await b.getJob(await sha(token), deviceId, jobMatch[1], now);
      return response(out.status, out.status === 200 ? out.payload : {error: 'request_denied'});
    }

    const resumeMatch = url.pathname.match(/^\/v1\/jobs\/synthetic\/([A-Za-z0-9_-]{36})\/resume$/);
    if (resumeMatch && req.method === 'POST') {
      const token = bearer(req);
      const deviceId = req.headers.get('X-QROS-Device');
      if (!validOpaque(token) || !validDevice(deviceId)) return response(401, {error: 'request_denied'});
      const out = await b.resumeJob(await sha(token), deviceId, resumeMatch[1], now);
      return response(out.status, out.status === 200 ? out.payload : {error: 'request_denied'});
    }

    return response(404, {error: 'not_found'});
  } catch {
    return response(503, {error: 'unavailable'});
  }
}
