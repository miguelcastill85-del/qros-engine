#!/usr/bin/env python3
"""Build and RUN an actual deterministic three-job non-economic QROS queue.

For CI and local qualification only. These bytes are never broker evidence.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,sys
SCRIPTS=pathlib.Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
from qros_anti_stall_v2_1 import atomic_json,sha_file
from qros_continuation_engine_v2_3 import run
AUTH={'repo':'fixture/not-a-live-repository','branch':'synthetic-only','base_commit':'1'*40}
LOCK={'holdout_open':False,'ga2_open':False,'new_old_shard_ga1_authorized':False}

def fixture(root):
    jobs=[]
    for name,parent,first,alternative in [
        ('SOURCE_CHECK',[],"open('result.bin','wb').write(b'frozen_source_ok')",None),
        ('REPLAY_PARITY',['SOURCE_CHECK'],"raise SystemExit(42)","open('result.bin','wb').write(b'independent_equivalent_ok')"),
        ('FREEZE_RECEIPT',['REPLAY_PARITY'],"open('result.bin','wb').write(b'closed_once')",None)]:
        work=root/name;work.mkdir(parents=True,exist_ok=True)
        src=work/'frozen_source.bin';src.write_bytes((name+' ORIGINAL FIXTURE').encode()) if not src.exists() else None
        plan={'schema':'QROS_ANTI_STALL_PLAN_V2_1','lane_id':'NON_ECONOMIC_SYNTHETIC_QUALIFICATION',
              'authority':AUTH,'scientific_firewalls':LOCK,
              'stages':[{'id':'ONE_FROZEN_STAGE','kind':'local','timeout_seconds':4,
              'inputs':[{'path':src.name,'bytes':src.stat().st_size,'sha256':sha_file(src)}],
              'outputs':[{'path':'result.bin','sha256':None,'bytes':None}],
              'routes':[{'name':'PRIMARY','argv':[sys.executable,'-c',first]}]+
                       ([{'name':'INDEPENDENT_EQUIVALENT','argv':[sys.executable,'-c',alternative]}] if alternative else [])}]}
        pp=work/'FROZEN_PLAN.json'
        if not pp.exists():atomic_json(pp,plan)
        elif json.loads(pp.read_bytes())!=plan:raise RuntimeError('PREEXISTING_FIXTURE_PLAN_DRIFT')
        jobs.append({'id':name,'work':str(work),'plan':str(pp),'plan_sha256':sha_file(pp),'kind':'local',
                     'hard_route_seconds':20,'max_distinct_routes':len(plan['stages'][0]['routes']),'depends_on':parent})
    q={'schema':'QROS_BOUNDED_CONTINUATION_QUEUE_V2_2','authority':AUTH,'control_root':str(root/'control'),'jobs':jobs}
    qp=root/'FROZEN_QUEUE.json'
    if not qp.exists():atomic_json(qp,q)
    elif json.loads(qp.read_bytes())!=q:raise RuntimeError('PREEXISTING_FIXTURE_QUEUE_DRIFT')
    return qp,sha_file(qp)

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',required=True);a=p.parse_args()
    root=pathlib.Path(a.work).resolve();root.mkdir(parents=True,exist_ok=True)
    q,h=fixture(root);result=run(q,h,max_seconds=60,max_stages=5)
    if result['status']!='ALL_JOBS_VERIFIED_PASS' or len(result['completed_jobs'])!=3:
        raise RuntimeError('REAL_WORKER_CANARY_FAILED:'+result['status'])
    out={'schema':'QROS_EXECUTABLE_NONSTALL_V23_ACTUAL_SUBPROCESS_CANARY_V1',
         'scope':'SYNTHETIC_ONLY_NO_MARKET_DATA_NO_ECONOMIC_GATE',
         'queue_sha256':h,'engine_checkpoint_sha256':result['durable_checkpoint_sha256'],
         'actually_executed_jobs_this_invocation':result['actually_executed_jobs'],
         'completed_jobs':result['completed_jobs'],
         'sha256_outputs':{job:sha_file(root/job/'result.bin') for job in result['completed_jobs']},
         'failover_primary_EXIT_42_then_frozen_independent_equivalent':True,
         'holdout_open':False,'ga2_open':False,'status':'PASS'}
    atomic_json(root/'QROS_V23_SMOKE_RECEIPT.json',out)
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
