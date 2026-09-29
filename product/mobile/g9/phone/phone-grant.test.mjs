import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomBytes} from 'node:crypto';
import {buildGrant,provision} from './phone-grant.mjs';
import {authorize} from '../worker/core.mjs';
const token=randomBytes(36).toString('base64url');
test('phone grant accepts exact scope, rejects expiry and cross-project in actual Worker authorizer',async()=>{
 const g=buildGrant(token,1000),env={PUBLIC_ORIGIN:'https://worker.invalid',TOKEN_GRANTS_JSON:JSON.stringify([g]),TENANT:'tenant_A',PROJECT:'project_A',CAMPAIGN:'campaign_A'};
 const req=p=>new Request('https://worker.invalid/v1/demo-snapshot',{headers:{Authorization:`Bearer ${token}`,'X-QROS-Project':p}});
 assert.equal((await authorize(req('project_A'),env,1000)).status,200);
 assert.equal((await authorize(req('project_A'),env,1299)).status,401);
 assert.equal((await authorize(req('project_B'),env,1000)).status,403);
});
test('malformed token cannot reach provider',async()=>{
 let calls=0;await assert.rejects(provision({QROS_G9_PHONE_TOKEN:'A'.repeat(48)},async()=>{calls++},1000));assert.equal(calls,0);
});
test('only hash reaches provider; receipt excludes bearer and provider credential',async()=>{
 const env={QROS_G9_PHONE_TOKEN:token,CLOUDFLARE_ACCOUNT_ID:'a'.repeat(32),CLOUDFLARE_API_TOKEN:'test-provider-secret',GITHUB_SHA:'fixture',GITHUB_RUN_ID:'fixture'};
 let calls=0;const receipt=await provision(env,async(url,options)=>{calls++;assert.equal(options.redirect,'error');assert.equal(options.body.includes(token),false);const g=JSON.parse(JSON.parse(options.body).text)[0];assert.equal(g.exp-g.nbf,299);return {ok:true,json:async()=>({success:true})}},1000);
 assert.equal(calls,1);assert.equal(JSON.stringify(receipt).includes(token),false);assert.equal(JSON.stringify(receipt).includes(env.CLOUDFLARE_API_TOKEN),false);
});
test('provider rejection is not retried',async()=>{
 let calls=0;await assert.rejects(provision({QROS_G9_PHONE_TOKEN:token,CLOUDFLARE_ACCOUNT_ID:'a'.repeat(32),CLOUDFLARE_API_TOKEN:'fixture'},async()=>{calls++;return {ok:false,json:async()=>({success:false})}},1000));assert.equal(calls,1);
});
