"""Observed model-program replay through three predeclared persistence policies.

This measures a restricted system slice, not full CURRENT_QROS or model parity.
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from cognitive import runtime as v
from .protocol import adapt,grade,grade_failure,VARIANTS,SCENARIOS

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[2]

def authority_sources(root,anchor):
    v.inspect_control_bootstrap(v.Snapshot(root),anchor)
    name='control/CONTROL_AUTHORITY_MANIFEST_v3.json';manifest=v.parse_json((root/name).read_bytes())
    registry=manifest['active_hash_registry'];reg=v.parse_json((root/registry).read_bytes())
    paths=[name,registry,reg['inherited_registry']['path']]+[x['path'] for x in manifest['single_active_authority'].values()]+[x['path'] for x in manifest['legacy_redirects']]
    return {path:(root/path).read_bytes() for path in paths}

def verify_prereg(path):
    protocol=v.parse_json(path.read_bytes())
    for name,h in protocol['source_sha256'].items():
        v.require(v.sha256((PROJECT/name).read_bytes())==h,'FROZEN_SOURCE_CHANGED',name)
    v.require(protocol['variants']==list(VARIANTS) and protocol['scenarios']==list(SCENARIOS),'FROZEN_DESIGN_CHANGED')
    return protocol

def run(raw,authority_root,anchor,prereg,out,route):
    protocol=verify_prereg(prereg)
    v.require(anchor==protocol['authority_manifest_blob_sha1'],'AUTHORITY_ANCHOR_CHANGED')
    sources=authority_sources(authority_root,anchor)
    out.mkdir(parents=True,exist_ok=False)
    def write(name,obj):(out/name).write_bytes(v.canonical(obj))
    (out/'RAW_RESPONSE.json').write_bytes(raw)
    try:plan=adapt(raw)
    except v.ContractError as error:
        result={'status':'MODEL_PROGRAM_REJECTED','error':error.code,'route':route,'response_sha256':v.sha256(raw),'model_claim_status':'NO_EXECUTION_INFERRED'}
        write('RESULTS.json',result);return result
    write('PLAN.json',plan);plan_sha=v.sha256(v.canonical(plan))
    records=[]
    env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','LANG':'C.UTF-8'}
    for scenario in SCENARIOS:
        for variant in VARIANTS:
            with tempfile.TemporaryDirectory(prefix='qrcel-system-dev-') as tmp:
                root=Path(tmp);(root/'cognitive').mkdir()
                for path,contents in sources.items():
                    target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(contents)
                plan_path=root/'plan.json';plan_path.write_bytes(v.canonical(plan));trace=root/'host_trace.jsonl';attempts=[]
                def invoke(fault='NONE'):
                    start=time.monotonic()
                    process=subprocess.run([sys.executable,'-B','-m','cognitive.research.system_development.worker',
                        '--root',str(root),'--authority',anchor,'--plan',str(plan_path),'--plan-sha',plan_sha,
                        '--variant',variant,'--fault',fault,'--trace',str(trace)],cwd=PROJECT,env=env,
                        stdin=subprocess.DEVNULL,capture_output=True,timeout=20)
                    row={'exit_code':process.returncode,'wall_seconds':time.monotonic()-start,'stdout':process.stdout.decode(),'stderr':process.stderr.decode()}
                    attempts.append(row);return row
                if scenario=='NORMAL':last=invoke()
                elif scenario.startswith('CRASH_'):
                    fault='BEFORE:T' if scenario=='CRASH_BEFORE_T' else 'AFTER:T'
                    first=invoke(fault);v.require(first['exit_code']==75,'FAULT_NOT_OBSERVED')
                    last=invoke()
                elif scenario=='AUTHORITY_MISMATCH':
                    head=root/'control/HEAD.json';head.write_bytes(head.read_bytes()+b' ')
                    last=invoke()
                else:
                    first=invoke();v.require(first['exit_code']==0,'SETUP_NOT_COMPLETED')
                    if variant=='C_REAL_KERNEL':
                        db=sqlite3.connect(root/'cognitive/runs/episode/state.sqlite');db.execute('UPDATE completed SET output=? WHERE id=?',(v.canonical({'fraction':'999'}),'A'));db.commit();db.close()
                    else:
                        path=root/'state.json';state=v.parse_json(path.read_bytes());state['completed']['A']['output']={'fraction':'999'};path.write_bytes(v.canonical(state))
                    last=invoke()
                answer=v.parse_json(last['stdout'].encode()) if last['stdout'] else {}
                negative=scenario in ('OUTPUT_CORRUPTION','AUTHORITY_MISMATCH')
                correct=grade_failure(scenario,last['exit_code'],answer) if negative else last['exit_code']==0 and grade(answer)
                idempotent=None
                if not negative and correct:
                    again=invoke();again_answer=v.parse_json(again['stdout'].encode())
                    idempotent=again['exit_code']==0 and grade(again_answer) and again_answer['new_calls']==0
                    correct=correct and idempotent
                events=[v.parse_json(x) for x in trace.read_bytes().splitlines()] if trace.exists() else []
                forbidden_calls=sum(e['task_id']=='S' for e in events)
                correct=correct and forbidden_calls==0
                records.append({'scenario':scenario,'variant':variant,'correct':correct,'attempts':attempts,'host_operation_trace':events,
                    'host_operation_attempts':len(events),'forbidden_marker_calls':forbidden_calls,'repeat_after_completion_zero_calls':idempotent,
                    'artifact_bytes':sum(p.stat().st_size for p in root.rglob('*') if p.is_file()),
                    'final_answer':answer,'wall_seconds':sum(a['wall_seconds'] for a in attempts)})
                write('PARTIAL_RESULTS.json',{'records':records})
    result={'schema':'QRCEL_OBSERVED_SYSTEM_SLICE_V1','status':'PASS_RESTRICTED_EPISODES' if all(r['correct'] for r in records) else 'FAIL_RESTRICTED_EPISODES',
        'route':route,'records':records,'correct':sum(r['correct'] for r in records),'total':len(records),'response_sha256':v.sha256(raw),
        'plan_sha256':plan_sha,'preregistration_sha256':v.sha256(prereg.read_bytes()),'authority_manifest_blob_sha1':anchor,
        'model_calls_during_replay':0,'model_actual_snapshot_id':None,'sealed':False,'scientific_dispatches':0,
        'scope':'HOST_OBSERVED_REPLAY_OF_MODEL_GENERATED_RESTRICTED_PROGRAM','current_qros_treatment':'NOT_REPRESENTED_BY_A_OR_B',
        'host_trace_scope':'Every interpreter operation invoked by trusted adapters; not a full agent tool trace',
        'full_model_context_recovery_tested':False,'full_system_benchmark':False,'parity':'INSUFFICIENT_EVIDENCE'}
    write('RESULTS.json',result)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--response',type=Path,required=True);p.add_argument('--authority-root',type=Path,required=True)
    p.add_argument('--authority-blob',required=True);p.add_argument('--prereg',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--route',required=True)
    a=p.parse_args();r=run(a.response.read_bytes(),a.authority_root,a.authority_blob,a.prereg,a.out,a.route)
    print(json.dumps({k:r[k] for k in ('status','correct','total') if k in r}));return 0 if r['status']=='PASS_RESTRICTED_EPISODES' else 1

if __name__=='__main__':raise SystemExit(main())
