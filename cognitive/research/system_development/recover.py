"""Reuse a completed observed episode receipt from an external immutable hash.

Read-only recovery; never infers agent execution from arbitrary submitted JSON.
The caller must obtain the expected hash from a trusted release/checkpoint source.
"""
import argparse
import math
from pathlib import Path
from cognitive import runtime as v
from .protocol import adapt,grade,grade_failure,VARIANTS,SCENARIOS
from .run import verify_prereg

def recover(directory,expected_result_sha,prereg):
    protocol=verify_prereg(prereg)
    v.require_hash(expected_result_sha)
    snapshot=v.Snapshot(directory)
    result,raw=snapshot.json('RESULTS.json')
    v.require(v.sha256(raw)==expected_result_sha,'RESULT_ANCHOR_MISMATCH')
    v.require(result.get('schema')=='QRCEL_OBSERVED_SYSTEM_SLICE_V1' and result.get('status')=='PASS_RESTRICTED_EPISODES','RESULT_SCHEMA_OR_STATUS')
    v.require(result.get('preregistration_sha256')==v.sha256(prereg.read_bytes()),'RESULT_PREREG_MISMATCH')
    v.require(result.get('authority_manifest_blob_sha1')==protocol['authority_manifest_blob_sha1'],'RESULT_AUTHORITY_BINDING')
    response=snapshot.read('RAW_RESPONSE.json');v.require(v.sha256(response)==result.get('response_sha256'),'MODEL_RESPONSE_MISMATCH')
    plan,plan_raw=snapshot.json('PLAN.json')
    v.require(plan==adapt(response) and v.sha256(plan_raw)==result.get('plan_sha256'),'MODEL_PLAN_MISMATCH')
    rows=result.get('records');v.require(isinstance(rows,list) and len(rows)==15,'EPISODE_COUNT')
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
        counts[scenario+':'+variant]=len(trace)
    v.require(result.get('correct')==15 and result.get('total')==15 and result.get('scientific_dispatches')==0 and result.get('sealed') is False,'RESULT_SCOPE')
    return {'schema':'QRCEL_COMPLETED_EPISODES_RECOVERY_V1','status':'VERIFIED_REUSE_COMPLETED_EPISODES','result_sha256':expected_result_sha,
            'episodes_revalidated':15,'new_model_calls':0,'new_interpreter_operations':0,'historical_operation_counts':counts,
            'scope':'HASH_ANCHORED_COMPLETED_RECEIPT_REVALIDATION_NOT_LIVE_MODEL_CONTEXT_RECOVERY',
            'authority_observation_is_historical':True,'future_execution_requires_fresh_authority_and_runtime':True,'scientific_dispatch_authorized':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--expected-result-sha',required=True);p.add_argument('--prereg',type=Path,required=True)
    a=p.parse_args();print(v.canonical(recover(a.directory,a.expected_result_sha,a.prereg)).decode(),end='')

if __name__=='__main__':main()
