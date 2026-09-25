#!/usr/bin/env python3
"""Executable, bounded QROS continuation over immutable v2.2 queues.

One local invocation *actually runs* all dependency-safe stages it can finish,
not just writes the next instruction. Resume is byte-checked and crash-safe.
External/blocked science remains closed. No network, holdout or economic authority.
"""
from __future__ import annotations
import argparse, contextlib, hashlib, json, os, pathlib, sys, time
try:
    import fcntl
except ImportError:
    fcntl = None
try:
    import msvcrt
except ImportError:
    msvcrt = None
from qros_anti_stall_v2_1 import Incident, atomic_json, canonical, digest, invoke, parse_plan, check_bytes
from qros_continuation_dispatch_v2_2 import queue_load, snapshot, dispatch

SCHEMA = 'QROS_CONTINUATION_ENGINE_V2_3_RECEIPT'
CHECKPOINT = 'QROS_CONTINUATION_ENGINE_V2_3_CHECKPOINT.json'

@contextlib.contextmanager
def engine_lock(control, timeout=8):
    """Separate global lock: dispatcher/v2.1 hold their own nested lock."""
    control.mkdir(parents=True, exist_ok=True)
    lock = control/'.qros_engine_v2_3.lock'
    with lock.open('a+b') as f:
        if msvcrt is not None:
            f.seek(0); f.write(b'0'); f.flush()
        end = time.monotonic()+min(max(timeout,.1),8)
        while True:
            try:
                if fcntl is not None: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
                elif msvcrt is not None:
                    f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
                else: raise Incident('NO_OS_PROCESS_LOCK_AVAILABLE')
                break
            except (OSError,BlockingIOError):
                if time.monotonic()>end: raise Incident('CONTINUATION_ENGINE_ALREADY_RUNNING')
                time.sleep(.05)
        try: yield
        finally:
            if fcntl is not None: fcntl.flock(f,fcntl.LOCK_UN)
            elif msvcrt is not None:
                f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)

def checkpoint_read(control,queue_sha,authority):
    path=control/CHECKPOINT
    if not path.exists():
        return {'schema':SCHEMA,'queue_sha256':queue_sha,'authority':authority,
                'sequence':0,'completed_jobs':[],'last_result':None,'history':[]}
    x=json.loads(path.read_bytes())
    sig=x.pop('self_sha256',None)
    if not isinstance(sig,str) or digest(canonical(x))!=sig:
        raise Incident('ENGINE_CHECKPOINT_HASH_DRIFT')
    if x.get('schema')!=SCHEMA or x.get('queue_sha256')!=queue_sha or x.get('authority')!=authority:
        raise Incident('ENGINE_CHECKPOINT_AUTHORITY_MISMATCH')
    prev='0'*64
    for i,e in enumerate(x.get('history',[]),1):
        if e.get('sequence')!=i or e.get('previous_sha256')!=prev:
            raise Incident('ENGINE_RECEIPT_CHAIN_DRIFT')
        d={k:v for k,v in e.items() if k!='event_sha256'}
        if digest(canonical(d))!=e.get('event_sha256'):
            raise Incident('ENGINE_RECEIPT_HASH_DRIFT')
        prev=e['event_sha256']
    if x['sequence']!=len(x['history']):raise Incident('ENGINE_COUNTER_DRIFT')
    return x

def persist(control,state,reason,rows):
    """Re-read local per-stage receipts before making a durable claim."""
    passed=[name for name,row in rows.items() if row['state']=='PASS']
    for name in state['completed_jobs']:
        if name not in passed:raise Incident('PREVIOUS_COMPLETION_REVOKED')
    head=state['history'][-1]['event_sha256'] if state['history'] else '0'*64
    event={'sequence':state['sequence']+1,'previous_sha256':head,'reason':reason,
           'completed_jobs':passed,'blocked_jobs':[k for k,v in rows.items() if v['state']!='PASS']}
    event['event_sha256']=digest(canonical(event))
    state['history'].append(event);state['sequence']+=1
    state['completed_jobs']=passed;state['last_result']=reason
    atomic_json(control/CHECKPOINT,{**state,'self_sha256':digest(canonical(state))})

def recover_prepinned(q,rows,remaining_seconds):
    """An interrupted worker may only be promoted using ORIGINAL expected SHA/bytes.

    Missing/unknown bytes: fail closed, no second execution of a possibly
    already started economic task. The next independent queue item may proceed.
    """
    changes=[]
    for j in q['jobs']:
        if rows[j['id']]['state']!='RUNNING':continue
        stage=parse_plan(pathlib.Path(j['work']).resolve(),j['plan'],j['plan_sha256'])['stages'][0]
        if stage['kind']!='local' or any(out.get('sha256') is None or out.get('bytes') is None for out in stage['outputs']):
            changes.append({'job':j['id'],'status':'INTERRUPTED_UNPINNED_OUTPUTS_NO_RERUN'});continue
        try:
            if remaining_seconds()<2:break
            for out in stage['outputs']:check_bytes(pathlib.Path(j['work']).resolve(),out,True)
            result=invoke(j['work'],j['plan'],j['plan_sha256'],'recover')
            if result.get('status')!='ONE_STAGE_RECOVERED':raise Incident('RECOVERY_NOT_CONFIRMED')
            changes.append({'job':j['id'],'status':'INDEPENDENTLY_PREPINNED_RECOVERED'})
        except (Incident,OSError,KeyError,ValueError) as e:
            changes.append({'job':j['id'],'status':'RECOVERY_NOT_PROVEN_NO_RERUN','error':str(e)})
    return changes

