#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, os, shutil, uuid
from pathlib import Path
import qros_heavy_job_supervisor_v1 as v1
SCHEMA='QROS_HEAVY_JOB_SUPERVISOR_2.0_LOCK_RACE_PATCH'
def _dir_age_seconds(lock:Path)->float:
    st=lock.stat();return max(0.0,dt.datetime.now(dt.timezone.utc).timestamp()-st.st_mtime)
def acquire_controller_lock(job_dir:Path,stale_seconds:int=120)->Path|None:
    lock=job_dir/'.controller.lock';job_dir.mkdir(parents=True,exist_ok=True)
    try:lock.mkdir()
    except FileExistsError:
        owner=lock/'owner.json';parsed=False
        if owner.exists():
            try:
                o=v1.load_json(owner);parsed=True
                if v1.process_alive(int(o.get('pid',-1)),o.get('birth')):return None
            except Exception:parsed=False
        if not parsed:
            try:age=_dir_age_seconds(lock)
            except Exception:return None
            if age<=stale_seconds:return None
        stale=job_dir/(f'.controller.lock.stale.{uuid.uuid4().hex}')
        try:os.replace(lock,stale)
        except OSError:return None
        shutil.rmtree(stale,ignore_errors=True)
        try:lock.mkdir()
        except FileExistsError:return None
    birth=v1.process_birth(os.getpid())
    if birth is None:
        shutil.rmtree(lock,ignore_errors=True);raise RuntimeError('CONTROLLER_PROCESS_BIRTH_UNAVAILABLE_FAIL_CLOSED')
    v1.atomic_write_json(lock/'owner.json',{'pid':os.getpid(),'created_at':v1.utc_now(),'birth':birth,'lock_schema':SCHEMA})
    return lock
v1.acquire_controller_lock=acquire_controller_lock
if __name__=='__main__':raise SystemExit(v1.main())
