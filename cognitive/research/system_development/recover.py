"""Reuse a completed observed episode receipt from an external immutable hash.

Read-only recovery; never infers agent execution from arbitrary submitted JSON.
The caller must obtain the expected hash from a trusted release/checkpoint source.
"""
import argparse
import math
from pathlib import Path
from cognitive import runtime as v
from cognitive import kernel as k
from .protocol import adapt,grade,grade_failure,VARIANTS,SCENARIOS
from .run import verify_prereg

def recover(directory,expected_result_sha,prereg,source_archive=None,partial=False):
    protocol=verify_prereg(prereg,source_archive)
    v.require_hash(expected_result_sha)
    snapshot=v.Snapshot(directory)
    result,raw=snapshot.json('PARTIAL_RESULTS.json' if partial else 'RESULTS.json')
    v.require(v.sha256(raw)==expected_result_sha,'RESULT_ANCHOR_MISMATCH')
    schema='QRCEL_BOUND_PARTIAL_EPISODES_V1' if partial else 'QRCEL_OBSERVED_SYSTEM_SLICE_V1'
    status='PARTIAL_EPISODES' if partial else 'PASS_RESTRICTED_EPISODES'
    v.require(result.get('schema')==schema and result.get('status')==status,'RESULT_SCHEMA_OR_STATUS')
    v.require(result.get('preregistration_sha256')==v.sha256(prereg.read_bytes()),'RESULT_PREREG_MISMATCH')
    v.require(result.get('authority_manifest_blob_sha1')==protocol['authority_manifest_blob_sha1'],'RESULT_AUTHORITY_BINDING')
    response=snapshot.read('RAW_RESPONSE.json');v.require(v.sha256(response)==result.get('response_sha256'),'MODEL_RESPONSE_MISMATCH')
    plan,plan_raw=snapshot.json('PLAN.json')
    v.require(plan==adapt(response) and v.sha256(plan_raw)==result.get('plan_sha256'),'MODEL_PLAN_MISMATCH')
    rows=result.get('records');v.require(isinstance(rows,list),'EPISODE_COUNT')
    v.require(0<=len(rows)<=15 if partial else len(rows)==15,'EPISODE_COUNT')
    identities=[(s,p) for s in SCENARIOS for p in VARIANTS]
    v.require(all(isinstance(r,dict) for r in rows),'EPISODE_SCHEMA')
    v.require([(r.get('scenario'),r.get('variant')) for r in rows]==identities[:len(rows)],'EPISODE_PREFIX')
    seen=set();counts={}
    for row in rows:
        v.require(isinstance(row,dict),'EPISODE_SCHEMA')
        key=(row.get('scenario'),row.get('variant'))
        v.require(key[0] in SCENARIOS and key[1] in VARIANTS and key not in seen,'EPISODE_IDENTITY')
        seen.add(key);scenario,variant=key
        v.require(row.get('correct') is True and row.get('forbidden_marker_calls')==0,'EPISODE_NOT_ACCEPTED')
        attempts=row.get('attempts');expected_length=1 if scenario=='AUTHORITY_MISMATCH' else 3 if scenario.startswith('CRASH_') else 2
        v.require(isinstance(attempts,list) and len(attempts)==expected_length,'ATTEMPT_COUNT')
        for a in attempts:
            v.require(isinstance(a,dict),'ATTEMPT_SCHEMA')
            v.require(type(a.get('exit_code')) is int and isinstance(a.get('stdout'),str) and isinstance(a.get('stderr'),str),'ATTEMPT_SCHEMA')
            wall=a.get('wall_seconds');v.require(type(wall) in (int,float) and math.isfinite(wall) and wall>=0,'ATTEMPT_TIME')
        negative=scenario in ('OUTPUT_CORRUPTION','AUTHORITY_MISMATCH')
        final=attempts[-1] if negative else attempts[-2]
        answer=v.parse_json(final['stdout'].encode())
        v.require(row.get('final_answer')==answer,'FINAL_ANSWER_MISMATCH')
        if negative:
            v.require(grade_failure(scenario,final['exit_code'],answer),'FAULT_REJECTION_NOT_VERIFIED')
            if scenario=='OUTPUT_CORRUPTION':v.require(attempts[0]['exit_code']==0 and grade(v.parse_json(attempts[0]['stdout'].encode())),'CORRUPTION_SETUP_INVALID')
        else:
            v.require(final['exit_code']==0 and grade(answer),'OUTPUT_ORACLE_FAILED')
            repeated=v.parse_json(attempts[-1]['stdout'].encode())
            v.require(attempts[-1]['exit_code']==0 and grade(repeated) and repeated.get('new_calls')==0 and row.get('repeat_after_completion_zero_calls') is True,'REPLAY_NOT_IDEMPOTENT')
            if scenario.startswith('CRASH_'):v.require(attempts[0]['exit_code']==75,'INTERRUPTION_NOT_OBSERVED')
        trace=row.get('host_operation_trace');v.require(isinstance(trace,list) and len(trace)==row.get('host_operation_attempts'),'TRACE_COUNT')
        for event in trace:
            v.require(isinstance(event,dict) and event.get('type')=='OPERATION_ATTEMPT' and event.get('task_id') in {'A','B','C','D','T','G'} and type(event.get('pid')) is int and event['pid']>0,'TRACE_EVENT')
        expected=0 if scenario=='AUTHORITY_MISMATCH' else 11 if scenario.startswith('CRASH_') and variant=='A_FINAL_SNAPSHOT' else 7 if scenario=='CRASH_BEFORE_T' else 6
        v.require(len(trace)==expected,'UNEXPECTED_OPERATION_RECOMPUTATION')
        order=[identity for identity in k.validate_plan(plan) if identity!='S']
        cut=order.index('T')+1
        if scenario=='AUTHORITY_MISMATCH':segments=[[]]
        elif scenario.startswith('CRASH_'):
            restart=order if variant=='A_FINAL_SNAPSHOT' else order[cut-1:] if scenario=='CRASH_BEFORE_T' else order[cut:]
            segments=[order[:cut],restart,[]]
        else:segments=[order,[]]
        v.require([e['task_id'] for e in trace]==[i for segment in segments for i in segment],'TRACE_SEQUENCE')
        offset=0
        for index,(attempt,segment) in enumerate(zip(attempts,segments)):
            events=trace[offset:offset+len(segment)];offset+=len(segment)
            v.require(len({e['pid'] for e in events})<=1,'TRACE_ATTEMPT_PID')
            if scenario.startswith('CRASH_') and index==0:
                v.require(attempt['stdout']=='','CRASH_OUTPUT_INVALID')
            elif attempt['exit_code']==0:
                parsed=v.parse_json(attempt['stdout'].encode())
                v.require(type(parsed.get('new_calls')) is int and parsed['new_calls']==len(segment),'ATTEMPT_CALL_COUNT')
        counts[scenario+':'+variant]=len(trace)
    v.require(type(result.get('correct')) is int and result['correct']==len(rows) and type(result.get('total')) is int and result['total']==len(rows) and result.get('scientific_dispatches')==0 and result.get('sealed') is False,'RESULT_SCOPE')
    return {'schema':'QRCEL_COMPLETED_EPISODES_RECOVERY_V1','status':'VERIFIED_PARTIAL_EPISODES' if partial else 'VERIFIED_REUSE_COMPLETED_EPISODES','result_sha256':expected_result_sha,
            'episodes_revalidated':len(rows),'remaining_episodes':[list(key) for key in identities[len(rows):]],'new_model_calls':0,'new_interpreter_operations':0,'historical_operation_counts':counts,
            'scope':'HASH_ANCHORED_COMPLETED_RECEIPT_REVALIDATION_NOT_LIVE_MODEL_CONTEXT_RECOVERY',
            'authority_observation_is_historical':True,'future_execution_requires_fresh_authority_and_runtime':True,'scientific_dispatch_authorized':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--expected-result-sha',required=True);p.add_argument('--prereg',type=Path,required=True)
    p.add_argument('--source-archive',type=Path);p.add_argument('--partial',action='store_true')
    a=p.parse_args();print(v.canonical(recover(a.directory,a.expected_result_sha,a.prereg,a.source_archive,a.partial)).decode(),end='')

if __name__=='__main__':main()
