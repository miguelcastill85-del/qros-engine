import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createPrivateKey,createPublicKey} from 'node:crypto';
import {provision} from '../scripts/provision-root.mjs';
const env={CLOUDFLARE_ACCOUNT_ID:'a'.repeat(32),CLOUDFLARE_API_TOKEN:'synthetic-test-only',GITHUB_SHA:'test',GITHUB_RUN_ID:'test'};
const result=x=>({ok:true,json:async()=>({success:true,result:x})});
test('one bulk provision, public-only output, Ed25519 matching pair',async()=>{
  let calls=0; const published=[];
  const root=await provision(env,async(url,init)=>{
    calls++;
    assert.equal(init.redirect,'error');
    if(calls===1)return result([]);
    if(calls===2){
      assert.equal(init.method,'PATCH'); assert.ok(url.endsWith('/secrets-bulk'));
      const s=JSON.parse(init.body).secrets;
      const key=createPrivateKey({key:Buffer.from(s.SIGNING_PKCS8_B64.text,'base64'),format:'der',type:'pkcs8'});
      assert.equal(Buffer.from(createPublicKey(key).export({format:'jwk'}).x,'base64url').toString('base64'),s.SIGNING_PUBLIC_B64.text);
      assert.equal(s.TOKEN_GRANTS_JSON.text,'[]');
      assert.ok(!JSON.stringify(published).includes(s.SIGNING_PKCS8_B64.text));
      return result({});
    }
    return result(['SIGNING_PKCS8_B64','SIGNING_PUBLIC_B64','TOKEN_GRANTS_JSON'].map(name=>({name,type:'secret_text'})));
  },x=>published.push(structuredClone(x)));
  assert.equal(calls,3); assert.equal(published.length,2);
  assert.equal(root.status,'PROVIDER_BINDINGS_CONFIRMED_SIGNING_NOT_YET_TESTED');
});
test('existing key cannot be overwritten',async()=>{
  let calls=0;
  await assert.rejects(provision(env,async()=>{calls++;return result([{name:'SIGNING_PKCS8_B64'}]);},()=>assert.fail()),/existing_root/);
  assert.equal(calls,1);
});
test('uncertain write is never retried and public identity survives',async()=>{
  let calls=0,published=0;
  await assert.rejects(provision(env,async()=>{if(++calls===1)return result([]);throw Error('sensitive request');},()=>published++),/provider_write_unknown_no_retry/);
  assert.equal(calls,2);assert.equal(published,1);
});
test('denied read cannot trigger mutation',async()=>{
  let calls=0;
  await assert.rejects(provision(env,async()=>{calls++;return {ok:false,json:async()=>({success:false})};},()=>assert.fail()),/provider_read_rejected/);
  assert.equal(calls,1);
});