def run(queue_file,expected_queue_sha256,max_seconds=180,max_stages=5):
    if not 5<=max_seconds<=1800 or not 1<=max_stages<=100:
        raise Incident('UNSAFE_ENGINE_BUDGET')
    # Only this queue version can be executed, exact external pin required.
    q=queue_load(queue_file,expected_queue_sha256)
    control=pathlib.Path(q['control_root']).resolve()
    start=time.monotonic();deadline=start+max_seconds
    steps=[];attempted_recovery=[]
    with engine_lock(control):
        cp=checkpoint_read(control,expected_queue_sha256,q['authority'])
        def remaining():return deadline-time.monotonic()
        rows=snapshot(q)  # independently rehash all previously PASS inputs/outputs
        previously=set(cp['completed_jobs'])
        if not previously.issubset({k for k,v in rows.items() if v['state']=='PASS'}):
            raise Incident('FROZEN_COMPLETED_STAGE_HASH_CHANGED')
        # Crash between stage PASS and engine receipt: reconcile already-verified bytes.
        if set(cp['completed_jobs'])!={k for k,v in rows.items() if v['state']=='PASS'}:
            persist(control,cp,'CRASH_GAP_VERIFIED_STAGE_RECONCILED',rows)
        attempted_recovery=recover_prepinned(q,rows,remaining)
        if any(x['status']=='INDEPENDENTLY_PREPINNED_RECOVERED' for x in attempted_recovery):
            rows=snapshot(q);persist(control,cp,'ORIGINAL_PREPINNED_CRASH_RECOVERY',rows)
        last=None
        for _ in range(max_stages):
            rows=snapshot(q)
            if all(x['state']=='PASS' for x in rows.values()):
                final='ALL_JOBS_VERIFIED_PASS';break
            # The v2.2 dispatcher owns dependency-safe failover and per-stage lock.
            # Its 180-second internal budget is a separate hard cap.
            if remaining()<5:
                final='BOUNDED_BUDGET_EXIT_CHECKPOINTED';break
            last=dispatch(queue_file,expected_queue_sha256,min(180,max(5,remaining())))
            after=snapshot(q)
            if last['status']=='ONE_VERIFIED_STAGE_PASS':
                job=last['job']
                if rows[job]['state']=='PASS' or after[job]['state']!='PASS':
                    raise Incident('DISPATCH_FALSE_OR_DUPLICATE_PASS')
                steps.append(job)
                persist(control,cp,'ACTUAL_LOCAL_STAGE_PASS:'+job,after)
            elif last['status']=='NO_STAGE_PROMOTED_SAFE_DEFER':
                final='SAFE_DEFER_NO_ELIGIBLE_STAGE';persist(control,cp,final,after)
                break
            else:raise Incident('UNRECOGNIZED_DISPATCH_RESULT')
        else:final='MAX_VERIFIED_STAGES_CHECKPOINTED'
        rows=snapshot(q)
        if all(x['state']=='PASS' for x in rows.values()):final='ALL_JOBS_VERIFIED_PASS'
        if cp['last_result']!=final or set(cp['completed_jobs'])!={k for k,v in rows.items() if v['state']=='PASS'}:
            persist(control,cp,final,rows)
        return {'schema':SCHEMA,'status':final,'queue_sha256':expected_queue_sha256,
                'actually_executed_jobs':steps,'recovery':attempted_recovery,
                'completed_jobs':[k for k,v in rows.items() if v['state']=='PASS'],
                'pending_jobs':{k:v['state'] for k,v in rows.items() if v['state']!='PASS'},
                'elapsed_seconds':round(time.monotonic()-start,3),
                'durable_checkpoint':str(control/CHECKPOINT),
                'durable_checkpoint_sha256':hashlib.sha256((control/CHECKPOINT).read_bytes()).hexdigest()}

def main():
    a=argparse.ArgumentParser(description='Ejecutor REAL reanudable; NO activa PnL, MT5 ni holdout')
    a.add_argument('--queue',required=True);a.add_argument('--expected-queue-sha256',required=True)
    a.add_argument('--max-seconds',type=float,default=180);a.add_argument('--max-stages',type=int,default=5)
    z=a.parse_args()
    try:
        print(json.dumps(run(z.queue,z.expected_queue_sha256,z.max_seconds,z.max_stages),sort_keys=True,ensure_ascii=False))
        return 0
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e)},sort_keys=True),file=sys.stderr)
        return 3
if __name__=='__main__':raise SystemExit(main())
