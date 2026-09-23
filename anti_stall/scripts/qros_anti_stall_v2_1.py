#!/usr/bin/env python3
"""QROS/RISE anti-stall v2.1: one frozen, evidence-producing action per call.

Local self-hashes detect accidental drift only. Promotion requires an independently
retrieved, immutable Git blob pin, and Drive metadata/bytes checked separately.
This program is a control-plane runner, not an MT5 or economic-result certifier.
"""
from __future__ import annotations
import argparse, contextlib, hashlib, json, os, pathlib, re, signal, subprocess, sys, time
try:
    import fcntl  # POSIX
except ImportError:
    fcntl=None
try:
    import msvcrt  # Windows
except ImportError:
    msvcrt=None

HEX64=re.compile(r'^[0-9a-f]{64}$'); HEX40=re.compile(r'^[0-9a-f]{40}$')
SCHEMA='QROS_ANTI_STALL_PLAN_V2_1'; STATE='QROS_ANTI_STALL_STATE_V2_1'
INTERNAL={'QROS_ANTI_STALL_STATE_V2_1.json','.qros_anti_stall.lock'}

class Incident(RuntimeError): pass

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
def digest(raw): return hashlib.sha256(raw).hexdigest()
def blob_sha(raw): return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def sha_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for piece in iter(lambda:f.read(4*1024*1024),b''):h.update(piece)
    return h.hexdigest()
def assert_hex(v,n=64):
    if not isinstance(v,str) or not (HEX64 if n==64 else HEX40).fullmatch(v): raise Incident('INVALID_EXTERNAL_HASH_PIN')
def under(root,name):
    if not isinstance(name,str) or not name or '\\' in name or name.startswith('/') or '\0' in name:raise Incident('UNSAFE_ARTIFACT_PATH')
    parts=name.split('/')
    if any(p in ('.','..','') for p in parts) or name in INTERNAL or name.startswith('.qros_'):raise Incident('UNSAFE_ARTIFACT_PATH')
    root=root.resolve();candidate=root.joinpath(*parts).resolve()
    if candidate==root or not candidate.is_relative_to(root):raise Incident('ARTIFACT_PATH_ESCAPE')
    return candidate

