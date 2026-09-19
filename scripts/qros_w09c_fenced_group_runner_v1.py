#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

SCHEMA='QROS_W09C_FENCED_GROUP_WRAPPER_RECEIPT_1.0'
CHUNK=8*1024*1024

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(CHUNK),b''): h.update(b)
    return h.hexdigest()

def git_blob_sha1(p:Path)->str:
    b=p.read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()

def atomic_json(p:Path,obj:dict):
    p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=p.name+'.tmp.',dir=p.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(obj,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def arr_hash(a):
    a=np.ascontiguousarray(a);h=hashlib.sha256();mv=memoryview(a).cast('B')
    for i in range(0,len(mv),CHUNK):h.update(mv[i:i+CHUNK])
    return h.hexdigest()

def indicator_root(npz_path:Path):
    z=np.load(npz_path,allow_pickle=False);d={k:z[k] for k in z.files};h=hashlib.sha256()
    for k in sorted(d):h.update(hashlib.sha256(k.encode()+b'\0'+bytes.fromhex(arr_hash(d[k]))).digest())
    return h.hexdigest()

def bar_root(npy_path:Path):
    a=np.load(npy_path,mmap_mode='r',allow_pickle=False);h=hashlib.sha256();mv=memoryview(np.ascontiguousarray(a)).cast('B')
    for i in range(0,len(mv),CHUNK):h.update(mv[i:i+CHUNK])
    return h.hexdigest()

def validate_source_pins(capsule:dict,source_root:Path):
    checked=[]
    for x in capsule['exact_inputs']:
        p=source_root/x['path']
        if not p.is_file():raise RuntimeError('SOURCE_MISSING:'+x['path'])
        got=git_blob_sha1(p)
        if got!=x['git_blob_sha1']:raise RuntimeError('SOURCE_GIT_BLOB_MISMATCH:'+x['path'])
        checked.append({'path':x['path'],'git_blob_sha1':got})
    return checked

def validate_lease(capsule:dict,lease:dict):
    gi=int(capsule['subject']['structural_group_index'])
    if lease.get('state')!='ACTIVE':raise RuntimeError('LEASE_NOT_ACTIVE')
    if lease.get('group_index')!=gi:raise RuntimeError('LEASE_GROUP_MISMATCH')
    for k in ['job_id','lease_epoch','lease_id','owner_runtime_id','fence_token']:
        if not lease.get(k):raise RuntimeError('LEASE_FIELD_MISSING:'+k)
    bound={k:lease[k] for k in ['job_id','group_index','lease_epoch','owner_runtime_id','lease_id']}
    want=hashlib.sha256(json.dumps(bound,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    if lease['fence_token']!=want:raise RuntimeError('FENCE_TOKEN_INVALID')
    return gi

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--capsule',type=Path,required=True);ap.add_argument('--capsule-blob-sha1',required=True)
    ap.add_argument('--lease',type=Path,required=True);ap.add_argument('--source-root',type=Path,required=True)
    ap.add_argument('--shard-json',type=Path,required=True);ap.add_argument('--ticks',type=Path,required=True)
    ap.add_argument('--bar-root',type=Path,required=True);ap.add_argument('--ind-root',type=Path,required=True)
    ap.add_argument('--point',type=float,required=True);ap.add_argument('--out-dir',type=Path,required=True);ap.add_argument('--receipt',type=Path,required=True)
    a=ap.parse_args();cap=json.loads(a.capsule.read_text());lease=json.loads(a.lease.read_text());gi=validate_lease(cap,lease)
    pins=validate_source_pins(cap,a.source_root)
    if sha256_file(a.ticks)!=cap['preconditions']['dev_prefix_sha256']:raise RuntimeError('DEV_SHA256_MISMATCH')
    asset=cap['subject']['asset'];tf=cap['subject']['timeframe'];side=cap['subject']['side']
    br=bar_root(a.bar_root/f'{asset}_{tf}_BID_BARS.npy')
    if br!=cap['preconditions']['bar_M1_content_sha256']:raise RuntimeError('BAR_ROOT_MISMATCH')
    ir=indicator_root(a.ind_root/f'{asset}_{tf}_INDICATORS.npz')
    if ir!=cap['preconditions']['indicator_M1_content_root_sha256']:raise RuntimeError('INDICATOR_ROOT_MISMATCH')
    worker=a.source_root/'scripts/qros_seed0076_ga1_group_worker_v222.py';a.out_dir.mkdir(parents=True,exist_ok=True);wr=a.out_dir/'group_worker_receipt.json'
    cmd=[sys.executable,str(worker),'--shard-json',str(a.shard_json),'--spec',str(a.source_root/'research/public1000/seed0076/QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json'),'--out-dir',str(a.out_dir),'--receipt',str(wr),'--ticks',str(a.ticks),'--bar-root',str(a.bar_root),'--ind-root',str(a.ind_root),'--point',str(a.point),'--expected-config-root',cap['preconditions']['config_root_sha256'],'--structural-group-index',str(gi)]
    cp=subprocess.run(cmd,capture_output=True,text=True)
    if cp.returncode!=0:raise RuntimeError('WORKER_EXIT_'+str(cp.returncode)+':'+cp.stderr[-500:])
    r=json.loads(wr.read_text())
    exp=cap['pass_criteria']
    for k in ['status','processed_signal_configs','structural_group_index','ordered_config_id_stream_root_sha256','economic_pnl_read','holdout_open']:
        if r.get(k)!=exp.get(k):raise RuntimeError('WORKER_RECEIPT_MISMATCH:'+k)
    arts=r.get('artifacts',[])
    if not arts:raise RuntimeError('WORKER_ARTIFACTS_MISSING')
    for art in arts:
        p=a.out_dir/art['path']
        if not p.is_file() or p.stat().st_size!=art['bytes'] or sha256_file(p)!=art['sha256']:raise RuntimeError('ARTIFACT_REHASH_FAIL:'+art['path'])
    out={'schema':SCHEMA,'status':'PASS','job_id':lease['job_id'],'group_index':gi,'lease_epoch':lease['lease_epoch'],'lease_id':lease['lease_id'],'fence_token':lease['fence_token'],'capsule_blob_sha1':a.capsule_blob_sha1,'processed_signal_configs':r['processed_signal_configs'],'structural_group_index':gi,'ordered_config_id_stream_root_sha256':r['ordered_config_id_stream_root_sha256'],'economic_pnl_read':False,'holdout_open':False,'source_pins':pins,'dev_sha256':cap['preconditions']['dev_prefix_sha256'],'bar_root_sha256':br,'indicator_root_sha256':ir,'worker_receipt_sha256':sha256_file(wr),'worker_result':r,'artifacts':arts}
    atomic_json(a.receipt,out);print(json.dumps({'status':'PASS','job_id':out['job_id'],'group_index':gi,'lease_epoch':out['lease_epoch'],'semantic_root':r.get('semantic_class_root_sha256')},sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
