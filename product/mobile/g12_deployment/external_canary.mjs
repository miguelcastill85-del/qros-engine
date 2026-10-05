import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';

const digest = x => createHash('sha256').update(x).digest('hex');
const canonical = o => JSON.stringify(Object.fromEntries(Object.entries(o).sort(([a],[b]) => a.localeCompare(b))));
export async function runCanary(origin, grants, transport = fetch) {
  const u = new URL(origin);
  if(u.protocol !== 'https:' || u.origin !== origin || !/^qros-mobile-g12-test-only\.[a-z0-9-]+\.workers\.dev$/.test(u.hostname)) throw Error('UNSAFE_CANARY_ORIGIN');
  const report = {schema:'QROS_G12_EXTERNAL_CANARY_V1', public_origin:origin, status:'FAIL', checks:[], sessions_revoked:false, scientific_authority:false, economic_tests:0};
  let a, b;
  const deviceA = 'device_'+'A'.repeat(43), deviceB = 'device_'+'B'.repeat(43);
  function check(name, ok) {report.checks.push({name, status:ok?'PASS':'FAIL'}); if(!ok) throw Error(name);}
  async function request(path, method='GET', token, device, body, extra={}) {
    const headers={...extra};
    if(token) headers.Authorization='Bearer '+token;
    if(device) headers['X-QROS-Device']=device;
    if(body) headers['Content-Type']='application/json';
    const response = await transport(origin+path, {method,headers,body:body?JSON.stringify(body):undefined,redirect:'error',signal:AbortSignal.timeout(20000)});
    const bytes = await response.arrayBuffer();
    if(bytes.byteLength>65536) throw Error('RESPONSE_LIMIT');
    const data = JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
    check('no_permissive_cors', !response.headers.has('access-control-allow-origin'));
    check('no_store', (response.headers.get('cache-control')||'').includes('no-store'));
    return {status:response.status,data};
  }
  try {
    let r=await request('/v1/jobs/synthetic');check('unauthenticated_rejected',r.status===404);
    r=await request('/v1/session/bootstrap','POST','Z'.repeat(48),null,{device_id:deviceA});check('unknown_bootstrap_rejected',r.status===401);
    r=await request('/v1/session/bootstrap','POST',grants.expired,null,{device_id:deviceA});check('expired_bootstrap_rejected',r.status===401);
    r=await request('/v1/session/bootstrap','POST',grants.crossTenant,null,{device_id:deviceA});check('cross_tenant_rejected',r.status===403);
    r=await request('/v1/session/bootstrap','POST',grants.a,null,{device_id:deviceA});check('bootstrap_a',r.status===200);a=r.data;
    r=await request('/v1/session/bootstrap','POST',grants.a,null,{device_id:deviceA});check('bootstrap_replay_rejected',r.status===409);
    r=await request('/v1/session/bootstrap','POST',grants.b,null,{device_id:deviceB});check('bootstrap_b',r.status===200);b=r.data;
    check('session_scope_no_scientific_authority',a.scope==='synthetic:jobs'&&a.scientific_authority==='NONE'&&b.client_id!==a.client_id);
    const input={request_id:'req_'+'C'.repeat(22),search_space_sha256:'1'.repeat(64),toy_enumeration_sha256:'2'.repeat(64),raw_births:12};
    r=await request('/v1/jobs/synthetic','POST',a.access_token,deviceA,input);check('create_job',r.status===201);const job=r.data;
    r=await request('/v1/jobs/synthetic','POST',a.access_token,deviceA,input);check('retry_same_job',r.status===200&&r.data.job_id===job.job_id);
    r=await request('/v1/jobs/synthetic','POST',a.access_token,deviceA,{...input,raw_births:13});check('conflicting_retry_rejected',r.status===409);
    const path='/v1/jobs/synthetic/'+job.job_id;
    r=await request(path,'GET',a.access_token,deviceB);check('wrong_device_rejected',r.status===401);
    r=await request(path,'GET',b.access_token,deviceB);check('cross_client_rejected',r.status===404);
    r=await request(path+'?x=1','GET',a.access_token,deviceA);check('query_rejected',r.status===403);
    r=await request(path,'GET',a.access_token,deviceA,null,{Origin:'https://fake.invalid'});check('cors_origin_rejected',r.status===403);
    const old=a;
    r=await request('/v1/session/refresh','POST',old.refresh_token,deviceA);check('refresh_rotated',r.status===200);a=r.data;
    r=await request('/v1/session/refresh','POST',old.refresh_token,deviceA);check('refresh_replay_rejected',r.status===401);
    r=await request(path,'GET',old.access_token,deviceA);check('old_access_rejected',r.status===401);
    for(let phase=1;phase<=3;phase++) {
      r=await request(path+'/resume','POST',a.access_token,deviceA);check('resume_phase_'+phase,r.status===200&&r.data.phase===phase);
    }
    const completed=r.data;
    check('complete_synthetic_only',completed.state==='COMPLETE'&&completed.progress===100&&completed.economic_tests===0&&completed.scientific_approval===false&&completed.holdout_open===false&&completed.ga2_open===false&&completed.mt5_executed===false);
    const {result_sha256,...body}=completed.result;
    check('independent_node_result_hash',digest(canonical(body))===result_sha256);
    check('result_input_binding',body.job_id===job.job_id&&body.raw_births===input.raw_births&&body.search_space_sha256===input.search_space_sha256&&body.toy_enumeration_sha256===input.toy_enumeration_sha256);
    r=await request(path+'/resume','POST',a.access_token,deviceA);check('completed_resume_idempotent',r.status===200&&r.data.result.result_sha256===result_sha256);
    report.synthetic_result=completed.result;
    report.status='PASS_TEST_ONLY_EXTERNAL_HTTPS';
  } catch(e) {report.failure = e instanceof Error && /^[a-z0-9_]+$/i.test(e.message) ? e.message : 'NETWORK_OR_PROTOCOL_FAILURE';}
  finally {
    const revoked=[];
    for(const [session,device] of [[a,deviceA],[b,deviceB]]) if(session) {
      try {
        const r=await request('/v1/session/revoke','POST',session.refresh_token,device);
        revoked.push(r.status===200);
        const denied=await request('/v1/session/refresh','POST',session.refresh_token,device);
        revoked.push(denied.status===401);
      }catch{revoked.push(false);}
    }
    report.sessions_revoked=revoked.length===4&&revoked.every(Boolean);
    if(!report.sessions_revoked) report.status='FAIL';
  }
  return report;
}
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href) {
  const privateInput=JSON.parse(await readFile(process.argv[2],'utf8'));
  const report=await runCanary(privateInput.origin,privateInput.grants);
  report.source_commit=process.env.GITHUB_SHA;
  report.verified_at=new Date().toISOString();
  await writeFile(process.argv[3],JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({status:report.status,checks:report.checks.length,sessions_revoked:report.sessions_revoked}));
  if(report.status!=='PASS_TEST_ONLY_EXTERNAL_HTTPS') process.exitCode=1;
}
