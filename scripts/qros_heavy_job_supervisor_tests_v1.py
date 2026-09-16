#!/usr/bin/env python3
from __future__ import annotations
import hashlib, importlib.util, json, os, signal, subprocess, sys, tempfile, time
from pathlib import Path

SUP=Path(__file__).resolve().with_name('qros_heavy_job_supervisor_v1.py')

WORKER=r'''#!/usr/bin/env python3
import argparse,hashlib,json,os,sys,time
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--out-dir',required=True);ap.add_argument('--receipt',required=True);ap.add_argument('--counter',required=True);ap.add_argument('--sleep',type=float,default=0.5);ap.add_argument('--mode',default='pass');ap.add_argument('--job-id',required=True)
a=ap.parse_args();out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
with open(a.counter,'a',encoding='utf-8') as f:f.write(str(os.getpid())+'\n');f.flush();os.fsync(f.fileno())
def write_receipt(bad=False):
    art=out/'artifact.bin';art.write_bytes(b'QROS-OK-'+a.job_id.encode());h=hashlib.sha256(art.read_bytes()).hexdigest()
    r={'status':'PASS','job_id':a.job_id,'processed_signal_configs':1,'artifacts':[{'path':'artifact.bin','bytes':art.stat().st_size,'sha256':('0'*64 if bad else h)}]}
    Path(a.receipt).write_text(json.dumps(r,sort_keys=True,indent=2)+'\n',encoding='utf-8')
if a.mode=='fail': time.sleep(a.sleep);sys.exit(7)
if a.mode=='early_receipt': write_receipt(False);time.sleep(a.sleep);sys.exit(0)
time.sleep(a.sleep)
write_receipt(a.mode=='bad_hash')
sys.exit(0)
'''

def load_sup():
    sp=importlib.util.spec_from_file_location('qhs',SUP);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def call(spec:Path,root:Path):
    cp=subprocess.run([sys.executable,str(SUP),'--job-spec',str(spec),'--work-root',str(root),'--launch-grace-seconds','1'],capture_output=True,text=True,timeout=10)
    if not cp.stdout.strip(): raise AssertionError('no supervisor output:'+cp.stderr)
    return cp.returncode,json.loads(cp.stdout.strip().splitlines()[-1])

def make_spec(base:Path,worker:Path,job:str,mode='pass',sleep=0.5,max_attempts=2,extra_expected=None):
    counter=base/f'{job}.counter'
    exp={'status':'PASS','job_id':job}
    if extra_expected:exp.update(extra_expected)
    spec={'schema':'QROS_HEAVY_JOB_SPEC_1.0','job_id':job,'max_attempts':max_attempts,'artifacts_required':True,'expected_receipt':exp,
          'command':[sys.executable,str(worker),'--out-dir','{out_dir}','--receipt','{receipt}','--counter',str(counter),'--sleep',str(sleep),'--mode',mode,'--job-id',job]}
    p=base/f'{job}.json';p.write_text(json.dumps(spec,sort_keys=True,indent=2)+'\n');return p,counter

def count(counter): return len(counter.read_text().splitlines()) if counter.exists() else 0

def poll(spec,root,want,limit=8):
    end=time.time()+limit;last=None
    while time.time()<end:
        _,last=call(spec,root)
        if last['state']==want:return last
        time.sleep(0.08)
    raise AssertionError(f'poll wanted {want}, last={last}')

def wait_file(p:Path,limit=4):
    end=time.time()+limit
    while time.time()<end:
        if p.exists():return
        time.sleep(0.03)
    raise AssertionError('file not found '+str(p))