def atomic_json(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.tmp.'+str(os.getpid()))
    with open(tmp,'wb') as f:
        f.write(json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False).encode()+b'\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def signed(s):
    p={k:v for k,v in s.items() if k!='self_sha256'}
    return {**p,'self_sha256':digest(canonical(p))}

def add_event(s,kind,stage=None,**details):
    previous=s['events'][-1]['event_sha256'] if s['events'] else '0'*64
    e={'sequence':len(s['events'])+1,'previous_sha256':previous,'kind':kind,'stage':stage,'details':details}
    e['event_sha256']=digest(canonical(e));s['events'].append(e)

def load_state(root):
    p=root/'QROS_ANTI_STALL_STATE_V2_1.json'
    if not p.is_file():raise Incident('UNINITIALIZED_REQUIRE_INIT')
    x=json.loads(p.read_bytes());expected=signed(x)['self_sha256']
    if expected!=x.get('self_sha256'):raise Incident('STATE_SELF_DIGEST_DRIFT')
    if x.get('schema')!=STATE:raise Incident('UNKNOWN_STATE_SCHEMA')
    return x

def save_state(root,s):atomic_json(root/'QROS_ANTI_STALL_STATE_V2_1.json',signed(s))

def parse_plan(root,plan_path,expected_sha):
    assert_hex(expected_sha)
    raw=pathlib.Path(plan_path).read_bytes()
    if digest(raw)!=expected_sha:raise Incident('FROZEN_PLAN_EXTERNAL_PIN_MISMATCH')
    p=json.loads(raw)
    if p.get('schema')!=SCHEMA or not isinstance(p.get('lane_id'),str) or not p.get('lane_id'):raise Incident('PLAN_SCHEMA_INVALID')
    a=p.get('authority',{})
    if not isinstance(a,dict) or not a.get('repo') or not a.get('branch') or not HEX40.fullmatch(a.get('base_commit','')):raise Incident('AUTHORITY_INCOMPLETE')
    if not isinstance(p.get('stages'),list) or not p['stages']:raise Incident('PLAN_STAGES_EMPTY')
    ids=set();paths=set()
    for step in p['stages']:
        sid=step.get('id','')
        if not re.fullmatch('[A-Z][A-Z0-9_]{2,70}',sid) or sid in ids:raise Incident('STAGE_ID_INVALID_OR_DUPLICATE')
        ids.add(sid)
        if step.get('kind') not in ('local','external'):raise Incident('BAD_STAGE_KIND')
        outputs=step.get('outputs',[])
        if not outputs or not isinstance(outputs,list):raise Incident('OUTPUT_CONTRACT_MISSING')
        for item in outputs:
            path=item.get('path');under(root,path)
            if path in paths:raise Incident('OUTPUT_PATH_REUSED_ACROSS_STAGES')
            paths.add(path)
            if item.get('sha256') is not None:assert_hex(item['sha256'])
            if item.get('bytes') is not None and (not isinstance(item['bytes'],int) or item['bytes']<0):raise Incident('OUTPUT_SIZE_INVALID')
        if step['kind']=='local':
            if not step.get('routes') or not step.get('inputs'):raise Incident('LOCAL_STAGE_NEEDS_FROZEN_ROUTES_AND_INPUTS')
            for t in step['inputs']:
                under(root,t['path']);assert_hex(t['sha256'])
                if not isinstance(t.get('bytes'),int) or t['bytes']<0:raise Incident('INPUT_SIZE_INVALID')
            names=set()
            for route in step['routes']:
                if route['name'] in names or not isinstance(route.get('argv'),list) or not route['argv'] or not all(isinstance(v,str) and v for v in route['argv']):raise Incident('ROUTE_INVALID')
                names.add(route['name'])
        else:
            assert_hex(step.get('anchor_git_blob_sha1'),40)
            if not step.get('remote_id'):raise Incident('REMOTE_ID_MISSING')
    locks=p.get('scientific_firewalls',{})
    for k in ('holdout_open','ga2_open','new_old_shard_ga1_authorized'):
        if locks.get(k) is not False:raise Incident('SCIENTIFIC_FIREWALL_MISSING_'+k)
    return p

def check_bytes(root,item,require_expected=False):
    p=under(root,item['path'])
    if not p.is_file():raise Incident('ARTIFACT_ABSENT:'+item['path'])
    size=p.stat().st_size;h=sha_file(p)
    if item.get('bytes') is not None and size!=item['bytes']:raise Incident('ARTIFACT_SIZE_DRIFT:'+item['path'])
    if item.get('sha256') is not None and h!=item['sha256']:raise Incident('ARTIFACT_HASH_DRIFT:'+item['path'])
    if require_expected and (item.get('bytes') is None or item.get('sha256') is None):raise Incident('EXPECTED_OUTPUT_HASH_REQUIRED')
    return {'path':item['path'],'bytes':size,'sha256':h}

def revalidate(root,plan,s):
    if s['authority']!=plan['authority'] or s['lane_id']!=plan['lane_id']:raise Incident('AUTHORITY_MIXING')
    stages=s['stages'];ps=plan['stages']
    if len(stages)!=len(ps):raise Incident('PLAN_STATE_LENGTH_DRIFT')
    seen_pending=False
    for i,(z,t) in enumerate(zip(stages,ps)):
        if z['id']!=t['id']:raise Incident('STAGE_IDENTITY_DRIFT')
        if z['status']=='PASS':
            if seen_pending:raise Incident('NON_PREFIX_PASS_INVALID')
            if [x['path'] for x in z['outputs']]!=[x['path'] for x in t['outputs']]:raise Incident('OUTPUT_CONTRACT_DRIFT')
            for x in z['outputs']:check_bytes(root,x,True)
            if t['kind']=='local':
                for source in t['inputs']:check_bytes(root,source,True)
        else:seen_pending=True
    if s['cursor']!=sum(z['status']=='PASS' for z in stages):raise Incident('CURSOR_DRIFT')
    if any(z['status']=='PASS' for z in stages[s['cursor']:]):raise Incident('PASS_AFTER_CURSOR')
    if s['scientific_firewalls']!=plan['scientific_firewalls']:raise Incident('FIREWALL_DRIFT')
    prev='0'*64
    for n,e in enumerate(s['events'],1):
        if e.get('sequence')!=n or e.get('previous_sha256')!=prev:raise Incident('EVENT_CHAIN_DRIFT')
        if digest(canonical({k:v for k,v in e.items() if k!='event_sha256'}))!=e.get('event_sha256'):raise Incident('EVENT_HASH_DRIFT')
        prev=e['event_sha256']
    return True

@contextlib.contextmanager
def mutex(root):
    # No unbounded wait: a crashed/competing process cannot monopolize the chat.
    root.mkdir(parents=True,exist_ok=True)
    timeout=max(0.2,min(float(os.environ.get('QROS_LOCK_TIMEOUT_SECONDS','8')),30))
    with open(root/'.qros_anti_stall.lock','a+b') as f:
        if msvcrt is not None:
            f.seek(0);f.write(b'0');f.flush()
        end=time.monotonic()+timeout;locked=False
        while not locked:
            try:
                if fcntl is not None:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
                elif msvcrt is not None:
                    f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
                else:raise Incident('NO_SUPPORTED_PROCESS_LOCK')
                locked=True
            except (OSError,BlockingIOError):
                if time.monotonic()>=end:raise Incident('LOCK_CONTENTION_BOUNDED_EXIT')
                time.sleep(0.10)
        try:yield
        finally:
            if fcntl is not None:fcntl.flock(f,fcntl.LOCK_UN)
            elif msvcrt is not None:
                f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)

