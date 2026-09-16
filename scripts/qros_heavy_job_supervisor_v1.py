#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, re, shutil, subprocess, sys, time, uuid
from pathlib import Path
from typing import Any

CHUNK=8*1024*1024
SCHEMA='QROS_HEAVY_JOB_SUPERVISOR_1.0'
CLAIM_SCHEMA='QROS_HEAVY_JOB_CLAIM_1.0'
IDENTITY_SCHEMA='QROS_HEAVY_JOB_BOOTSTRAP_IDENTITY_1.0'
EXIT_SCHEMA='QROS_HEAVY_JOB_EXIT_1.0'


def utc_now()->str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')

def canonical(x:Any)->bytes:
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def sha256_bytes(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(CHUNK),b''): h.update(b)
    return h.hexdigest()

def fsync_dir(p:Path)->None:
    # POSIX supports directory fsync. Windows does not expose equivalent semantics
    # through os.open for directories; file fsync + os.replace remains the safe path.
    if os.name=='nt': return
    fd=os.open(p,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def atomic_write_json(p:Path,obj:dict)->None:
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.tmp.'+uuid.uuid4().hex)
    data=json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False).encode('utf-8')+b'\n'
    with tmp.open('wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,p); fsync_dir(p.parent)

def load_json(p:Path)->dict:
    v=json.loads(p.read_text(encoding='utf-8'))
    if not isinstance(v,dict): raise RuntimeError('JSON_ROOT_NOT_OBJECT:'+str(p))
    return v

def parse_time(s:str)->dt.datetime:
    x=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
    if x.tzinfo is None: raise RuntimeError('NAIVE_TIMESTAMP')
    return x.astimezone(dt.timezone.utc)

def process_birth(pid:int)->str|None:
    if pid<=0: return None
    if os.name=='posix':
        stat=Path(f'/proc/{pid}/stat')
        boot=Path('/proc/sys/kernel/random/boot_id')
        try:
            s=stat.read_text(encoding='utf-8')
            # comm may contain spaces/parens; field 22 is index 19 after final ') '
            rest=s[s.rfind(') ')+2:].split()
            start_ticks=rest[19]
            boot_id=boot.read_text(encoding='utf-8').strip() if boot.exists() else 'unknown'
            return f'linux:{boot_id}:{start_ticks}'
        except Exception:
            return None
    if os.name=='nt':
        try:
            import ctypes
            from ctypes import wintypes
            PROCESS_QUERY_LIMITED_INFORMATION=0x1000
            h=ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,False,pid)
            if not h: return None
            c=e=k=u=wintypes.FILETIME()
            c=wintypes.FILETIME();e=wintypes.FILETIME();k=wintypes.FILETIME();u=wintypes.FILETIME()
            ok=ctypes.windll.kernel32.GetProcessTimes(h,ctypes.byref(c),ctypes.byref(e),ctypes.byref(k),ctypes.byref(u))
            ctypes.windll.kernel32.CloseHandle(h)
            if not ok:return None
            v=(c.dwHighDateTime<<32)|c.dwLowDateTime
            return f'windows:{v}'
        except Exception:
            return None
    return None

def process_alive(pid:int,birth:str|None)->bool:
    if birth is None:return False
    if os.name=='posix':
        try:
            raw=Path(f'/proc/{pid}/stat').read_text(encoding='utf-8')
            rest=raw[raw.rfind(') ')+2:].split()
            if not rest or rest[0]=='Z': return False
        except Exception:
            return False
    return process_birth(pid)==birth

