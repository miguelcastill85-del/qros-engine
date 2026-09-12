"""Trusted DEVELOPMENT adapters over the existing restricted kernel operations.

No generated Python is executed. A/B are explicit experimental reference policies,
not the deployed CURRENT_QROS stack. C is the real transactional Kernel.
"""
import argparse
import json
import os
from pathlib import Path
from cognitive import kernel as k
from cognitive import runtime as v
from cognitive.validate_candidate import atomic_write

def append_trace(path, event):
    with path.open('ab') as out:
        out.write(v.canonical(event));out.flush();os.fsync(out.fileno())

def run(root, authority, plan, plan_sha, variant, fault, trace):
    k.validate_plan(plan)
    v.require(v.sha256(v.canonical(plan))==plan_sha,'PLAN_ANCHOR_MISMATCH')
    tasks={x['task_id']:x for x in plan['tasks']}
    binding={'plan_sha256':plan_sha,'authority_manifest_blob_sha1':authority,'source_sha256':k.source_identity(),
             'adapter_sha256':v.sha256(Path(__file__).read_bytes())}
    calls=0
    original=k.execute
    def execute(task, parents):
        nonlocal calls
        calls+=1
        append_trace(trace,{'type':'OPERATION_ATTEMPT','task_id':task['task_id'],'pid':os.getpid()})
        return original(task,parents)
    if variant=='C_REAL_KERNEL':
        k.execute=execute
        kernel=k.Kernel(root,plan,plan_sha,authority,'episode')
        try:
            receipt=kernel.run(None if fault=='NONE' else tuple(fault.split(':')))
            rows=kernel.rows()
            return {'status':receipt['status'],'outputs':{t:r['output'] for t,r in rows.items()},'blocked':receipt['blocked'],
                    'errors':receipt['errors'],'new_calls':calls,'kernel_receipt':receipt}
        finally:kernel.close();k.execute=original
    v.require(variant in ('A_FINAL_SNAPSHOT','B_PER_TASK_SNAPSHOT'),'VARIANT')
    v.inspect_control_bootstrap(v.Snapshot(root),authority)
    state_path=root/'state.json';completed={}
    if state_path.exists():
        state=v.parse_json(state_path.read_bytes())
        v.require(state.get('binding')==binding,'ADAPTER_BINDING_MISMATCH')
        completed=state['completed']
        v.require(set(completed)<=set(tasks),'UNKNOWN_COMPLETION')
        for identity,row in completed.items():
            v.require(v.sha256(v.canonical(row['output']))==row['sha256'],'OUTPUT_INTEGRITY_FAILED')
            v.require(set(tasks[identity]['parent_ids'])<=set(completed),'IMPOSSIBLE_COMPLETION')
    def persist():
        atomic_write(state_path,v.canonical({'binding':binding,'completed':completed}))
    blocked=[]
    for identity in k.validate_plan(plan):
        if identity in completed:continue
        task=tasks[identity];level,_=k.route(task)
        v.inspect_control_bootstrap(v.Snapshot(root),authority)
        if level=='L3' or not set(task['parent_ids'])<=set(completed):
            blocked.append(identity);continue
        output,evidence=execute(task,[completed[p]['output'] for p in task['parent_ids']])
        completed[identity]={'output':output,'evidence':evidence,'sha256':v.sha256(v.canonical(output))}
        if fault=='BEFORE:'+identity:os._exit(75)
        if variant=='B_PER_TASK_SNAPSHOT':persist()
        if fault=='AFTER:'+identity:os._exit(75)
    persist()
    return {'status':'BLOCKED' if blocked else 'COMPLETED_LOCAL_TASKS','outputs':{t:r['output'] for t,r in completed.items()},
            'blocked':blocked,'errors':[],'new_calls':calls}

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--authority',required=True)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--plan-sha',required=True)
    p.add_argument('--variant',required=True);p.add_argument('--fault',default='NONE');p.add_argument('--trace',type=Path,required=True)
    a=p.parse_args()
    try:answer=run(a.root,a.authority,v.parse_json(a.plan.read_bytes()),a.plan_sha,a.variant,a.fault,a.trace)
    except v.ContractError as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':e.code}));return 2
    print(json.dumps(answer,sort_keys=True));return 0

if __name__=='__main__':raise SystemExit(main())
