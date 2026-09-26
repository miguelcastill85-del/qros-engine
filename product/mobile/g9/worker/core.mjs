// G9 TEST_ONLY. No OIDC or independent custody claim. No input controls signed data.
export const encoder = new TextEncoder();
export function canonical(o) {
  if(o === null || typeof o === 'boolean' || typeof o === 'string') return JSON.stringify(o);
  if(typeof o === 'number' && Number.isSafeInteger(o)) return String(o);
  if(Array.isArray(o)) return '['+o.map(canonical).join(',')+']';
  if(o && Object.getPrototypeOf(o) === Object.prototype) return '{'+Object.keys(o).sort().map(k=>JSON.stringify(k)+':'+canonical(o[k])).join(',')+'}';
  throw new Error('invalid_canonical_type');
}
export async function sha(data) {return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', typeof data==='string'?encoder.encode(data):data)),x=>x.toString(16).padStart(2,'0')).join('');}
export function b64(bytes) {return btoa(String.fromCharCode(...new Uint8Array(bytes)));}
export function unb64(s) {if(typeof s!=='string'||s.length>256)throw Error('encoding'); const b=Uint8Array.from(atob(s),x=>x.charCodeAt(0));if(b64(b)!==s)throw Error('encoding');return b;}
export function response(status, data) {return new Response(canonical(data),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store, max-age=0','Pragma':'no-cache','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'"}});}
const ident=x=>typeof x==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$/.test(x);
const exact=(o,keys)=>o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).sort().join(',')===keys.slice().sort().join(',');
export async function authorize(req, env, now) {
  const url=new URL(req.url);
  if(url.protocol!=='https:'||url.origin!==env.PUBLIC_ORIGIN)return {status:403};
  if(req.method!=='GET')return {status:405};
  if(url.pathname!=='/v1/demo-snapshot'||url.search||url.hash)return {status:404};
  if(req.headers.has('Origin'))return {status:403};
  const auth=req.headers.get('Authorization')||'';
  if(!/^Bearer [A-Za-z0-9_-]{43,128}$/.test(auth))return {status:401};
  const grants=JSON.parse(env.TOKEN_GRANTS_JSON);
  if(!Array.isArray(grants)||grants.length>100)throw Error('registry');
  const hash=await sha(auth.slice(7));
  for(const g of grants){
    if(!exact(g,['sha256','tenant','project','campaign','scope','nbf','exp'])||!/^([0-9a-f]{64})$/.test(g.sha256)||
      ![g.tenant,g.project,g.campaign].every(ident)||g.scope!=='demo:read'||
      !Number.isSafeInteger(g.nbf)||!Number.isSafeInteger(g.exp)||g.exp<=g.nbf||g.exp-g.nbf>300)throw Error('registry');
  }
  const found=grants.filter(g=>g.sha256===hash);
  if(found.length!==1)return {status:401};
  const g=found[0];
  if(!(g.nbf<=now&&now<g.exp))return {status:401};
  if(req.headers.get('X-QROS-Project')!==g.project)return {status:403};
  // Explicit headers optional for the frozen G6 transport; bearer binds all three.
  for(const [h,k] of [['X-QROS-Tenant','tenant'],['X-QROS-Campaign','campaign']])if(req.headers.has(h)&&req.headers.get(h)!==g[k])return {status:403};
  if(g.tenant!==env.TENANT||g.project!==env.PROJECT||g.campaign!==env.CAMPAIGN)return {status:403};
  return {status:200,grant:g,hash};
}
export async function snapshot(env) {
  // Immutable synthetic two-row fixture; never accept tenant-supplied audit bytes.
  const audit={schema:'QROS_G4_DATA_AUDIT_TEST_RECEIPT_V1',classification:'TEST_ONLY_NO_SCIENTIFIC_AUTHORITY',
    tenant:env.TENANT,source_id:'g9_synthetic',source_sha256:await sha('G9_SYNTHETIC_SOURCE\n'),license_id:'synthetic_test',
    source_class:'SYNTHETIC_ONLY',broker_timezone:'TEST_ONLY_NO_BROKER_CLOCK',rows:2,
    diagnostics:{zero_spread_preserved:0,crossed_spread_preserved:0,large_gaps:0,session_transitions:0,invalid_execution_quotes:0},
    execution_eligible:true,imputation:'NONE',economic_tests:0,holdout_open:false,ga2_open:false,audit_spec_sha256:await sha('G9_SYNTHETIC_SPEC')};
  if(![env.TENANT,env.PROJECT,env.CAMPAIGN,env.WITNESS_ID].every(ident))throw Error('config');
  if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(env.SNAPSHOT_CREATED_UTC)||!Number.isFinite(Date.parse(env.SNAPSHOT_CREATED_UTC)))throw Error('time');
  const body={schema:'QROS_G4_WITNESS_TEST_V1',witness_id:env.WITNESS_ID,sequence:1,previous_sha256:'0'.repeat(64),tenant:env.TENANT,
    campaign:env.CAMPAIGN,subject_sha256:await sha(canonical(audit)),created_utc:env.SNAPSHOT_CREATED_UTC,classification:'TEST_ONLY_SYNTHETIC'};
  const key=await crypto.subtle.importKey('pkcs8',unb64(env.SIGNING_PKCS8_B64),{name:'Ed25519'},false,['sign']);
  const signature=await crypto.subtle.sign('Ed25519',key,encoder.encode(canonical(body)));
  const pub=unb64(env.SIGNING_PUBLIC_B64);
  // Explicitly reject the published G6 test root; it has a public deterministic seed.
  if(pub.length!==32||env.SIGNING_PUBLIC_B64==='QwRr/kCSs+lJlOraFdzCDYqqB7ZY/TlU644O+4vcpd4=')throw Error('unsafe_root');
  const verifyKey=await crypto.subtle.importKey('raw',pub,{name:'Ed25519'},false,['verify']);
  if(!await crypto.subtle.verify('Ed25519',verifyKey,signature,encoder.encode(canonical(body))))throw Error('key_mismatch');
  return {schema:'QROS_G5_SIGNED_SYNTHETIC_SNAPSHOT_V1',source_class:'SYNTHETIC_ONLY',scientific_approval:false,
    tenant:env.TENANT,project:env.PROJECT,campaign:env.CAMPAIGN,audit_receipt:audit,witness_event:{body,signature_b64:b64(signature)},
    head:{sequence:1,sha256:await sha(canonical(body))},external_independent_custody:'NOT_DEPLOYED',economic_backtests:0,holdout_open:false,ga2_open:false};
}
export async function handle(req,env,consume,now=Math.floor(Date.now()/1000)) {
  try {
    if(env.ENABLED!=='true')return response(503,{error:'unavailable'});
    const a=await authorize(req,env,now);
    if(a.status!==200)return response(a.status,{error:'request_denied'});
    const payload=await snapshot(env);
    // Consume atomically BEFORE release. Lost response consumes token: fail closed.
    const status=await consume(a.hash,a.grant,now);
    if(status!==200)return response(status===409?409:status===429?429:503,{error:'request_denied'});
    return response(200,payload);
  } catch {return response(503,{error:'unavailable'});}
}
