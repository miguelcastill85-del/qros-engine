import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {randomBytes, createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {writeFile} from 'node:fs/promises';
import {runCanary} from './external_canary.mjs';
const require=createRequire(new URL('../g12/package.json',import.meta.url));
const {Miniflare}=require('miniflare');
test('deployment canary protocol is valid against the unchanged tested Worker; report contains no enrollment or session tokens',async()=>{
 const origin='https://qros-mobile-g12-test-only.test-account.workers.dev';
 const now=Math.floor(Date.now()/1000);
 const grants=Object.fromEntries(['a','b','expired','crossTenant'].map(k=>[k,randomBytes(36).toString('base64url')]));
 const entries=Object.entries(grants).map(([k,t])=>({sha256:createHash('sha256').update(t).digest('hex'),tenant:k==='crossTenant'?'tenant_B':'tenant_A',project:'project_A',campaign:'campaign_A',scope:'session:bootstrap',nbf:k==='expired'?now-299:now,exp:k==='expired'?now-1:now+299}));
 const mf=new Miniflare({modules:true,scriptPath:resolve('product/mobile/g12/worker/index.mjs'),compatibilityDate:'2026-07-30',bindings:{ENABLED:'true',PUBLIC_ORIGIN:origin,TENANT:'tenant_A',PROJECT:'project_A',CAMPAIGN:'campaign_A',BOOTSTRAP_GRANTS_JSON:JSON.stringify(entries)},durableObjects:{SESSION_BROKER:{className:'SessionBroker',useSQLite:true}}});
 try {
   const tokens=[];
   const report=await runCanary(origin,grants,async(url,options)=>{
     const r=await mf.dispatchFetch(url,options);
     const body=await r.clone().json();
     if(body.access_token) tokens.push(body.access_token,body.refresh_token);
     return r;
   });
   assert.equal(report.status,'PASS_TEST_ONLY_EXTERNAL_HTTPS');
   assert.equal(report.sessions_revoked,true);
   for(const t of [...Object.values(grants),...tokens]) assert(!JSON.stringify(report).includes(t));
   // This is local harness evidence only, never a deployed service receipt.
   await writeFile('/tmp/qros-g12-canary-local.json',JSON.stringify({...report,status:'PASS_LOCAL_PROTOCOL_ONLY'}));
 }finally{await mf.dispose();}
});
test('unsafe HTTPS origin rejected before network',async()=>{
 await assert.rejects(runCanary('https://fake.invalid',{},()=>{throw Error('must not call');}),/UNSAFE_CANARY_ORIGIN/);
});
