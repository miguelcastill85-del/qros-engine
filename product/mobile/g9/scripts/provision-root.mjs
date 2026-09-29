// Backend provisioning only. Never print requests, API bodies or private material.
import {generateKeyPairSync, createHash} from 'node:crypto';
import {mkdirSync, writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const worker = 'qros-mobile-g9-test-only';
const names = ['SIGNING_PKCS8_B64', 'SIGNING_PUBLIC_B64', 'TOKEN_GRANTS_JSON'];
export async function provision(env, request, publish) {
  if (!/^[a-f0-9]{32}$/.test(env.CLOUDFLARE_ACCOUNT_ID || '') || !env.CLOUDFLARE_API_TOKEN)
    throw Error('credentials_missing_or_invalid');
  const endpoint = `https://api.cloudflare.com/client/v4/accounts/${env.CLOUDFLARE_ACCOUNT_ID}/workers/scripts/${worker}`;
  const headers = {Authorization: `Bearer ${env.CLOUDFLARE_API_TOKEN}`, 'Content-Type':'application/json'};
  async function api(path, method='GET', body) {
    let r, j;
    try {
      r = await request(endpoint+path, {method, headers, redirect:'error', signal:AbortSignal.timeout(20000), ...(body ? {body:JSON.stringify(body)} : {})});
      j = await r.json();
    } catch { throw Error(method==='GET' ? 'provider_read_failed' : 'provider_write_unknown_no_retry'); }
    if (!r.ok || j.success !== true) throw Error(method==='GET' ? 'provider_read_rejected' : 'provider_write_rejected_no_retry');
    return j.result;
  }
  const before = await api('/secrets');
  if (!Array.isArray(before)) throw Error('invalid_secret_inventory');
  if (before.some(x=>names.includes(x.name))) throw Error('existing_root_or_grants_manual_reconciliation_required');
  const pair = generateKeyPairSync('ed25519');
  const pub = Buffer.from(pair.publicKey.export({format:'jwk'}).x, 'base64url');
  const der = pair.privateKey.export({format:'der',type:'pkcs8'});
  const root = {schema:'QROS_G9_PUBLIC_ROOT_V1', worker, algorithm:'Ed25519', public_key_b64:pub.toString('base64'), public_key_sha256:createHash('sha256').update(pub).digest('hex'), source_commit:env.GITHUB_SHA, run_id:env.GITHUB_RUN_ID, origin:'https://qros-mobile-g9-test-only.miguelcastill85.workers.dev', custody:'CLOUDFLARE_SECRET_SAME_OPERATOR_NOT_INDEPENDENT', status:'GENERATED_NOT_YET_CONFIRMED'};
  // Public recovery identity must survive even if the mutation outcome is ambiguous.
  publish(root);
  try {
    const values=[der.toString('base64'),root.public_key_b64,'[]'];
    const secrets=Object.fromEntries(names.map((name,i)=>[name,{name,type:'secret_text',text:values[i]}]));
    await api('/secrets-bulk','PATCH',{secrets});
    const after=await api('/secrets');
    if (!Array.isArray(after) || !names.every(n=>after.some(x=>x.name===n && x.type==='secret_text')))
      throw Error('postwrite_inventory_unverified_no_retry');
    root.status='PROVIDER_BINDINGS_CONFIRMED_SIGNING_NOT_YET_TESTED';
    publish(root);
    return root;
  } finally { der.fill(0); }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    await provision(process.env, fetch, root=>{
      mkdirSync('public-root-evidence',{recursive:true});
      writeFileSync('public-root-evidence/public-root.json',JSON.stringify(root,null,2)+'\n');
      console.log('QROS_G9_PUBLIC_ROOT='+JSON.stringify(root));
    });
  } catch(e) {
    // Only our fixed codes; never serialize a provider response or exception object.
    const allowed=['credentials_missing_or_invalid','provider_read_failed','provider_write_unknown_no_retry','provider_read_rejected','provider_write_rejected_no_retry','invalid_secret_inventory','existing_root_or_grants_manual_reconciliation_required','postwrite_inventory_unverified_no_retry'];
    console.error(allowed.includes(e.message)?e.message:'provision_failed_no_retry');
    process.exitCode=1;
  }
}
