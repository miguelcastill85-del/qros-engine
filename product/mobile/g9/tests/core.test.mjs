import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {canonical,sha,b64,handle,snapshot} from '../worker/core.mjs';
const pair=await crypto.subtle.generateKey('Ed25519',true,['sign','verify']);
const env={ENABLED:'true',PUBLIC_ORIGIN:'https://canary.example',TENANT:'tenant_A',PROJECT:'project_A',CAMPAIGN:'campaign_A',WITNESS_ID:'g9_backend_test_only',
 SNAPSHOT_CREATED_UTC:'2026-09-26T00:00:00Z',SIGNING_PKCS8_B64:b64(await crypto.subtle.exportKey('pkcs8',pair.privateKey)),SIGNING_PUBLIC_B64:b64(await crypto.subtle.exportKey('raw',pair.publicKey))};
const token='A'.repeat(43), now=1000000000;
const grant={sha256:await sha(token),tenant:'tenant_A',project:'project_A',campaign:'campaign_A',scope:'demo:read',nbf:now-1,exp:now+299};
env.TOKEN_GRANTS_JSON=JSON.stringify([grant]);
const request=(headers={},url=env.PUBLIC_ORIGIN+'/v1/demo-snapshot',method='GET')=>new Request(url,{method,headers:{Authorization:'Bearer '+token,'X-QROS-Project':'project_A',...headers}});
const ok=async()=>200;
test('G6 frozen fixture canonical bytes unchanged by JS',async()=>{
 const f=JSON.parse(readFileSync(new URL('../../g6/tests/fixtures/g5_signed_snapshot_fixture.json',import.meta.url)));
 assert.equal(await sha(canonical(f.payload)),f.canonical_payload_sha256);
 const key=await crypto.subtle.importKey('raw',Uint8Array.from(atob(f.public_key_b64),c=>c.charCodeAt(0)),'Ed25519',false,['verify']);
 assert.ok(await crypto.subtle.verify('Ed25519',key,Uint8Array.from(atob(f.payload.witness_event.signature_b64),c=>c.charCodeAt(0)),new TextEncoder().encode(canonical(f.payload.witness_event.body))));
});
test('fresh backend root signs G6-compatible canonical payload; export only public evidence',async()=>{
 const r=await handle(request(),env,ok,now);assert.equal(r.status,200);
 const raw=await r.text(),p=JSON.parse(raw);assert.equal(raw,canonical(p));
 assert.equal(r.headers.get('Access-Control-Allow-Origin'),null);assert.match(r.headers.get('Cache-Control'),/no-store/);
 assert.equal(p.external_independent_custody,'NOT_DEPLOYED');assert.equal(p.holdout_open,false);
 assert.ok(!raw.includes(env.SIGNING_PKCS8_B64));assert.ok(!raw.includes(token));assert.ok(!raw.includes(env.SIGNING_PUBLIC_B64));
 mkdirSync(new URL('../evidence/',import.meta.url),{recursive:true});
 writeFileSync(new URL('../evidence/worker_snapshot.json',import.meta.url),raw);
 writeFileSync(new URL('../evidence/parity_fixture.json',import.meta.url),JSON.stringify({public_key_b64:env.SIGNING_PUBLIC_B64,payload:p,canonical_payload_sha256:await sha(raw)}));
});
for(const [name,headers,status] of [
 ['unknown bearer',{Authorization:'Bearer '+'B'.repeat(43)},401],['malformed bearer',{Authorization:'Basic forbidden'},401],
 ['project crossing',{'X-QROS-Project':'project_B'},403],['tenant crossing',{'X-QROS-Tenant':'tenant_B'},403],
 ['campaign crossing',{'X-QROS-Campaign':'campaign_B'},403],['browser origin',{Origin:'https://attacker.example'},403]])
 test(name,async()=>assert.equal((await handle(request(headers),env,ok,now)).status,status));
for(const method of ['POST','PUT','PATCH','DELETE','OPTIONS','HEAD'])test('read only '+method,async()=>assert.equal((await handle(request({},undefined,method),env,ok,now)).status,405));
for(const [name,url,status] of [['plaintext','http://canary.example/v1/demo-snapshot',403],['false server','https://false.example/v1/demo-snapshot',403],['query token',env.PUBLIC_ORIGIN+'/v1/demo-snapshot?token=x',404],['unknown path',env.PUBLIC_ORIGIN+'/admin',404]])test(name,async()=>assert.equal((await handle(request({},url),env,ok,now)).status,status));
test('expired and future tokens',async()=>{for(const t of [grant.exp,grant.nbf-1])assert.equal((await handle(request(),env,ok,t)).status,401);});
test('invalid registry, TTL, duplicate grants and scope',async()=>{
 for(const g of [{...grant,exp:now+301},{...grant,scope:'write'},{...grant,exp:'wrong'}])assert.equal((await handle(request(),{...env,TOKEN_GRANTS_JSON:JSON.stringify([g])},ok,now)).status,503);
 assert.equal((await handle(request(),{...env,TOKEN_GRANTS_JSON:JSON.stringify([grant,grant])},ok,now)).status,401);
});
test('missing dependencies fail closed without secret detail',async()=>{
 for(const key of ['SIGNING_PKCS8_B64','SIGNING_PUBLIC_B64','TOKEN_GRANTS_JSON']){
  const e={...env};delete e[key];const r=await handle(request(),e,ok,now);assert.equal(r.status,503);assert.equal(await r.text(),'{"error":"unavailable"}');
 }
 assert.equal((await handle(request(),env,async()=>{throw Error('secret')},now)).status,503);
});
test('published G6 private-fixture root is forbidden',async()=>assert.equal((await handle(request(),{...env,SIGNING_PUBLIC_B64:'QwRr/kCSs+lJlOraFdzCDYqqB7ZY/TlU644O+4vcpd4='},ok,now)).status,503));
test('replay and limits preserved in transport',async()=>{for(const s of [409,429,503])assert.equal((await handle(request(),env,async()=>s,now)).status,s);});
test('disabled deployment stays closed',async()=>assert.equal((await handle(request(),{...env,ENABLED:'false'},ok,now)).status,503));
test('manipulated signature cryptographic rejection',async()=>{
 const p=await snapshot(env),msg=new TextEncoder().encode(canonical({...p.witness_event.body,tenant:'tenant_B'}));
 assert.equal(await crypto.subtle.verify('Ed25519',pair.publicKey,Uint8Array.from(atob(p.witness_event.signature_b64),c=>c.charCodeAt(0)),msg),false);
});