def run_bounded(argv,root,timeout):
    timeout=min(max(1,int(timeout)),600)  # chunks must checkpoint within ten minutes
    flags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
    child=subprocess.Popen(argv,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                           start_new_session=(os.name!='nt'),creationflags=flags)
    try:
        out,err=child.communicate(timeout=timeout)
        return {'returncode':child.returncode,'stdout':out,'stderr':err}
    except subprocess.TimeoutExpired:
        if os.name=='nt':
            try:subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=8)
            except Exception:child.kill()
        else:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        child.communicate()
        raise Incident('EXECUTION_TIMEOUT_PROCESS_TREE_TERMINATED')

def invoke(root,plan_path,expected_plan_sha,verb,route_name=None,proof_path=None,anchor_path=None,anchor_git_blob=None):
    root=pathlib.Path(root).resolve();plan_path=pathlib.Path(plan_path).resolve()
    with mutex(root):
        plan=parse_plan(root,plan_path,expected_plan_sha);sp=root/'QROS_ANTI_STALL_STATE_V2_1.json'
        if verb=='init':
            if sp.exists():
                old=load_state(root)
                if old['plan_sha256']!=expected_plan_sha:raise Incident('FROZEN_PLAN_CHANGED_FOR_EXISTING_LANE')
                revalidate(root,plan,old)
                return {'status':'ALREADY_INITIALIZED','cursor':old['cursor'],'next':plan['stages'][old['cursor']]['id'] if old['cursor']<len(plan['stages']) else None}
            s={'schema':STATE,'lane_id':plan['lane_id'],'authority':plan['authority'],'plan_sha256':expected_plan_sha,'cursor':0,
               'scientific_firewalls':plan['scientific_firewalls'],'stages':[{'id':x['id'],'status':'PENDING','attempted_routes':[],'outputs':[],'remote_evidence':None,'last_error':None} for x in plan['stages']],'events':[]}
            add_event(s,'INIT',authority_sha=expected_plan_sha);save_state(root,s)
            return {'status':'INITIALIZED','cursor':0,'next':plan['stages'][0]['id']}
        s=load_state(root)
        if s['plan_sha256']!=expected_plan_sha:raise Incident('PINNED_PLAN_CHANGED')
        revalidate(root,plan,s)
        if verb=='status':return {'status':'STATUS','lane':s['lane_id'],'cursor':s['cursor'],'next':plan['stages'][s['cursor']]['id'] if s['cursor']<len(plan['stages']) else None,'event_head':s['events'][-1]['event_sha256'],'stages':[{'id':t['id'],'status':t['status'],'attempted_routes':t['attempted_routes']} for t in s['stages']]}
        if s['cursor']==len(s['stages']):return {'status':'DONE_NOOP','cursor':s['cursor']}
        idx=s['cursor'];step=plan['stages'][idx];entry=s['stages'][idx]
        if entry['status']=='HALTED':return {'status':'HALTED','reason':entry['last_error'],'stage':step['id']}
        if verb=='run':
            if step['kind']!='local':return {'status':'EXTERNAL_NEEDS_GIT_ANCHOR_AND_DRIVE_READBACK','stage':step['id']}
            if entry['status']=='RUNNING':return {'status':'INTERRUPTED_FAIL_CLOSED_USE_RECOVER','stage':step['id']}
            if entry['status'] not in ('PENDING','FAILED'):raise Incident('INVALID_RUN_STATE')
            for item in step['inputs']:check_bytes(root,item,True)
            routes=[r for r in step['routes'] if r['name'] not in entry['attempted_routes']]
            if not routes:
                entry['status']='HALTED';entry['last_error']='NO_FROZEN_ALTERNATE_ROUTE';add_event(s,'HALT',step['id'],cause=entry['last_error']);save_state(root,s)
                return {'status':'HALTED_NO_RELAUNCH','stage':step['id']}
            route=next((r for r in routes if r['name']==route_name),None) if route_name else routes[0]
            if route is None:raise Incident('ROUTE_NOT_FROZEN_OR_ALREADY_ATTEMPTED')
            if len(entry['attempted_routes'])>=2:raise Incident('MAX_TWO_DISTINCT_ROUTES')
            entry['attempted_routes'].append(route['name']);entry['status']='RUNNING';add_event(s,'START',step['id'],route=route['name']);save_state(root,s)
            try:
                proc=run_bounded(route['argv'],root,step.get('timeout_seconds',120))
                log={'route':route['name'],'exit':proc['returncode'],'stdout_tail':proc['stdout'][-4000:],'stderr_tail':proc['stderr'][-4000:]}
                if proc['returncode']:raise Incident('EXECUTION_EXIT_'+str(proc['returncode']))
                outs=[check_bytes(root,o) for o in step['outputs']]
                entry['status']='PASS';entry['outputs']=outs;entry['last_error']=None;s['cursor']+=1
                add_event(s,'PASS',step['id'],route=route['name'],outputs=outs,log=log);save_state(root,s)
                return {'status':'ONE_STAGE_PASS','stage':step['id'],'cursor':s['cursor'],'output_sha256':[x['sha256'] for x in outs]}
            except (Exception,subprocess.TimeoutExpired) as exc:
                entry['last_error']=str(exc);entry['status']='FAILED' if len(entry['attempted_routes'])<min(2,len(step['routes'])) else 'HALTED'
                add_event(s,'FAIL',step['id'],route=route['name'],reason=entry['last_error']);save_state(root,s)
                return {'status':'FAILED_ROUTE_SWITCH_REQUIRED' if entry['status']=='FAILED' else 'HALTED_NO_FROZEN_ROUTE','stage':step['id'],'error':entry['last_error']}
        if verb=='recover':
            if step['kind']!='local' or entry['status']!='RUNNING':raise Incident('RECOVER_ONLY_INTERRUPTED_LOCAL_STAGE')
            # Resume only when every expected output SHA was pinned in the original plan.
            outs=[check_bytes(root,item,True) for item in step['outputs']]
            entry['status']='PASS';entry['outputs']=outs;s['cursor']+=1;add_event(s,'RECOVER_VERIFIED_OUTPUT',step['id'],outputs=outs);save_state(root,s)
            return {'status':'ONE_STAGE_RECOVERED','stage':step['id'],'cursor':s['cursor']}
        if verb=='attest':
            if step['kind']!='external':raise Incident('ATTEST_REQUIRES_EXTERNAL_STAGE')
            if not (proof_path and anchor_path and anchor_git_blob):raise Incident('EXTERNAL_ANCHOR_AND_READBACK_REQUIRED')
            assert_hex(anchor_git_blob,40)
            if anchor_git_blob!=step['anchor_git_blob_sha1']:raise Incident('UNPINNED_EXTERNAL_GIT_ANCHOR')
            raw=pathlib.Path(anchor_path).read_bytes()
            if blob_sha(raw)!=anchor_git_blob:raise Incident('GIT_BLOB_PIN_MISMATCH')
            anchor=json.loads(raw);proof=json.loads(pathlib.Path(proof_path).read_bytes())
            if anchor.get('schema')!='QROS_EXTERNAL_OUTPUT_ANCHOR_V1' or anchor.get('lane_id')!=plan['lane_id'] or anchor.get('stage_id')!=step['id']:raise Incident('EXTERNAL_ANCHOR_IDENTITY_MISMATCH')
            if anchor.get('remote_id')!=step['remote_id'] or anchor.get('remote_id')!=proof.get('remote_id'):raise Incident('REMOTE_ID_MISMATCH')
            if proof.get('verified_remote_readback') is not True or proof.get('source')!='GOOGLE_DRIVE_CONNECTED_READBACK':raise Incident('NO_CONNECTED_DRIVE_READBACK')
            outs=[check_bytes(root,item) for item in step['outputs']]
            if outs!=anchor.get('outputs') or len(outs)!=1:raise Incident('OUTPUT_NOT_PINNED_BY_REMOTE_GIT_ANCHOR')
            if proof.get('bytes')!=outs[0]['bytes'] or proof.get('file_name')!=pathlib.PurePosixPath(outs[0]['path']).name:raise Incident('DRIVE_READBACK_SIZE_OR_NAME_MISMATCH')
            entry['status']='PASS';entry['outputs']=outs;entry['remote_evidence']={'anchor_git_blob_sha1':anchor_git_blob,'remote_id':proof['remote_id'],'verified_remote_readback':True};s['cursor']+=1
            add_event(s,'EXTERNAL_PASS',step['id'],outputs=outs,anchor_git_blob_sha1=anchor_git_blob,remote_id=proof['remote_id']);save_state(root,s)
            return {'status':'ONE_EXTERNAL_STAGE_PASS','stage':step['id'],'cursor':s['cursor']}
        raise Incident('UNKNOWN_VERB')

def main():
    p=argparse.ArgumentParser();p.add_argument('verb',choices=['init','status','run','recover','attest']);p.add_argument('--work',required=True);p.add_argument('--plan',required=True);p.add_argument('--expected-plan-sha256',required=True);p.add_argument('--route');p.add_argument('--proof');p.add_argument('--anchor');p.add_argument('--anchor-git-blob');a=p.parse_args()
    try:print(json.dumps(invoke(a.work,a.plan,a.expected_plan_sha256,a.verb,a.route,a.proof,a.anchor,a.anchor_git_blob),sort_keys=True))
    except Exception as ex:print(json.dumps({'status':'FAIL_CLOSED','incident_class':'SCIENTIFIC_DIVERGENCE_OR_AUTHORITY_INVALID','reason':str(ex)},sort_keys=True),file=sys.stderr);raise SystemExit(3)
if __name__=='__main__':main()
