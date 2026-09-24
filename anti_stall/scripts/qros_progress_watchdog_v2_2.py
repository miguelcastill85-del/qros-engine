#!/usr/bin/env python3
"""Bound one frozen QROS worker by elapsed time AND independently rehashed progress.

This watcher is an engineering scheduler, not a scientific oracle. Progress files
may extend liveness only when they point to NEW, physically present bytes whose
SHA256 is independently recalculated; final promotion remains with v2.1 gates.
"""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, signal, subprocess, sys, time

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def safe(root,relative):
    if not isinstance(relative,str) or not relative or relative.startswith('/') or '\\' in relative or any(x in ('..','.','') for x in relative.split('/')):raise ValueError('BAD_PROGRESS_PATH')
    p=(root/relative).resolve()
    if not p.is_relative_to(root) or not p.is_file():raise ValueError('MISSING_OR_ESCAPED_PROGRESS_OUTPUT')
    return p

def verified_progress(root,progress_file,seen):
    try:
        rec=json.loads(progress_file.read_bytes());seq=rec['sequence'];arr=rec['verified_artifacts']
        if type(seq) is not int or seq<=seen['seq'] or not isinstance(arr,list) or not arr:return False
        changed=False;new_digests=dict(seen['digests'])
        for v in arr:
            path=v['path'];p=safe(root,path)
            if type(v['bytes']) is not int or v['bytes']<0 or p.stat().st_size!=v['bytes'] or sha(p)!=v['sha256']:return False
            if new_digests.get(path)!=v['sha256']:changed=True
            new_digests[path]=v['sha256']
        if not changed:return False  # touching a heartbeat alone cannot buy more time
        seen.update(seq=seq,digests=new_digests)
        return True
    except (ValueError,KeyError,TypeError,AttributeError,OSError,json.JSONDecodeError):return False

def kill_tree(p):
    if p.poll() is not None:return
    if os.name=='nt':
        try:subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],timeout=8,capture_output=True)
        except Exception:p.kill()
    else:
        try:os.killpg(p.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    try:p.wait(timeout=8)
    except subprocess.TimeoutExpired:p.kill();p.wait()

def watch(work,argv,progress_path,max_wall,max_idle,poll=.1):
    root=pathlib.Path(work).resolve();root.mkdir(parents=True,exist_ok=True)
    progress=(root/progress_path).resolve()
    if not progress.is_relative_to(root):raise ValueError('PROGRESS_PATH_ESCAPE')
    if max_wall<=0 or max_wall>600 or max_idle<=0 or max_idle>max_wall:raise ValueError('BAD_TIME_BUDGET')
    log=root/'qros_watchdog_v2_2_worker.log';started=time.monotonic()
    # Startup is bounded too; never confuse interpreter spin-up with a stalled worker.
    # Any startup grace is INCLUDED in the absolute wall-clock deadline.
    startup_grace=min(max_wall*.5,max(.5,max_idle*.1))
    last=started+startup_grace
    seen={'seq':0,'digests':{}}
    if progress.is_file():
        verified_progress(root,progress,seen)  # baseline old receipts; do NOT count as new progress

    with log.open('ab') as f:
        flags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
        p=subprocess.Popen(argv,cwd=root,stdout=f,stderr=subprocess.STDOUT,start_new_session=(os.name!='nt'),creationflags=flags)
        try:
            while True:
                code=p.poll()
                if code is not None:
                    print(json.dumps({'status':'WORKER_EXIT','exit':code,'elapsed_seconds':round(time.monotonic()-started,3),'verified_progress_events':seen['seq']}),flush=True)
                    return code
                now=time.monotonic()
                if progress.is_file() and verified_progress(root,progress,seen):last=now
                reason='WALL_DEADLINE' if now-started>=max_wall else ('NO_VERIFIED_BYTE_PROGRESS' if now-last>=max_idle else None)
                if reason:
                    kill_tree(p)
                    print(json.dumps({'status':'ROUTE_TIMEOUT','reason':reason,'elapsed_seconds':round(now-started,3),'verified_progress_events':seen['seq'],'worker_process_tree_terminated':True,'partial_outputs_preserved':True}),flush=True)
                    return 124
                time.sleep(poll)
        except BaseException:
            kill_tree(p);raise

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',required=True);ap.add_argument('--progress-file',default='qros_verified_progress.json')
    ap.add_argument('--wall',type=float,required=True);ap.add_argument('--idle',type=float,required=True)
    ap.add_argument('cmd',nargs=argparse.REMAINDER);a=ap.parse_args();cmd=a.cmd[1:] if a.cmd and a.cmd[0]=='--' else a.cmd
    if not cmd:ap.error('frozen worker argv required after --')
    raise SystemExit(watch(a.work,cmd,a.progress_file,a.wall,a.idle))
if __name__=='__main__':main()
