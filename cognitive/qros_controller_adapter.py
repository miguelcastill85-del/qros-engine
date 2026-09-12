"""V191 controller compatibility facade; inspection only, no authority transitions.

Reuses validated QRCEL readers; preserves original QROS schemas and task statuses.
The legacy V1 controller remains immutable and is not the repaired treatment.
"""
import argparse
import copy
from pathlib import Path
from . import runtime as v

def inspect(root:Path,manifest_blob:str,operation='validate'):
    v.require(operation in ('validate','next'),'V191_TRANSITION_CONTRACT_REQUIRED')
    snapshot=v.Snapshot(root)
    observation=v.observe_authority(snapshot,manifest_blob)
    v.require(observation.manifest['authority_epoch']==191,'UNSUPPORTED_CONTROLLER_ADAPTER_EPOCH')
    bootstrap=v.inspect_control_bootstrap(snapshot,manifest_blob)
    v.require(bootstrap.get('status')=='PASS','CONTROLLER_BOOTSTRAP_INCOMPLETE')
    queue=v.inspect_v191_queue(observation)
    rows=observation.queue['queue']
    hint=queue['next_item_hint']
    selected=[row for row in rows if row.get('item_id')==hint]
    v.require(len(selected)==1,'CONTROLLER_NEXT_ITEM_AMBIGUOUS')
    return {'schema':'QROS_V191_CONTROLLER_COMPATIBILITY_V1','status':'PASS',
        'operation':operation,'compatibility_scope':'FROZEN_INITIAL_V191_VALIDATE_AND_NEXT_ONLY',
        'manifest_blob_sha1':manifest_blob,'authority_epoch':191,
        'original_schemas':{'head':observation.head['schema'],'state':observation.state['schema'],'queue':observation.queue['schema']},
        'stage_hint':queue['stage_hint'],'next_item':copy.deepcopy(selected[0]) if operation=='next' else None,
        'decision':'PREFLIGHT_REQUIRED_NO_DISPATCH','population':queue['input_population'],
        'source_state_status':observation.state['status'],'source_queue_status':selected[0]['status'],
        'lease_contract_available':False,'supported_operations':['validate','next'],
        'unsupported_operations':['claim_lease','heartbeat_lease','release_lease','checkpoint_transition','scientific_dispatch'],
        'scientific_dispatch_authorized':False,'writes':0,'evidence_promoted':False,
        'baseline_identity':'QROS_V191_COMPATIBILITY_PATCH_NOT_UNMODIFIED_HISTORICAL_BASELINE'}

def main():
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['validate','next']);p.add_argument('--repo-root',type=Path,required=True);p.add_argument('--manifest-blob',required=True)
    a=p.parse_args()
    try:r=inspect(a.repo_root,a.manifest_blob,a.operation)
    except v.ContractError as e:
        r={'status':'FAIL_CLOSED','error':e.code,'scientific_dispatch_authorized':False,'writes':0}
    print(v.canonical(r).decode(),end='');return 0 if r['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
