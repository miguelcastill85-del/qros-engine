#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, tempfile
from pathlib import Path

SCHEMA='QROS_EXTERNAL_CALL_BUDGET_GUARD_1.0'
HARD_CAP=15
NORMAL_MAX=10
CHECKPOINT_CALL=11
CLOSEOUT_MIN=12

class GuardError(RuntimeError): pass

def atomic_write(path:Path,obj:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.tmp.',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(obj,f,sort_keys=True,separators=(',',':')); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
        if os.name=='posix':
            dfd=os.open(path.parent,os.O_RDONLY)
            try: os.fsync(dfd)
            finally: os.close(dfd)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def load(path:Path)->dict:
    return json.loads(path.read_text(encoding='utf-8'))

def init_state(block_id:str,checkpoint_ref:str)->dict:
    return {'schema':SCHEMA,'block_id':block_id,'hard_cap':HARD_CAP,'normal_max':NORMAL_MAX,'checkpoint_call':CHECKPOINT_CALL,
            'calls_used':0,'checkpoint_ref':checkpoint_ref,'checkpoint_persisted':False,'open_expensive_unit':False,
            'status':'ACTIVE','history':[]}

def decision(st:dict,kind:str)->str:
    used=int(st['calls_used']); nxt=used+1
    if st.get('status')!='ACTIVE': return 'STOP_BLOCK_CLOSED'
    if nxt>HARD_CAP: return 'STOP_HARD_CAP'
    if kind in {'launch','search','explore','new_work'}:
        if nxt>NORMAL_MAX: return 'STOP_NEW_WORK_BUDGET_EXHAUSTED'
        if st.get('open_expensive_unit'): return 'STOP_EXPENSIVE_UNIT_ALREADY_OPEN'
        return 'ALLOW'
    if kind=='checkpoint':
        if nxt>CHECKPOINT_CALL: return 'STOP_CHECKPOINT_TOO_LATE'
        return 'ALLOW'
    if nxt>=CLOSEOUT_MIN and kind not in {'validate','persist','closeout','status'}:
        return 'STOP_CLOSEOUT_ONLY'
    return 'ALLOW'

def record(st:dict,kind:str,success:bool,durable:bool=False)->dict:
    d=decision(st,kind)
    if d!='ALLOW': raise GuardError(d)
    st['calls_used']=int(st['calls_used'])+1
    if kind in {'launch','new_work'} and success: st['open_expensive_unit']=True
    if durable and success:
        st['checkpoint_persisted']=True; st['open_expensive_unit']=False
    st['history'].append({'n':st['calls_used'],'kind':kind,'success':bool(success),'durable':bool(durable)})
    if st['calls_used']>=HARD_CAP: st['status']='BUDGET_EXHAUSTED'
    return st

def close(st:dict)->dict:
    if st.get('open_expensive_unit') and not st.get('checkpoint_persisted'):
        raise GuardError('CANNOT_CLOSE_WITH_UNPERSISTED_EXPENSIVE_UNIT')
    st['status']='CLOSED'; return st

def main()->int:
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('init'); p.add_argument('--state',required=True,type=Path); p.add_argument('--block-id',required=True); p.add_argument('--checkpoint-ref',required=True)
    p=sp.add_parser('decision'); p.add_argument('--state',required=True,type=Path); p.add_argument('--kind',required=True)
    p=sp.add_parser('record'); p.add_argument('--state',required=True,type=Path); p.add_argument('--kind',required=True); p.add_argument('--success',action='store_true'); p.add_argument('--durable',action='store_true')
    p=sp.add_parser('close'); p.add_argument('--state',required=True,type=Path)
    a=ap.parse_args()
    if a.cmd=='init': st=init_state(a.block_id,a.checkpoint_ref); atomic_write(a.state,st); print(json.dumps(st,sort_keys=True)); return 0
    st=load(a.state)
    if a.cmd=='decision': print(decision(st,a.kind)); return 0
    if a.cmd=='record': st=record(st,a.kind,a.success,a.durable); atomic_write(a.state,st); print(json.dumps(st,sort_keys=True)); return 0
    st=close(st); atomic_write(a.state,st); print(json.dumps(st,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