def acquire_controller_lock(job_dir:Path,stale_seconds:int=120)->Path|None:
    lock=job_dir/'.controller.lock'
    job_dir.mkdir(parents=True,exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError:
        owner=lock/'owner.json'
        try:
            o=load_json(owner); age=(dt.datetime.now(dt.timezone.utc)-parse_time(o['created_at'])).total_seconds()
            if process_alive(int(o.get('pid',-1)),o.get('birth')): return None
        except Exception:
            age=stale_seconds+1
        # A dead owner can be reclaimed immediately. For unreadable legacy locks,
        # require the stale-time threshold before takeover.
        if not owner.exists() and age<=stale_seconds:return None
        stale=job_dir/(f'.controller.lock.stale.{uuid.uuid4().hex}')
        try: os.replace(lock,stale)
        except OSError:return None
        shutil.rmtree(stale,ignore_errors=True)
        try: lock.mkdir()
        except FileExistsError:return None
    atomic_write_json(lock/'owner.json',{'pid':os.getpid(),'created_at':utc_now(),'birth':process_birth(os.getpid())})
    return lock

def release_controller_lock(lock:Path|None)->None:
    if lock is not None: shutil.rmtree(lock,ignore_errors=True)

def validate_job_spec(spec:dict)->str:
    req={'schema','job_id','command','expected_receipt'}
    miss=req-set(spec)
    if miss: raise RuntimeError('JOB_SPEC_MISSING:'+','.join(sorted(miss)))
    if not isinstance(spec['job_id'],str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',spec['job_id']) or spec['job_id'] in {'.','..'}:
        raise RuntimeError('JOB_ID_INVALID')
    if not isinstance(spec['command'],list) or not spec['command'] or not all(isinstance(x,str) for x in spec['command']):raise RuntimeError('COMMAND_INVALID')
    if not isinstance(spec['expected_receipt'],dict):raise RuntimeError('EXPECTED_RECEIPT_INVALID')
    if int(spec.get('max_attempts',2))<1 or int(spec.get('max_attempts',2))>3:raise RuntimeError('MAX_ATTEMPTS_OUT_OF_RANGE')
    return sha256_bytes(canonical(spec))

def expand_command(command:list[str],attempt_dir:Path)->list[str]:
    receipt=attempt_dir/'worker_receipt.json'
    repl={'{attempt_dir}':str(attempt_dir),'{out_dir}':str(attempt_dir),'{receipt}':str(receipt)}
    out=[]
    for arg in command:
        for k,v in repl.items():arg=arg.replace(k,v)
        out.append(arg)
    return out

def validate_receipt(attempt_dir:Path,spec:dict)->tuple[bool,str,dict|None]:
    rp=attempt_dir/'worker_receipt.json'
    if not rp.is_file():return False,'RECEIPT_MISSING',None
    try:r=load_json(rp)
    except Exception as e:return False,'RECEIPT_PARSE_'+type(e).__name__,None
    for k,v in spec['expected_receipt'].items():
        if r.get(k)!=v:return False,f'RECEIPT_EXPECTATION_MISMATCH:{k}',r
    arts=r.get('artifacts')
    if spec.get('artifacts_required',True):
        if not isinstance(arts,list) or not arts:return False,'ARTIFACT_LIST_INVALID',r
        for a in arts:
            rel=a.get('path')
            rp_rel=Path(rel) if isinstance(rel,str) else None
            if not isinstance(rel,str) or rp_rel is None or rp_rel.is_absolute() or rel.startswith('/') or '..' in rp_rel.parts:return False,'ARTIFACT_PATH_INVALID',r
            p=attempt_dir/rel
            if not p.is_file():return False,'ARTIFACT_MISSING:'+rel,r
            if p.stat().st_size!=a.get('bytes'):return False,'ARTIFACT_SIZE_MISMATCH:'+rel,r
            if sha256_file(p)!=a.get('sha256'):return False,'ARTIFACT_SHA_MISMATCH:'+rel,r
    return True,'PASS',r

def archive_attempt(job_dir:Path,attempt_dir:Path,reason:str)->None:
    if not attempt_dir.exists():return
    ab=job_dir/'abandoned';ab.mkdir(exist_ok=True)
    target=ab/(attempt_dir.name+'.'+reason+'.'+uuid.uuid4().hex[:8])
    os.replace(attempt_dir,target);fsync_dir(ab)

def make_claim(job_dir:Path,spec:dict,spec_sha:str,attempt:int)->dict:
    attempt_dir=job_dir/f'attempt_{attempt:02d}'
    attempt_dir.mkdir(parents=True,exist_ok=False)
    token=uuid.uuid4().hex
    cmd=expand_command(spec['command'],attempt_dir)
    command_sha=sha256_bytes(canonical(cmd))
    claim={'schema':CLAIM_SCHEMA,'job_id':spec['job_id'],'spec_sha256':spec_sha,'attempt':attempt,'claim_token':token,
           'created_at':utc_now(),'attempt_dir':attempt_dir.name,'command':cmd,'command_sha256':command_sha}
    atomic_write_json(attempt_dir/'claim.json',claim)
    atomic_write_json(job_dir/'current_claim.json',claim)
    return claim

def spawn_bootstrap(script:Path,job_dir:Path,claim:dict)->int:
    attempt_dir=job_dir/claim['attempt_dir']
    out=(attempt_dir/'bootstrap.stdout.txt').open('ab',buffering=0)
    err=(attempt_dir/'bootstrap.stderr.txt').open('ab',buffering=0)
    cmd=[sys.executable,str(script),'--bootstrap','--job-dir',str(job_dir),'--claim-token',claim['claim_token']]
    kwargs={'stdin':subprocess.DEVNULL,'stdout':out,'stderr':err,'close_fds':True}
    if os.name=='posix': kwargs['start_new_session']=True
    elif os.name=='nt': kwargs['creationflags']=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP
    p=subprocess.Popen(cmd,**kwargs)
    out.close();err.close()
    return p.pid

def bootstrap(job_dir:Path,token:str)->int:
    cp=job_dir/'current_claim.json'
    try:claim=load_json(cp)
    except Exception:return 91
    if claim.get('claim_token')!=token:return 92
    attempt_name=claim.get('attempt_dir')
    if not isinstance(attempt_name,str) or not re.fullmatch(r'attempt_[0-9]{2}',attempt_name): return 97
    attempt_dir=job_dir/attempt_name
    bbirth=process_birth(os.getpid())
    if bbirth is None:
        atomic_write_json(attempt_dir/'exit.json',{'schema':EXIT_SCHEMA,'claim_token':token,'returncode':95,'ended_at':utc_now(),'reason':'BOOTSTRAP_PROCESS_BIRTH_UNAVAILABLE_FAIL_CLOSED'})
        return 95
    identity={'schema':IDENTITY_SCHEMA,'job_id':claim['job_id'],'claim_token':token,'attempt':claim['attempt'],
              'bootstrap_pid':os.getpid(),'bootstrap_birth':bbirth,'started_at':utc_now(),
              'command_sha256':claim['command_sha256']}
    atomic_write_json(attempt_dir/'identity.json',identity)
    # Re-check ownership after identity became durable. A stale takeover must not race us.
    claim2=load_json(cp)
    if claim2.get('claim_token')!=token:
        atomic_write_json(attempt_dir/'exit.json',{'schema':EXIT_SCHEMA,'claim_token':token,'returncode':93,'ended_at':utc_now(),'reason':'CLAIM_SUPERSEDED_BEFORE_WORKER_START'})
        return 93
    cmd=claim['command']
    stdout=(attempt_dir/'worker.stdout.txt').open('ab',buffering=0)
    stderr=(attempt_dir/'worker.stderr.txt').open('ab',buffering=0)
    try:
        p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,close_fds=True)
        wbirth=process_birth(p.pid)
        if wbirth is None:
            try: p.terminate()
            except Exception: pass
            try: p.wait(timeout=5)
            except Exception:
                try: p.kill()
                except Exception: pass
            raise RuntimeError('WORKER_PROCESS_BIRTH_UNAVAILABLE_FAIL_CLOSED')
        worker={'pid':p.pid,'birth':wbirth,'started_at':utc_now()}
        atomic_write_json(attempt_dir/'worker_identity.json',worker)
        rc=p.wait()
    except Exception as e:
        rc=94
        atomic_write_json(attempt_dir/'bootstrap_exception.json',{'type':type(e).__name__,'message':str(e),'at':utc_now()})
    finally:
        stdout.close();stderr.close()
    atomic_write_json(attempt_dir/'exit.json',{'schema':EXIT_SCHEMA,'claim_token':token,'returncode':rc,'ended_at':utc_now()})
    return int(rc)

def promote_done(job_dir:Path,attempt_dir:Path,spec:dict,spec_sha:str,receipt:dict)->dict:
    done=job_dir/'done'
    if done.exists():
        ok,why,_=validate_receipt(done,spec)
        if ok:return {'state':'PASS','action':'REUSE_VALID_DONE','job_id':spec['job_id'],'spec_sha256':spec_sha}
        raise RuntimeError('INVALID_EXISTING_DONE:'+why)
    # Attach supervisor provenance after worker artifacts are frozen, outside worker receipt.
    meta={'schema':SCHEMA,'job_id':spec['job_id'],'spec_sha256':spec_sha,'promoted_at':utc_now(),
          'attempt':int(attempt_dir.name.split('_')[-1]),'worker_receipt_sha256':sha256_file(attempt_dir/'worker_receipt.json')}
    atomic_write_json(attempt_dir/'supervisor_receipt.json',meta)
    for p in attempt_dir.rglob('*'):
        if p.is_file():
            with p.open('rb') as f: os.fsync(f.fileno())
    fsync_dir(attempt_dir)
    os.replace(attempt_dir,done);fsync_dir(job_dir)
    atomic_write_json(job_dir/'state.json',{'schema':SCHEMA,'job_id':spec['job_id'],'spec_sha256':spec_sha,'state':'PASS','done_at':utc_now(),'attempt':meta['attempt']})
    return {'state':'PASS','action':'PROMOTE_ATOMIC_DONE','job_id':spec['job_id'],'spec_sha256':spec_sha,'attempt':meta['attempt']}

def controller(script:Path,spec_path:Path,work_root:Path,launch_grace:int)->dict:
    spec=load_json(spec_path);spec_sha=validate_job_spec(spec)
    job_dir=work_root/spec['job_id'];job_dir.mkdir(parents=True,exist_ok=True)
    lock=acquire_controller_lock(job_dir)
    if lock is None:return {'state':'BUSY','action':'CONTROLLER_LOCK_HELD','job_id':spec['job_id']}
    try:
        done=job_dir/'done'
        if done.exists():
            ok,why,_=validate_receipt(done,spec)
            if not ok:return {'state':'FAIL','action':'DONE_INVALID','reason':why,'job_id':spec['job_id']}
            return {'state':'PASS','action':'REUSE_VALID_DONE','job_id':spec['job_id'],'spec_sha256':spec_sha}
        cp=job_dir/'current_claim.json'
        if not cp.exists():
            claim=make_claim(job_dir,spec,spec_sha,1);pid=spawn_bootstrap(script,job_dir,claim)
            return {'state':'RUNNING','action':'LAUNCHED','job_id':spec['job_id'],'attempt':1,'bootstrap_pid':pid,'spec_sha256':spec_sha}
        claim=load_json(cp)
        if claim.get('spec_sha256')!=spec_sha:
            return {'state':'FAIL','action':'CAPSULE_MISMATCH_FAIL_CLOSED','job_id':spec['job_id'],'claimed_spec_sha256':claim.get('spec_sha256'),'requested_spec_sha256':spec_sha}
        attempt=int(claim['attempt']);attempt_name=claim.get('attempt_dir')
        if not isinstance(attempt_name,str) or not re.fullmatch(r'attempt_[0-9]{2}',attempt_name):
            return {'state':'FAIL','action':'CLAIM_PATH_INVALID_FAIL_CLOSED','job_id':spec['job_id'],'attempt':attempt}
        attempt_dir=job_dir/attempt_name;identity_p=attempt_dir/'identity.json';exit_p=attempt_dir/'exit.json'
        if identity_p.exists():
            ident=load_json(identity_p)
            if ident.get('claim_token')!=claim['claim_token'] or ident.get('command_sha256')!=claim['command_sha256']:
                return {'state':'FAIL','action':'IDENTITY_MISMATCH_FAIL_CLOSED','job_id':spec['job_id'],'attempt':attempt}
            if process_alive(int(ident['bootstrap_pid']),ident.get('bootstrap_birth')):
                return {'state':'RUNNING','action':'ADOPT_LIVE_PROCESS','job_id':spec['job_id'],'attempt':attempt,'bootstrap_pid':ident['bootstrap_pid']}
            # Bootstrap may die while the heavy worker survives. Never infer worker death
            # from bootstrap death: adopt the exact worker by PID + process-birth identity.
            worker_identity_p=attempt_dir/'worker_identity.json'
            if worker_identity_p.exists():
                try:
                    wid=load_json(worker_identity_p)
                    wpid=int(wid['pid']);wbirth=wid.get('birth')
                except Exception:
                    return {'state':'FAIL','action':'WORKER_IDENTITY_INVALID_FAIL_CLOSED','job_id':spec['job_id'],'attempt':attempt}
                if process_alive(wpid,wbirth):
                    return {'state':'RUNNING','action':'ADOPT_ORPHAN_WORKER','job_id':spec['job_id'],'attempt':attempt,'worker_pid':wpid}
            if exit_p.exists():
                ex=load_json(exit_p);rc=int(ex.get('returncode',999))
                ok,why,receipt=validate_receipt(attempt_dir,spec)
                if rc==0 and ok:return promote_done(job_dir,attempt_dir,spec,spec_sha,receipt or {})
                reason=f'WORKER_EXIT_{rc}:{why}'
            else:
                ok,why,receipt=validate_receipt(attempt_dir,spec)
                if ok:
                    # Bootstrap vanished after worker completed but before exit marker. Valid receipt/artifacts are sufficient.
                    return promote_done(job_dir,attempt_dir,spec,spec_sha,receipt or {})
                reason='ORPHANED_BOOTSTRAP_NO_VALID_RECEIPT:'+why
        else:
            age=(dt.datetime.now(dt.timezone.utc)-parse_time(claim['created_at'])).total_seconds()
            if age<=launch_grace:
                return {'state':'RUNNING','action':'PREPARED_WAIT_IDENTITY','job_id':spec['job_id'],'attempt':attempt,'age_seconds':round(age,3)}
            reason='STALE_PREPARED_NO_IDENTITY'
        max_attempts=int(spec.get('max_attempts',2))
        if attempt>=max_attempts:
            atomic_write_json(job_dir/'state.json',{'schema':SCHEMA,'job_id':spec['job_id'],'spec_sha256':spec_sha,'state':'FAIL','reason':reason,'attempt':attempt,'failed_at':utc_now()})
            return {'state':'FAIL','action':'RETRY_BUDGET_EXHAUSTED','job_id':spec['job_id'],'attempt':attempt,'reason':reason}
        archive_attempt(job_dir,attempt_dir,'attempt_failed')
        claim2=make_claim(job_dir,spec,spec_sha,attempt+1);pid=spawn_bootstrap(script,job_dir,claim2)
        return {'state':'RUNNING','action':'RELAUNCHED_AFTER_PROVEN_DEATH','job_id':spec['job_id'],'attempt':attempt+1,'bootstrap_pid':pid,'previous_reason':reason}
    finally:
        release_controller_lock(lock)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--bootstrap',action='store_true')
    ap.add_argument('--job-dir',type=Path);ap.add_argument('--claim-token')
    ap.add_argument('--job-spec',type=Path);ap.add_argument('--work-root',type=Path);ap.add_argument('--launch-grace-seconds',type=int,default=30)
    a=ap.parse_args()
    if a.bootstrap:
        if not a.job_dir or not a.claim_token:return 90
        return bootstrap(a.job_dir,a.claim_token)
    if not a.job_spec or not a.work_root:ap.error('--job-spec and --work-root are required')
    try:
        out=controller(Path(__file__).resolve(),a.job_spec,a.work_root,a.launch_grace_seconds)
    except Exception as e:
        out={'state':'FAIL','action':'SUPERVISOR_EXCEPTION_FAIL_CLOSED','reason':f'{type(e).__name__}:{e}'}
    print(json.dumps(out,sort_keys=True,separators=(',',':')))
    return 0 if out['state'] in {'PASS','RUNNING','BUSY'} else 2
if __name__=='__main__':raise SystemExit(main())