def main():
    results=[]
    with tempfile.TemporaryDirectory(prefix='qros_hjs_test_') as td:
        base=Path(td);worker=base/'worker.py';worker.write_text(WORKER);root=base/'jobs';root.mkdir()
        # 1 transport retry adopts running; exactly one worker launch.
        spec,c=make_spec(base,worker,'t1',sleep=0.8)
        _,a=call(spec,root);assert a['action']=='LAUNCHED',a
        _,b=call(spec,root);assert b['state']=='RUNNING' and b['action'] in {'ADOPT_LIVE_PROCESS','PREPARED_WAIT_IDENTITY'},b
        r=poll(spec,root,'PASS');assert count(c)==1,(count(c),r);results.append('PASS_transport_retry_exactly_once')
        # 2 concurrent controller calls cannot double launch.
        spec,c=make_spec(base,worker,'t2',sleep=0.8)
        cmd=[sys.executable,str(SUP),'--job-spec',str(spec),'--work-root',str(root),'--launch-grace-seconds','1']
        p1=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);p2=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        o1,e1=p1.communicate(timeout=10);o2,e2=p2.communicate(timeout=10)
        s1=json.loads(o1.strip().splitlines()[-1]);s2=json.loads(o2.strip().splitlines()[-1]);assert {s1['state'],s2['state']} <= {'RUNNING','BUSY'},(s1,s2)
        poll(spec,root,'PASS');assert count(c)==1,count(c);results.append('PASS_concurrent_controller_exactly_once')
        # 3 kill bootstrap only; worker must be adopted, not relaunched.
        spec,c=make_spec(base,worker,'t3',sleep=1.4)
        _,a=call(spec,root);bp=int(a['bootstrap_pid']);job=root/'t3';wait_file(job/'attempt_01'/'worker_identity.json')
        os.kill(bp,signal.SIGKILL);time.sleep(0.08)
        _,b=call(spec,root);assert b['action']=='ADOPT_ORPHAN_WORKER',b;assert count(c)==1,count(c)
        poll(spec,root,'PASS',limit=6);assert count(c)==1,count(c);results.append('PASS_orphan_worker_adopted_no_relaunch')
        # 4 genuine failure retries exactly once then hard fails, no infinite loop.
        spec,c=make_spec(base,worker,'t4',mode='fail',sleep=0.15,max_attempts=2)
        _,a=call(spec,root);assert a['action']=='LAUNCHED'
        end=time.time()+6;seen_retry=False;last=None
        while time.time()<end:
            _,last=call(spec,root)
            if last['action']=='RELAUNCHED_AFTER_PROVEN_DEATH':seen_retry=True
            if last['state']=='FAIL':break
            time.sleep(0.08)
        assert seen_retry and last and last['action']=='RETRY_BUDGET_EXHAUSTED',(seen_retry,last)
        assert count(c)==2,count(c);results.append('PASS_proven_death_one_retry_only')
        # 5 corrupt artifact hash retries once then fail, never promotes done.
        spec,c=make_spec(base,worker,'t5',mode='bad_hash',sleep=0.15,max_attempts=2)
        call(spec,root);last=poll(spec,root,'FAIL',limit=6);assert last['action']=='RETRY_BUDGET_EXHAUSTED',last;assert count(c)==2;assert not (root/'t5'/'done').exists();results.append('PASS_tampered_artifact_fail_closed')
        # 6 capsule/spec drift for same job_id fails closed while live.
        spec,c=make_spec(base,worker,'t6',sleep=1.0);call(spec,root)
        d=json.loads(spec.read_text());d['expected_receipt']['extra']='changed';spec2=base/'t6_changed.json';spec2.write_text(json.dumps(d,sort_keys=True,indent=2)+'\n')
        rc,b=call(spec2,root);assert rc==2 and b['action']=='CAPSULE_MISMATCH_FAIL_CLOSED',b
        poll(spec,root,'PASS');assert count(c)==1;results.append('PASS_capsule_drift_fail_closed')
        # 7 receipt appearing before process exit must not cause early promotion.
        spec,c=make_spec(base,worker,'t7',mode='early_receipt',sleep=0.8);call(spec,root);job=root/'t7';wait_file(job/'attempt_01'/'worker_receipt.json')
        _,b=call(spec,root);assert b['state']=='RUNNING',b;assert not (job/'done').exists();poll(spec,root,'PASS');assert count(c)==1;results.append('PASS_no_early_promotion_while_live')
        # 8 PID reuse defense: wrong birth never counts alive.
        m=load_sup();assert m.process_alive(os.getpid(),'linux:definitely-wrong:0') is False;results.append('PASS_pid_birth_identity_required')
        # 9 running attempt remains present; no active-temp deletion semantics.
        spec,c=make_spec(base,worker,'t9',sleep=0.8);call(spec,root);job=root/'t9';wait_file(job/'attempt_01'/'identity.json');call(spec,root);assert (job/'attempt_01').is_dir();assert not (job/'abandoned').exists();poll(spec,root,'PASS');assert count(c)==1;results.append('PASS_active_attempt_never_deleted')
        # 10 path traversal / unsafe job identity is rejected before touching outside work root.
        bad={'schema':'QROS_HEAVY_JOB_SPEC_1.0','job_id':'../escape','expected_receipt':{},'command':[sys.executable,'-c','print(1)']}
        badp=base/'bad_job.json';badp.write_text(json.dumps(bad)+'\n');rc,b=call(badp,root);assert rc==2 and b['action']=='SUPERVISOR_EXCEPTION_FAIL_CLOSED',b;assert not (base/'escape').exists();results.append('PASS_job_id_traversal_fail_closed')
        # 11 a live controller lock is never stolen merely because wall-clock age is old.
        spec,c=make_spec(base,worker,'t11',sleep=0.1);job=root/'t11';lock=job/'.controller.lock';lock.mkdir(parents=True)
        m.atomic_write_json(lock/'owner.json',{'pid':os.getpid(),'birth':m.process_birth(os.getpid()),'created_at':'2000-01-01T00:00:00Z'})
        _,b=call(spec,root);assert b['state']=='BUSY' and b['action']=='CONTROLLER_LOCK_HELD',b;m.release_controller_lock(lock);results.append('PASS_live_controller_lock_not_time_stolen')
    print(json.dumps({'schema':'QROS_HEAVY_JOB_SUPERVISOR_TESTS_1.0','status':'PASS','tests':results,'count':len(results),'supervisor_sha256':hashlib.sha256(SUP.read_bytes()).hexdigest()},sort_keys=True,indent=2))
if __name__=='__main__': main()
