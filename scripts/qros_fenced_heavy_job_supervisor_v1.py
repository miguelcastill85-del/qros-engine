#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import qros_fenced_runtime_lease_guard_v1 as fence
SCHEMA='QROS_FENCED_HEAVY_JOB_SUPERVISOR_1.0'

def validate_binding(spec:dict,lease:dict,now:str|None=None):
    ok,why=fence.validate_lease(lease,now)
    if not ok:return False,why
    if spec.get('job_id')!=lease.get('job_id'):return False,'JOB_ID_LEASE_MISMATCH'
    er=spec.get('expected_receipt')
    if not isinstance(er,dict):return False,'EXPECTED_RECEIPT_INVALID'
    gi=er.get('structural_group_index')
    if gi!=lease.get('group_index'):return False,'GROUP_INDEX_LEASE_MISMATCH'
    for k in ['lease_epoch','lease_id','fence_token']:
        if er.get(k)!=lease.get(k):return False,'EXPECTED_RECEIPT_FENCE_MISMATCH:'+k
    return True,'PASS'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job-spec',type=Path,required=True);ap.add_argument('--work-root',type=Path,required=True);ap.add_argument('--lease',type=Path,required=True);ap.add_argument('--supervisor-v2',type=Path,required=True);ap.add_argument('--launch-grace-seconds',type=int,default=30);ap.add_argument('--now')
    a=ap.parse_args()
    try:
        spec=json.loads(a.job_spec.read_text());lease=json.loads(a.lease.read_text())
        ok,why=validate_binding(spec,lease,a.now)
        if not ok:
            print(json.dumps({'schema':SCHEMA,'state':'FAIL','action':'FENCE_BINDING_FAIL_CLOSED','reason':why},sort_keys=True));return 2
        import subprocess
        cmd=[sys.executable,str(a.supervisor_v2),'--job-spec',str(a.job_spec),'--work-root',str(a.work_root),'--launch-grace-seconds',str(a.launch_grace_seconds)]
        cp=subprocess.run(cmd,capture_output=True,text=True)
        lines=[x for x in cp.stdout.splitlines() if x.strip()]
        if not lines:
            print(json.dumps({'schema':SCHEMA,'state':'FAIL','action':'SUPERVISOR_V2_NO_JSON','returncode':cp.returncode},sort_keys=True));return 2
        out=json.loads(lines[-1]);out={'schema':SCHEMA,'lease_epoch':lease['lease_epoch'],'lease_id':lease['lease_id'],'fence_token':lease['fence_token'],'delegate':out}
        print(json.dumps(out,sort_keys=True));return cp.returncode
    except Exception as e:
        print(json.dumps({'schema':SCHEMA,'state':'FAIL','action':'FENCED_SUPERVISOR_EXCEPTION','reason':f'{type(e).__name__}:{e}'},sort_keys=True));return 2
if __name__=='__main__':raise SystemExit(main())
