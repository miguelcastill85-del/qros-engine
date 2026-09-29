// TEST_ONLY. Bearer is provided through GitHub Actions Secrets, never printed.
import {createHash} from 'node:crypto';
import {writeFileSync,mkdirSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
export function buildGrant(token,now){
  if(typeof token!=='string'||!/^[A-Za-z0-9_-]{48}$/.test(token)||new Set(token).size<16)throw Error('phone_token_format');
  if(!Number.isSafeInteger(now)||now<1)throw Error('clock');
  return {sha256:createHash('sha256').update(token).digest('hex'),tenant:'tenant_A',project:'project_A',campaign:'campaign_A',scope:'demo:read',nbf:now,exp:now+299};
}
export async function provision(env,request=fetch,now=Math.floor(Date.now()/1000)){
  const grant=buildGrant(env.QROS_G9_PHONE_TOKEN,now);
  if(!/^[a-f0-9]{32}$/.test(env.CLOUDFLARE_ACCOUNT_ID||'')||!env.CLOUDFLARE_API_TOKEN)throw Error('provider_credentials_missing');
  const url=`https://api.cloudflare.com/client/v4/accounts/${env.CLOUDFLARE_ACCOUNT_ID}/workers/scripts/qros-mobile-g9-test-only/secrets`;
  const response=await request(url,{method:'PUT',redirect:'error',signal:AbortSignal.timeout(20000),headers:{Authorization:`Bearer ${env.CLOUDFLARE_API_TOKEN}`,'Content-Type':'application/json'},body:JSON.stringify({name:'TOKEN_GRANTS_JSON',type:'secret_text',text:JSON.stringify([grant])})});
  const result=await response.json();
  if(!response.ok||result.success!==true)throw Error('grant_write_unverified');
  // No retries on an uncertain write; no authenticated request that would consume it.
  // Expiry is enforced by Worker, even if CI stops. Retain only a hash in the backend.
  return {schema:'QROS_G9_PHONE_WINDOW_V1',status:'PROVIDER_WRITE_CONFIRMED_PHONE_RESULT_PENDING',source_commit:env.GITHUB_SHA,run_id:env.GITHUB_RUN_ID,origin:'https://qros-mobile-g9-test-only.miguelcastill85.workers.dev',valid_from_utc:new Date(grant.nbf*1000).toISOString(),expires_at_utc:new Date(grant.exp*1000).toISOString(),max_lifetime_seconds:299,scope:'tenant_A/project_A/campaign_A demo:read',bearer_disclosed:false,phone_authenticated_request:'NOT_OBSERVED',cleanup:'FAIL_CLOSED_EXPIRY; backend stores hash only; remove user-held GitHub secret after the test',scientific_gate_pass:false};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  try{
    const receipt=await provision(process.env);
    mkdirSync('/tmp/qros-g9-phone',{recursive:true});
    writeFileSync('/tmp/qros-g9-phone/PHONE_WINDOW.json',JSON.stringify(receipt,null,2)+'\n');
    console.log(JSON.stringify(receipt));
  }catch{console.error('QROS_G9_PHONE_WINDOW_FAILED_NO_SECRET_DETAILS; if provider write was attempted, any grant expires within 299 seconds; do not retry automatically');process.exitCode=1;}
}
