#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math, os, re, selectors, shutil, signal, subprocess, sys, time, uuid
from pathlib import Path
from typing import Any

CHUNK=8*1024*1024
SCHEMA='QROS_HEAVY_JOB_SUPERVISOR_3.0_ENGINEERING_CANDIDATE'
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

def acquire_controller_lock(job_dir:Path,stale_seconds:int=120)->int|None:
    # A new, local work root is mandatory. Never migrate a legacy active claim
    # merely by observing another runtime's PID. Do not unlink this inode.
    if not sys.platform.startswith('linux'):
        raise RuntimeError('V3_REQUIRES_LINUX_LOCAL_FILESYSTEM')
    import fcntl
    job_dir.mkdir(parents=True,exist_ok=True)
    if (job_dir/'.controller.lock').exists(): return None
    fd=os.open(job_dir/'.controller.v3.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd);return None
    except BaseException:
        os.close(fd);raise
    return fd

def release_controller_lock(lock:int|None)->None:
    if lock is not None: os.close(lock)

def process_status(pid:int,birth:str|None)->str:
    """Only same-boot, readable /proc evidence can prove local process death."""
    current=process_birth(os.getpid())
    if not isinstance(birth,str) or not current or not birth.startswith('linux:'):
        return 'UNKNOWN'
    if birth.rsplit(':',1)[0]!=current.rsplit(':',1)[0]: return 'FOREIGN_RUNTIME'
    if type(pid) is not int or pid<=0:return 'UNKNOWN'
    try:
        raw=Path(f'/proc/{pid}/stat').read_text()
        rest=raw[raw.rfind(') ')+2:].split()
        if rest[0]=='Z' or rest[19]!=birth.rsplit(':',1)[1]:return 'DEAD'
        return 'ALIVE'
    except FileNotFoundError:return 'DEAD'
    except (OSError,IndexError):return 'UNKNOWN'

def validate_job_spec(spec:dict)->str:
    req={'schema','job_id','command','expected_receipt'}
    miss=req-set(spec)
    if miss: raise RuntimeError('JOB_SPEC_MISSING:'+','.join(sorted(miss)))
    if not isinstance(spec['job_id'],str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',spec['job_id']) or spec['job_id'] in {'.','..'}:
        raise RuntimeError('JOB_ID_INVALID')
    if not isinstance(spec['command'],list) or not spec['command'] or not all(isinstance(x,str) for x in spec['command']):raise RuntimeError('COMMAND_INVALID')
    if not isinstance(spec['expected_receipt'],dict):raise RuntimeError('EXPECTED_RECEIPT_INVALID')
    if int(spec.get('max_attempts',2))<1 or int(spec.get('max_attempts',2))>3:raise RuntimeError('MAX_ATTEMPTS_OUT_OF_RANGE')
    seconds=spec.get('max_runtime_seconds')
    if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<=0:
        raise RuntimeError('FINITE_POSITIVE_MAX_RUNTIME_SECONDS_REQUIRED')
    cap=spec.get('max_log_bytes')
    if type(cap) is not int or not 1<=cap<=1024*1024*1024:
        raise RuntimeError('MAX_LOG_BYTES_REQUIRED_1_TO_1GIB')
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
    if attempt_dir.is_symlink() or rp.is_symlink():return False,'RECEIPT_SYMLINK_FORBIDDEN',None
    if not rp.is_file():return False,'RECEIPT_MISSING',None
    try:r=load_json(rp)
    except Exception as e:return False,'RECEIPT_PARSE_'+type(e).__name__,None
    for k,v in spec['expected_receipt'].items():
        if r.get(k)!=v:return False,f'RECEIPT_EXPECTATION_MISMATCH:{k}',r
    arts=r.get('artifacts')
    if spec.get('artifacts_required',True):
        if not isinstance(arts,list) or not arts:return False,'ARTIFACT_LIST_INVALID',r
        for a in arts:
            if not isinstance(a,dict):return False,'ARTIFACT_ENTRY_INVALID',r
            rel=a.get('path')
            rp_rel=Path(rel) if isinstance(rel,str) else None
            if not isinstance(rel,str) or rp_rel is None or rp_rel.is_absolute() or rel.startswith('/') or '..' in rp_rel.parts:return False,'ARTIFACT_PATH_INVALID',r
            p=attempt_dir/rel
            cursor=attempt_dir
            for part in rp_rel.parts:
                cursor=cursor/part
                if cursor.is_symlink():return False,'ARTIFACT_SYMLINK_FORBIDDEN',r
            if not isinstance(a.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',a['sha256']):return False,'ARTIFACT_HASH_INVALID',r
            if type(a.get('bytes')) is not int or a['bytes']<0:return False,'ARTIFACT_SIZE_INVALID',r
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
           'created_at':utc_now(),'attempt_dir':attempt_dir.name,'command':cmd,'command_sha256':command_sha,
           'spec':spec}
    atomic_write_json(attempt_dir/'claim.json',claim)
    atomic_write_json(job_dir/'current_claim.json',claim)
    return claim

def spawn_bootstrap(script:Path,job_dir:Path,claim:dict)->int:
    attempt_dir=job_dir/claim['attempt_dir']
    out=(attempt_dir/'bootstrap.stdout.txt').open('ab',buffering=0)
    err=(attempt_dir/'bootstrap.stderr.txt').open('ab',buffering=0)
    cmd=[sys.executable,str(script),'--bootstrap','--job-dir',str(job_dir),'--claim-token',claim['claim_token']]
    kwargs={'stdin':subprocess.DEVNULL,'stdout':out,'stderr':err,'close_fds':True,'env':worker_env()}
    if os.name=='posix': kwargs['start_new_session']=True
    elif os.name=='nt': kwargs['creationflags']=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP
    p=subprocess.Popen(cmd,**kwargs)
    out.close();err.close()
    return p.pid

def worker_env()->dict:
    # This reduces inherited secrets; it is not an OS network/filesystem sandbox.
    return {k:v for k,v in os.environ.items() if k in {'PATH','LANG','LC_ALL','TZ','SYSTEMROOT'}}

def run_bounded_worker(cmd:list[str],attempt_dir:Path,spec:dict)->tuple[int,str]:
    deadline=time.monotonic()+spec['max_runtime_seconds']
    cap=spec['max_log_bytes'];written=0
    reason='WORKER_EXIT'
    with selectors.DefaultSelector() as sel, \
         (attempt_dir/'worker.stdout.txt').open('wb') as out, \
         (attempt_dir/'worker.stderr.txt').open('wb') as err:
        p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,close_fds=True,start_new_session=True,env=worker_env())
        try:
            birth=process_birth(p.pid)
            if birth is None:raise RuntimeError('WORKER_PROCESS_BIRTH_UNAVAILABLE_FAIL_CLOSED')
            atomic_write_json(attempt_dir/'worker_identity.json',{'pid':p.pid,'birth':birth,'started_at':utc_now()})
            for pipe,log in ((p.stdout,out),(p.stderr,err)):
                os.set_blocking(pipe.fileno(),False);sel.register(pipe,selectors.EVENT_READ,log)
            while sel.get_map() or p.poll() is None:
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    reason='WORKER_RUNTIME_LIMIT';break
                for key,_ in sel.select(min(remaining,0.05)):
                    data=os.read(key.fileobj.fileno(),65536)
                    if not data:sel.unregister(key.fileobj);key.fileobj.close();continue
                    accepted=data[:max(0,cap-written)]
                    key.data.write(accepted);written+=len(accepted)
                    if len(accepted)!=len(data):reason='WORKER_LOG_LIMIT';break
                if reason!='WORKER_EXIT':break
            if reason!='WORKER_EXIT':
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            rc=p.wait(timeout=2)
            # A deadline/log limit is failure even if the worker concurrently exited 0.
            return (124 if reason=='WORKER_RUNTIME_LIMIT' else 125 if reason=='WORKER_LOG_LIMIT' else rc),reason
        finally:
            # Reap descendants still in our process group, including inherited pipes.
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            p.wait(timeout=2)
            for pipe in (p.stdout,p.stderr):
                if not pipe.closed:pipe.close()

def bootstrap(job_dir:Path,token:str)->int:
    if not sys.platform.startswith('linux'):return 96
    import fcntl
    # Transport retries of the bootstrap itself must not start a second worker.
    claim=load_json(job_dir/'current_claim.json')
    name=claim.get('attempt_dir')
    if claim.get('claim_token')!=token or not isinstance(name,str) or not re.fullmatch(r'attempt_[0-9]{2}',name):return 92
    fd=os.open(job_dir/name/'.bootstrap.v3.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return 96
        # A prior bootstrap may have died after starting its worker. The durable
        # identity prevents reuse of this attempt even when the flock is free.
        if (job_dir/name/'identity.json').exists():return 96
        return _bootstrap_once(job_dir,token)
    finally:os.close(fd)

def _bootstrap_once(job_dir:Path,token:str)->int:
    cp=job_dir/'current_claim.json'
    try:claim=load_json(cp)
    except Exception:return 91
    if claim.get('claim_token')!=token:return 92
    spec=claim.get('spec',{})
    if validate_job_spec(spec)!=claim.get('spec_sha256'):return 98
    if sha256_bytes(canonical(claim.get('command')))!=claim.get('command_sha256'):return 98
    attempt_name=claim.get('attempt_dir')
    if not isinstance(attempt_name,str) or not re.fullmatch(r'attempt_[0-9]{2}',attempt_name): return 97
    attempt_dir=job_dir/attempt_name
    if claim['command']!=expand_command(spec['command'],attempt_dir):return 98
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
    reason='BOOTSTRAP_EXCEPTION'
    try:
        rc,reason=run_bounded_worker(cmd,attempt_dir,spec)
    except Exception as e:
        rc=94
        atomic_write_json(attempt_dir/'bootstrap_exception.json',{'type':type(e).__name__,'message':str(e),'at':utc_now()})
    atomic_write_json(attempt_dir/'exit.json',{'schema':EXIT_SCHEMA,'claim_token':token,'returncode':rc,'ended_at':utc_now(),'reason':reason})
    return int(rc)

def validate_done(done:Path,spec:dict,spec_sha:str)->tuple[bool,str]:
    ok,why,_=validate_receipt(done,spec)
    if not ok:return False,why
    try:
        p=done/'supervisor_receipt.json'
        if p.is_symlink():return False,'SUPERVISOR_RECEIPT_SYMLINK'
        if not p.is_file():return False,'SUPERVISOR_PROVENANCE_MISSING_OR_INVALID'
        meta=load_json(p)
    except (OSError,ValueError):return False,'SUPERVISOR_PROVENANCE_MISSING_OR_INVALID'
    if meta.get('job_id')!=spec['job_id'] or meta.get('spec_sha256')!=spec_sha:
        return False,'DONE_SPEC_IDENTITY_MISMATCH'
    if meta.get('worker_receipt_sha256')!=sha256_file(done/'worker_receipt.json'):
        return False,'DONE_RECEIPT_HASH_MISMATCH'
    return True,'PASS'

def promote_done(job_dir:Path,attempt_dir:Path,spec:dict,spec_sha:str,receipt:dict)->dict:
    done=job_dir/'done'
    if done.exists():
        ok,why=validate_done(done,spec,spec_sha)
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
            ok,why=validate_done(done,spec,spec_sha)
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
            bs=process_status(int(ident['bootstrap_pid']),ident.get('bootstrap_birth'))
            if bs in {'UNKNOWN','FOREIGN_RUNTIME'}:
                return {'state':'FAIL','action':'PROCESS_DEATH_UNPROVEN_FAIL_CLOSED','reason':bs,'job_id':spec['job_id'],'attempt':attempt}
            if bs=='ALIVE':
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
                ws=process_status(wpid,wbirth)
                if ws in {'UNKNOWN','FOREIGN_RUNTIME'}:
                    return {'state':'FAIL','action':'WORKER_DEATH_UNPROVEN_FAIL_CLOSED','reason':ws,'job_id':spec['job_id'],'attempt':attempt}
                if ws=='ALIVE':
                    return {'state':'RUNNING','action':'ADOPT_ORPHAN_WORKER','job_id':spec['job_id'],'attempt':attempt,'worker_pid':wpid}
            if exit_p.exists():
                ex=load_json(exit_p);rc=int(ex.get('returncode',999))
                if ex.get('claim_token')!=claim['claim_token']:
                    return {'state':'FAIL','action':'EXIT_TOKEN_MISMATCH_FAIL_CLOSED','job_id':spec['job_id']}
                ok,why,receipt=validate_receipt(attempt_dir,spec)
                if rc==0 and ok:return promote_done(job_dir,attempt_dir,spec,spec_sha,receipt or {})
                reason=f'WORKER_EXIT_{rc}:{why}'
            else:
                if not worker_identity_p.exists():
                    return {'state':'FAIL','action':'WORKER_LAUNCH_UNKNOWN_FAIL_CLOSED','job_id':spec['job_id']}
                ok,why,receipt=validate_receipt(attempt_dir,spec)
                if ok:
                    # Bootstrap vanished after worker completed but before exit marker. Valid receipt/artifacts are sufficient.
                    return promote_done(job_dir,attempt_dir,spec,spec_sha,receipt or {})
                reason='ORPHANED_BOOTSTRAP_NO_VALID_RECEIPT:'+why
        else:
            age=(dt.datetime.now(dt.timezone.utc)-parse_time(claim['created_at'])).total_seconds()
            if age<=launch_grace:
                return {'state':'RUNNING','action':'PREPARED_WAIT_IDENTITY','job_id':spec['job_id'],'attempt':attempt,'age_seconds':round(age,3)}
            return {'state':'FAIL','action':'PREPARED_LAUNCH_UNKNOWN_FAIL_CLOSED','job_id':spec['job_id'],'attempt':attempt}
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
