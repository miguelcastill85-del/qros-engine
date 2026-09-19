#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, tempfile
from pathlib import Path
SCHEMA='QROS_EXTERNAL_CALL_BUDGET_GUARD_2.0'
HARD_CAP=15; NORMAL_MAX=10; CHECKPOINT_CALL=11; CLOSEOUT_MIN=12
EXPENSIVE_KINDS={'launch','new_work'}
DURABLE_KINDS={'checkpoint','persist'}
CLOSEOUT_KINDS={'validate','persist','closeout','status'}
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

def load(path:Path)->dict:return json.loads(path.read_text(encoding='utf-8'))
def init_state(block_id:str,checkpoint_ref:str)->dict:
    return {'schema':SCHEMA,'block_id':block_id,'hard_cap':HARD_CAP,'normal_max':NORMAL_MAX,'checkpoint_call':CHECKPOINT_CALL,
            'calls_used':0,'checkpoint_ref':checkpoint_ref,'checkpoint_persisted':False,'last_durable_call':None,
            'open_expensive_unit':False,'expensive_units_started':0,'status':'ACTIVE','history':[]}

def decision(st:dict,kind:str)->str:
    used=int(st['calls_used']); nxt=used+1
    if used>=HARD_CAP or nxt>HARD_CAP:return 'STOP_HARD_CAP'
    if st.get('status')!='ACTIVE':return 'STOP_BLOCK_CLOSED'
    if st.get('open_expensive_unit'):
        if nxt>CHECKPOINT_CALL:return 'STOP_CHECKPOINT_DEADLINE_MISSED'
        if nxt==CHECKPOINT_CALL and kind not in DURABLE_KINDS:return 'STOP_CHECKPOINT_REQUIRED_AT_CALL_11'
    if kind in EXPENSIVE_KINDS:
        if nxt>NORMAL_MAX:return 'STOP_NEW_WORK_BUDGET_EXHAUSTED'
        if st.get('open_expensive_unit'):return 'STOP_EXPENSIVE_UNIT_ALREADY_OPEN'
        if int(st.get('expensive_units_started',0))>=1:return 'STOP_SECOND_EXPENSIVE_UNIT_IN_BLOCK'
        return 'ALLOW'
    if kind=='search' or kind=='explore':
        if nxt>NORMAL_MAX:return 'STOP_NEW_WORK_BUDGET_EXHAUSTED'
        return 'ALLOW'
    if kind=='checkpoint':
        if nxt>CHECKPOINT_CALL:return 'STOP_CHECKPOINT_TOO_LATE'
        return 'ALLOW'
    if nxt>=CLOSEOUT_MIN and kind not in CLOSEOUT_KINDS:return 'STOP_CLOSEOUT_ONLY'
    return 'ALLOW'

def record(st:dict,kind:str,success:bool,durable:bool=False)->dict:
    d=decision(st,kind)
    if d!='ALLOW':raise GuardError(d)
    nxt=int(st['calls_used'])+1
    if durable and kind not in DURABLE_KINDS:raise GuardError('DURABLE_FLAG_REQUIRES_CHECKPOINT_OR_PERSIST')
    if st.get('open_expensive_unit') and nxt==CHECKPOINT_CALL and (kind not in DURABLE_KINDS or not durable or not success):
        raise GuardError('CALL_11_MUST_DURABLY_PERSIST_OPEN_EXPENSIVE_UNIT')
    st['calls_used']=nxt
    if kind in EXPENSIVE_KINDS and success:
        st['open_expensive_unit']=True; st['expensive_units_started']=int(st.get('expensive_units_started',0))+1
    if durable and success:
        st['checkpoint_persisted']=True; st['last_durable_call']=nxt; st['open_expensive_unit']=False
    st['history'].append({'n':nxt,'kind':kind,'success':bool(success),'durable':bool(durable)})
    if nxt>=HARD_CAP:st['status']='BUDGET_EXHAUSTED'
    return st

def close(st:dict)->dict:
    if st.get('open_expensive_unit'):raise GuardError('CANNOT_CLOSE_WITH_UNPERSISTED_EXPENSIVE_UNIT')
    st['status']='CLOSED';return st

def main()->int:
    ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('init');p.add_argument('--state',required=True,type=Path);p.add_argument('--block-id',required=True);p.add_argument('--checkpoint-ref',required=True)
    p=sp.add_parser('decision');p.add_argument('--state',required=True,type=Path);p.add_argument('--kind',required=True)
    p=sp.add_parser('record');p.add_argument('--state',required=True,type=Path);p.add_argument('--kind',required=True);p.add_argument('--success',action='store_true');p.add_argument('--durable',action='store_true')
    p=sp.add_parser('close');p.add_argument('--state',required=True,type=Path)
    a=ap.parse_args()
    if a.cmd=='init':st=init_state(a.block_id,a.checkpoint_ref);atomic_write(a.state,st);print(json.dumps(st,sort_keys=True));return 0
    st=load(a.state)
    if a.cmd=='decision':print(decision(st,a.kind));return 0
    if a.cmd=='record':st=record(st,a.kind,a.success,a.durable);atomic_write(a.state,st);print(json.dumps(st,sort_keys=True));return 0
    st=close(st);atomic_write(a.state,st);print(json.dumps(st,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
