import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync,writeFileSync,mkdirSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {Miniflare} from 'miniflare';
import {sha,b64,canonical} from '../worker/core.mjs';
test('actual workerd SQLite DO: concurrency replay, restart, quotas, scoped access and Python/Dart evidence',async()=>{
 const key=await crypto.subtle.generateKey('Ed25519',true,['sign','verify']);
 const origin='https://canary.example',now=Math.floor(Date.now()/1000);
 const tokens=Array.from({length:15},(_,i)=>String.fromCharCode(65+i).repeat(43));
 const grants=await Promise.all(tokens.map(async t=>({sha256:await sha(t),tenant:'tenant_A',project:'project_A',campaign:'campaign_A',scope:'demo:read',nbf:now-1,exp:now+299})));
 const pub=b64(await crypto.subtle.exportKey('raw',key.publicKey));
 const bindings={ENABLED:'true',PUBLIC_ORIGIN:origin,TENANT:'tenant_A',PROJECT:'project_A',CAMPAIGN:'campaign_A',WITNESS_ID:'g9_backend_test_only',SNAPSHOT_CREATED_UTC:'2026-09-26T00:00:00Z',SIGNING_PUBLIC_B64:pub,SIGNING_PKCS8_B64:b64(await crypto.subtle.exportKey('pkcs8',key.privateKey)),TOKEN_GRANTS_JSON:JSON.stringify(grants)};
 const dir=mkdtempSync(join(tmpdir(),'qros-g9-do-'));
 const opts={modules:true,scriptPath:resolve('product/mobile/g9/worker/index.mjs'),compatibilityDate:'2026-07-30',bindings,durableObjects:{REPLAY_GATE:{className:'ReplayGate',useSQLite:true}},durableObjectsPersist:dir};
 let mf=new Miniflare(opts);
 const fetch=(token,headers={})=>mf.dispatchFetch(origin+'/v1/demo-snapshot',{headers:{Authorization:'Bearer '+token,'X-QROS-Project':'project_A',...headers}});
 try {
  assert.equal((await fetch(tokens[0],{'X-QROS-Campaign':'wrong'})).status,403);
  const replies=await Promise.all(Array.from({length:8},()=>fetch(tokens[0])));
  assert.equal(replies.filter(r=>r.status===200).length,1);assert.equal(replies.filter(r=>r.status===409).length,7);
  const raw=await replies.find(r=>r.status===200).text();const p=JSON.parse(raw);assert.equal(raw,canonical(p));
  mkdirSync('product/mobile/g9/evidence',{recursive:true});
  writeFileSync('product/mobile/g9/evidence/worker_snapshot.json',raw);
  writeFileSync('product/mobile/g9/evidence/parity_fixture.json',JSON.stringify({public_key_b64:pub,payload:p,canonical_payload_sha256:await sha(raw)}));
  await mf.dispose();mf=new Miniflare(opts);
  assert.equal((await fetch(tokens[0])).status,409);
  for(let i=1;i<10;i++)assert.equal((await fetch(tokens[i])).status,200);
  assert.equal((await fetch(tokens[10])).status,429);
  writeFileSync('product/mobile/g9/evidence/workerd_receipt.json',JSON.stringify({status:'PASS_TEST_ONLY',runtime:'workerd_miniflare',concurrent_requests:8,accepted:1,replays_denied:7,restart_replay_denied:true,quota_denied:true,public_https:false,physical_android:false}));
 }finally{await mf.dispose();rmSync(dir,{recursive:true,force:true});}
});
