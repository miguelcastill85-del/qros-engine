#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, tempfile, time
from pathlib import Path

SCHEMA='QROS_NO_FREEZE_BARRIER_1.0'
TERMINAL={'PASS','RUNNING_ADOPTABLE','FAIL_CLOSED','PENDING_NOT_STARTED'}
DEFAULT_TIMEOUT=5.0

class BarrierError(RuntimeError): pass

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def sha256_file(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def atomic_write(path:Path,obj:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.tmp.',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(obj,f,sort_keys=True,indent=2,ensure_ascii=False);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
        if os.name=='posix':
            dfd=os.open(path.parent,os.O_RDONLY)
            try:os.fsync(dfd)
            finally:os.close(dfd)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def load(path:Path):
    x=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(x,dict):raise BarrierError('STATE_NOT_OBJECT')
    return x

def job_spec_sha(path:Path):
    spec=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(spec,dict):raise BarrierError('JOB_SPEC_NOT_OBJECT')
    return hashlib.sha256(canonical(spec)).hexdigest(), spec

def init_state(state:Path,job_spec:Path,work_root:Path,supervisor:Path):
    spec_sha,spec=job_spec_sha(job_spec)
    jid=spec.get('job_id')
    if not isinstance(jid,str) or not jid:raise BarrierError('JOB_ID_MISSING')
    st={'schema':SCHEMA,'status':'PENDING_NOT_STARTED','job_id':jid,'job_spec_sha256':spec_sha,
        'job_spec_path':str(job_spec.resolve()),'work_root':str(work_root.resolve()),
        'supervisor_path':str(supervisor.resolve()),'supervisor_sha256':sha256_file(supervisor),
        'launch_attempted':False,'supervisor_calls':0,'last_supervisor':None,'updated_monotonic_ns':time.monotonic_ns()}
    atomic_write(state,st);return st

def verify_identity(st,job_spec,work_root,supervisor):
    spec_sha,spec=job_spec_sha(job_spec)
    if st.get('job_spec_sha256')!=spec_sha:raise BarrierError('JOB_SPEC_DRIFT_FAIL_CLOSED')
    if st.get('job_id')!=spec.get('job_id'):raise BarrierError('JOB_ID_DRIFT_FAIL_CLOSED')
    if st.get('work_root')!=str(work_root.resolve()):raise BarrierError('WORK_ROOT_DRIFT_FAIL_CLOSED')
    if st.get('supervisor_sha256')!=sha256_file(supervisor):raise BarrierError('SUPERVISOR_DRIFT_FAIL_CLOSED')

def call_supervisor(supervisor:Path,job_spec:Path,work_root:Path,timeout_s:float):
    cmd=[sys.executable,str(supervisor),'--job-spec',str(job_spec),'--work-root',str(work_root),'--launch-grace-seconds','1']
    t0=time.monotonic()
    try:
        cp=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {'state':'CONTROL_TIMEOUT','action':'FAIL_CLOSED_NONBLOCKING_TIMEOUT','elapsed_s':round(time.monotonic()-t0,6)}
    elapsed=round(time.monotonic()-t0,6)
    lines=[x for x in cp.stdout.splitlines() if x.strip()]
    if not lines:
        return {'state':'CONTROL_ERROR','action':'FAIL_CLOSED_NO_SUPERVISOR_JSON','returncode':cp.returncode,'stderr':cp.stderr[-500:],'elapsed_s':elapsed}
    try:out=json.loads(lines[-1])
    except Exception:
        return {'state':'CONTROL_ERROR','action':'FAIL_CLOSED_BAD_SUPERVISOR_JSON','returncode':cp.returncode,'tail':lines[-1][-500:],'elapsed_s':elapsed}
    out=dict(out);out['returncode']=cp.returncode;out['elapsed_s']=elapsed;return out

def map_state(out:dict,work_root:Path,job_id:str):
    s=out.get('state')
    if s=='PASS':return 'PASS',None
    if s in {'RUNNING','BUSY'}:
        job_dir=work_root/job_id
        claim=job_dir/'current_claim.json'
        if not claim.is_file():return 'FAIL_CLOSED','RUNNING_WITHOUT_DURABLE_CLAIM'
        try:c=json.loads(claim.read_text(encoding='utf-8'))
        except Exception:return 'FAIL_CLOSED','DURABLE_CLAIM_UNREADABLE'
        if c.get('job_id')!=job_id:return 'FAIL_CLOSED','DURABLE_CLAIM_JOB_MISMATCH'
        return 'RUNNING_ADOPTABLE',None
    return 'FAIL_CLOSED',out.get('action') or out.get('reason') or 'SUPERVISOR_FAILED'

def probe(state:Path,job_spec:Path,work_root:Path,supervisor:Path,timeout_s:float,allow_launch:bool):
    st=load(state)
    try:
        verify_identity(st,job_spec,work_root,supervisor)
    except Exception as e:
        st['status']='FAIL_CLOSED'; st['failure_reason']=f'{type(e).__name__}:{e}'; st['updated_monotonic_ns']=time.monotonic_ns(); atomic_write(state,st); return st
    if st['status']=='PASS':return st
    if st['status']=='FAIL_CLOSED':return st
    if st['status']=='RUNNING_ADOPTABLE' and allow_launch:
        pass
    elif st['status']=='PENDING_NOT_STARTED' and not allow_launch:
        return st
    out=call_supervisor(supervisor,job_spec,work_root,timeout_s)
    st['supervisor_calls']=int(st.get('supervisor_calls',0))+1
    st['last_supervisor']=out
    st['launch_attempted']=True
    mapped,why=map_state(out,work_root,st['job_id'])
    st['status']=mapped
    st['failure_reason']=why
    st['updated_monotonic_ns']=time.monotonic_ns()
    atomic_write(state,st);return st

def close_check(state:Path):
    st=load(state)
    if st.get('status') not in TERMINAL:raise BarrierError('TURN_CLOSE_FORBIDDEN_NONTERMINAL:'+str(st.get('status')))
    if st.get('status')=='RUNNING_ADOPTABLE':
        claim=Path(st['work_root'])/st['job_id']/'current_claim.json'
        if not claim.is_file():raise BarrierError('TURN_CLOSE_FORBIDDEN_RUNNING_WITHOUT_CLAIM')
    return st

def main():
    ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('init');p.add_argument('--state',type=Path,required=True);p.add_argument('--job-spec',type=Path,required=True);p.add_argument('--work-root',type=Path,required=True);p.add_argument('--supervisor',type=Path,required=True)
    p=sp.add_parser('launch-or-adopt');p.add_argument('--state',type=Path,required=True);p.add_argument('--job-spec',type=Path,required=True);p.add_argument('--work-root',type=Path,required=True);p.add_argument('--supervisor',type=Path,required=True);p.add_argument('--timeout-seconds',type=float,default=DEFAULT_TIMEOUT)
    p=sp.add_parser('status');p.add_argument('--state',type=Path,required=True);p.add_argument('--job-spec',type=Path,required=True);p.add_argument('--work-root',type=Path,required=True);p.add_argument('--supervisor',type=Path,required=True);p.add_argument('--timeout-seconds',type=float,default=DEFAULT_TIMEOUT)
    p=sp.add_parser('close-check');p.add_argument('--state',type=Path,required=True)
    a=ap.parse_args()
    try:
        if a.cmd=='init':out=init_state(a.state,a.job_spec,a.work_root,a.supervisor)
        elif a.cmd=='launch-or-adopt':out=probe(a.state,a.job_spec,a.work_root,a.supervisor,a.timeout_seconds,True)
        elif a.cmd=='status':out=probe(a.state,a.job_spec,a.work_root,a.supervisor,a.timeout_seconds,True)
        else:out=close_check(a.state)
        print(json.dumps(out,sort_keys=True,separators=(',',':')));return 0 if out.get('status') in TERMINAL else 2
    except Exception as e:
        out={'schema':SCHEMA,'status':'FAIL_CLOSED','failure_reason':f'{type(e).__name__}:{e}'}
        try:
            if hasattr(a,'state'):atomic_write(a.state,out)
        except Exception:pass
        print(json.dumps(out,sort_keys=True,separators=(',',':')));return 2
if __name__=='__main__':raise SystemExit(main())
