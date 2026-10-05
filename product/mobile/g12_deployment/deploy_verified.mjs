import {randomBytes, createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {resolve} from 'node:path';
import {validCostGate} from './check_cost_gate.mjs';

const output='/tmp/qros-g12-public';
await mkdir(output,{recursive:true});
const report={schema:'QROS_G12_DEPLOYMENT_V1',source_commit:process.env.GITHUB_SHA,status:'BLOCKED',deployment:'NOT_ATTEMPTED',free_plan:'USER_CONFIRMED_GATE_REQUIRED',scientific_authority:false,paid_services_activated:false};
const root=resolve('product/mobile/g12');
const config=resolve(root,'.g12-verified-deploy.json');
const privateFile='/tmp/qros-g12-private-canary.json';
const hash=x=>createHash('sha256').update(x).digest('hex');
let deployed=false, passed=false;
function run(args,input,withCredentials=true) {
  const env={...process.env,WRANGLER_SEND_METRICS:'false'};
  if(!withCredentials) {delete env.CLOUDFLARE_API_TOKEN;delete env.CLOUDFLARE_ACCOUNT_ID;}
  const p=spawnSync(args[0],args.slice(1),{env,input,encoding:'utf8',timeout:180000,maxBuffer:1048576});
  // Never forward subprocess output: it may contain request/credential details.
  if(p.error||p.status!==0) throw Error('SUBPROCESS_FAILED_'+args[0].replace(/[^a-z0-9]/gi,'_'));
}
const wrangler=resolve(root,'node_modules/.bin/wrangler');
const cfg=JSON.parse(await readFile(resolve(root,'wrangler.jsonc'),'utf8'));
async function deploy(enabled,origin) {
  const generated={...cfg,main:'worker/index.mjs',limits:{cpu_ms:10},
    vars:{...cfg.vars,ENABLED:enabled?'true':'false',PUBLIC_ORIGIN:origin},
    observability:{enabled:false}};
  await writeFile(config,JSON.stringify(generated,null,2)+'\n');
  run([wrangler,'deploy','--config',config]);
}
async function registry(value) {run([wrangler,'secret','bulk','--config',config],JSON.stringify({BOOTSTRAP_GRANTS_JSON:JSON.stringify(value)}));}
try {
  if(process.env.QROS_G12_FREE_PLAN_VERIFIED!=='true') throw Error('CURRENT_FREE_PLAN_CONFIRMATION_REQUIRED');
  if(!validCostGate(JSON.parse(await readFile('product/mobile/g12_deployment/cost_gate.json','utf8')))) throw Error('COST_CONFIRMATION_EXPIRED_OR_INVALID');
  if(!process.env.CLOUDFLARE_API_TOKEN||!/^[0-9a-f]{32}$/.test(process.env.CLOUDFLARE_ACCOUNT_ID||'')) throw Error('MISSING_PROVIDER_CONFIGURATION');
  const api=await fetch(`https://api.cloudflare.com/client/v4/accounts/${process.env.CLOUDFLARE_ACCOUNT_ID}/workers/subdomain`,{
    headers:{Authorization:'Bearer '+process.env.CLOUDFLARE_API_TOKEN},redirect:'error',signal:AbortSignal.timeout(15000)});
  const response=await api.json();
  if(!api.ok||response.success!==true||!/^[a-z0-9][a-z0-9-]{0,62}$/.test(response.result?.subdomain||'')) throw Error('PROVIDER_ACCESS_DENIED');
  const origin=`https://${cfg.name}.${response.result.subdomain}.workers.dev`;
  report.public_origin=origin;report.free_plan='REPORTADO_CURRENT_USER_GATE';
  // Deploy a disabled isolated Worker before any enrollment grant exists.
  report.deployment='INITIAL_WRITE_ATTEMPTED_AWAITING_PROVIDER_RESULT';
  await deploy(false,origin);deployed=true;report.deployment='DISABLED_WORKER_CREATED';
  const now=Math.floor(Date.now()/1000);
  const grants=Object.fromEntries(['a','b','expired','crossTenant'].map(k=>[k,randomBytes(36).toString('base64url')]));
  const entries=Object.entries(grants).map(([k,t])=>({sha256:hash(t),tenant:k==='crossTenant'?'tenant_B':'tenant_A',project:'project_A',campaign:'campaign_A',scope:'session:bootstrap',nbf:k==='expired'?now-299:now,exp:k==='expired'?now-1:now+299}));
  await registry(entries);
  await writeFile(privateFile,JSON.stringify({origin,grants}),{mode:0o600});
  await deploy(true,origin);report.deployment='ENABLED_CANARY_WITH_SHORT_GRANTS';
  run(['node','product/mobile/g12_deployment/external_canary.mjs',privateFile,output+'/external-canary.json'],undefined,false);
  run(['python3','product/mobile/g12_deployment/verify_external.py',output+'/external-canary.json',output+'/python-external-verification.json'],undefined,false);
  passed=true;report.status='PASS_TEST_ONLY_DEPLOYMENT_AND_EXTERNAL_HTTPS';
}catch(e){
  report.reason=/^[a-z0-9_]+$/i.test(e.message||'')?e.message:'DEPLOYMENT_FAILURE';
  if(report.deployment==='INITIAL_WRITE_ATTEMPTED_AWAITING_PROVIDER_RESULT') report.deployment='UNKNOWN_REQUIRES_PROVIDER_INSPECTION';
}
finally {
  if(deployed) {
    try{await registry([]);report.bootstrap_registry_cleared=true;}catch{report.bootstrap_registry_cleared=false;passed=false;report.status='FAIL_CLEANUP';}
    if(!passed) {
      try{await deploy(false,report.public_origin);report.deployment='DISABLED_AFTER_FAILURE';}catch{report.deployment='UNKNOWN_REQUIRES_PROVIDER_INSPECTION';}
    }else report.deployment='ENABLED_NO_ACTIVE_BOOTSTRAP_GRANTS';
  }
  await rm(privateFile,{force:true});
  await rm(config,{force:true});
  report.completed_at=new Date().toISOString();
  await writeFile(output+'/deployment-receipt.json',JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));
}
if(!passed) process.exitCode=1;
