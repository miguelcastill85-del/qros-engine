// One bounded integration test. Bearers stay in memory; only hashes reach backend.
import {randomBytes,createHash,createPublicKey,verify} from 'node:crypto';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {canonical} from '../worker/core.mjs';
const root=JSON.parse(readFileSync(new URL('../receipts/PUBLIC_ROOT_20260928.json',import.meta.url)));
const origin=root.origin;
const sha=x=>createHash('sha256').update(x).digest('hex');
const publicBytes=Buffer.from(root.public_key_b64,'base64');
if(sha(publicBytes)!==root.public_key_sha256)throw Error('public_pin_integrity');
const key=createPublicKey({key:{kty:'OKP',crv:'Ed25519',x:publicBytes.toString('base64url')},format:'jwk'});
const account=process.env.CLOUDFLARE_ACCOUNT_ID;
const apiToken=process.env.CLOUDFLARE_API_TOKEN;
if(!/^[a-f0-9]{32}$/.test(account||'')||!apiToken)throw Error('credentials_missing');
const endpoint=`https://api.cloudflare.com/client/v4/accounts/${account}/workers/scripts/qros-mobile-g9-test-only/secrets`;
async function grants(value){
  // No transport retries on a write, no provider response logging.
  const r=await fetch(endpoint,{method:'PUT',redirect:'error',signal:AbortSignal.timeout(20000),headers:{Authorization:`Bearer ${apiToken}`,'Content-Type':'application/json'},body:JSON.stringify({name:'TOKEN_GRANTS_JSON',type:'secret_text',text:JSON.stringify(value)})});
  const j=await r.json();if(!r.ok||j.success!==true)throw Error('grant_write_rejected');
}
const tokens=Array.from({length:20},()=>randomBytes(32).toString('base64url'));
const now=Math.floor(Date.now()/1000);
const registry=tokens.map(t=>({sha256:sha(t),tenant:'tenant_A',project:'project_A',campaign:'campaign_A',scope:'demo:read',nbf:now-1,exp:now+240}));
registry[1].nbf=now-120;registry[1].exp=now-60;
registry[2].tenant='tenant_B';registry[3].project='project_B';registry[4].campaign='campaign_B';
const checks=[];
async function check(name,expected,index,extra={},method='GET'){
  const headers={'X-QROS-Project':'project_A',...extra};
  if(index!==undefined)headers.Authorization=`Bearer ${tokens[index]}`;
  const r=await fetch(origin+'/v1/demo-snapshot',{headers,method,redirect:'error',signal:AbortSignal.timeout(15000)});
  const raw=await r.text();
  if(r.status!==expected||r.headers.has('access-control-allow-origin'))throw Error('live_gate_'+name);
  checks.push({name,status:r.status,body_sha256:sha(raw),cf_ray:r.headers.get('cf-ray')});
  return raw;
}
let attempted=false;
try{
  attempted=true;await grants(registry);
  // Allow deployed secret version to propagate, without retrying credential writes.
  await new Promise(r=>setTimeout(r,5000));
  await check('missing_auth',401);
  await check('expired',401,1);
  await check('cross_tenant_grant',403,2);
  await check('cross_project_grant',403,3);
  await check('cross_campaign_grant',403,4);
  await check('cross_tenant_header',403,0,{'X-QROS-Tenant':'tenant_B'});
  await check('cross_project_header',403,0,{'X-QROS-Project':'project_B'});
  await check('cross_campaign_header',403,0,{'X-QROS-Campaign':'campaign_B'});
  await check('cors_origin',403,0,{Origin:'https://invalid.example'});
  await check('readonly_method',405,0,{},'POST');
  const bucket=Math.floor(Date.now()/60000);
  const raw=await check('valid_signed_receipt',200,0);
  const p=JSON.parse(raw);
  if(canonical(p)!==raw||!verify(null,Buffer.from(canonical(p.witness_event.body)),key,Buffer.from(p.witness_event.signature_b64,'base64')))throw Error('pinned_signature');
  if(verify(null,Buffer.from(canonical(p.witness_event.body)),key,Buffer.alloc(64)))throw Error('invalid_signature_accepted');
  await check('replay',409,0);
  // Same token simultaneously: exactly one release. Other status must be replay.
  const race=await Promise.all([fetch(origin+'/v1/demo-snapshot',{headers:{Authorization:`Bearer ${tokens[5]}`,'X-QROS-Project':'project_A'},signal:AbortSignal.timeout(15000)}),fetch(origin+'/v1/demo-snapshot',{headers:{Authorization:`Bearer ${tokens[5]}`,'X-QROS-Project':'project_A'},signal:AbortSignal.timeout(15000)})]);
  const statuses=race.map(x=>x.status).sort();if(statuses.join(',')!=='200,409')throw Error('atomic_replay');
  await Promise.all(race.map(x=>x.arrayBuffer()));checks.push({name:'concurrent_replay',statuses});
  // Quota is minute-bucket based; require evidence inside one bucket, never infer it.
  for(let i=6;i<14;i++)await check('quota_accept_'+i,200,i);
  const quota=await fetch(origin+'/v1/demo-snapshot',{headers:{Authorization:`Bearer ${tokens[14]}`,'X-QROS-Project':'project_A'},signal:AbortSignal.timeout(15000)});
  await quota.arrayBuffer();
  checks.push({name:'quota',status:quota.status,result:quota.status===429?'PASS':Math.floor(Date.now()/60000)!==bucket?'INCONCLUSIVE_BUCKET_BOUNDARY':'FAIL'});
  if(checks.at(-1).result==='FAIL')throw Error('quota');
  mkdirSync('product/mobile/g9/evidence',{recursive:true});
  writeFileSync('product/mobile/g9/evidence/worker_snapshot.json',raw);
  writeFileSync('product/mobile/g9/evidence/parity_fixture.json',JSON.stringify({payload:p,public_key_b64:root.public_key_b64,canonical_payload_sha256:sha(raw)}));
  const receipt={schema:'QROS_G9_LIVE_CANARY_V1',source_commit:process.env.GITHUB_SHA,run_id:process.env.GITHUB_RUN_ID,origin,public_key_sha256:root.public_key_sha256,checks,signature:'PASS_PINNED_ROOT_FROM_GITHUB_PROVISIONING',invalid_signature:'REJECTED_LOCALLY',external_custody:'NOT_DEPLOYED',physical_android:'NOT_RUN'};
  writeFileSync('product/mobile/g9/evidence/live_canary.json',JSON.stringify(receipt,null,2)+'\n');
  console.log('QROS_G9_LIVE_CANARY='+JSON.stringify(receipt));
  console.log('QROS_G9_LIVE_PAYLOAD_BASE64='+Buffer.from(raw).toString('base64'));
}catch{
  console.error('live_canary_failed_no_sensitive_details');process.exitCode=1;
}finally{
  if(attempted){try{await grants([]);console.log('QROS_G9_GRANTS_CLEARED=true');}catch{console.error('grant_cleanup_unverified_tokens_expire_within_240_seconds');process.exitCode=1;}}
}
