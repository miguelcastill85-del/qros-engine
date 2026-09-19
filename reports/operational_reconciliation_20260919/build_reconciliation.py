import copy
import importlib.util
import json
from pathlib import Path
import sys
from validate_reconciliation import POINTER,CHECKPOINT,blob,encode,validate,CANDIDATE_REF

source=Path(__file__).parent/'source'
root=Path(__file__).parent/'candidate'
root.mkdir(exist_ok=True)
payload=json.loads((Path(__file__).parents[1]/'reconcile_payload.json').read_text())
registry={x['path']:x['sha'] for x in payload['tree']['tree'] if x['type']=='blob'}
objects={f['path']:json.loads(f['content']) for f in payload['files']}
basep=objects[POINTER];basec=objects[CHECKPOINT]
cap=objects[basec['semantic_progress']['next_capsule']['path']]
receipts={obj['subject']['structural_group_index']:obj for path,obj in objects.items() if '_SEMANTIC_RECEIPT_' in path}
histpath='governance/QROS_DETERMINISTIC_EXECUTION_KERNEL_GOVERNANCE_v3.0.json'
historical={(histpath,CANDIDATE_REF):blob((source/'historical_dek_candidate.json').read_bytes())}
RECEIPT='control/QROS_OPERATIONAL_POINTER_RECONCILIATION_20260919_v1.json'

def build(validation_summary):
    p=copy.deepcopy(basep);c=copy.deepcopy(basec)
    p['schema']='QROS_PUBLIC1000_STABLE_FRONTIER_POINTER_6.9'
    c['schema']='QROS_PUBLIC1000_CURRENT_W09C_EXECUTION_CHECKPOINT_4.26'
    c['authority']['previous_checkpoint_blob_sha1']=registry[CHECKPOINT]
    c['authority']['stable_frontier']={'path':p['target_path'],'version':p['current_version'],
        'git_blob_sha1':p['target_git_blob_sha1'],'reference_role':'IMMUTABLE_SCIENTIFIC_TARGET_NO_BACK_EDGE'}
    for obj in (p['operational_overlay'],c['authority']):
        obj['recursive_dek_v3_candidate']['ref']=CANDIDATE_REF
        obj['recursive_dek_v3_candidate']['reference_scope']='HISTORICAL_CANDIDATE_SUPERSEDED_BY_RECURSIVE_DEK_V3_ACTIVE'
    rec9=c['authority']['group09_recovery_authority']
    p['operational_overlay']['group09_recovery_authority']=copy.deepcopy(rec9)
    p['operational_overlay']['next_capsule']=copy.deepcopy(c['semantic_progress']['next_capsule'])
    p['operational_overlay']['last_durable_group_receipt']=copy.deepcopy(c['semantic_progress']['last_receipt'])
    n=c['semantic_progress']['groups_durably_closed']
    c['pending']['semantic_mask_root_rematerialization']=f'IN_PROGRESS_{n}_OF_24_DURABLY_CLOSED'
    receipt={'schema':'QROS_OPERATIONAL_POINTER_RECONCILIATION_1.0',
      'status':'PASS_OPERATIONAL_REFERENCE_RECONCILIATION','objective':'Reconcile operational references against current authority without scientific dispatch',
      'authority':{'repository':'miguelcastill85-del/qros-engine','base_commit':payload['base'],'base_tree':payload['tree']['sha'],
        'source_pointer_blob':registry[POINTER],'source_checkpoint_blob':registry[CHECKPOINT],
        'original_reported_base':'ede867afa821bd7b7ee86e259b87c42ae782f4a3',
        'original_checkpoint_mismatch':'SUPERSEDED_BY_MAIN_ADVANCE_TO_4.25_BEFORE_THIS_REPAIR'},
      'source_bytes_verified':len(payload['files'])+2,
      'corrections':['BIND_CHECKPOINT_TO_IMMUTABLE_V255_TARGET_INSTEAD_OF_MUTABLE_POINTER',
        'VERSION_HISTORICAL_DEK_CANDIDATE_BY_EXACT_COMMIT',
        'BIND_GROUP09_RECOVERY_AUTHORITY_TO_TERMINAL_RECEIPT_VERSION',
        'ALIGN_NEXT_CAPSULE_TO_EXISTING_GROUP11_AUTHORIZATION',
        'ALIGN_LAST_TERMINAL_RECEIPT_TO_GROUP10',
        'ALIGN_PENDING_LABEL_TO_ELEVEN_CLOSED_GROUPS',
        'UPDATE_POINTER_AND_CHECKPOINT_AS_ONE_ATOMIC_GIT_TREE'],
      'history_preserved':{'old_stable_frontier_reference':copy.deepcopy(basec['authority']['stable_frontier']),
        'old_group09_recovery_reference':copy.deepcopy(basep['operational_overlay']['group09_recovery_authority']),
        'history_resolution':'Historical refs in this section describe source snapshot, not current-path pins'},
      'data':'No market payload opened; receipt metadata only',
      'verified_results':validation_summary,
      'scientific_state':c['scientific_state'],'scientific_state_changed':False,
      'scientific_target_blob':p['target_git_blob_sha1'],'closed_group_indices_preserved':list(receipts),
      'reported_config_count_preserved':c['semantic_progress']['processed_signal_configs_durable'],
      'real_worker_artifacts_rehashed':False,'closed_work_repeated':False,'capsule_activation_changed':False,
      'supervisor_v3_activated':False,'PR54_merged':False,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False,
      'portfolio_impact':'NONE','root_cause':'Incremental edits left current-path pins and cached labels stale; mutable pointer/checkpoint back-edge cannot be content-addressed consistently.',
      'next_automatic_action':basec['next_automatic_action'],
      'workflow_state_preserved':basep['operational_overlay']['execution_state'],
      'execution_scope':'RECONCILIATION_ONLY_NO_EXTERNAL_WORKFLOW_OR_WORKER_DISPATCH',
      'gates':{'operational_references':'PASS','scientific_or_data_validation':'NOT_REEXECUTED','P09_P12':'UNCHANGED'},
      'limitations':['Historical PASS claims preserved; original worker artifacts not rehashed','This receipt does not certify workflow liveness or runtime-local data availability','DEK v3 stays active; PR54 remains an unactivated engineering candidate']}
    # Remove ambiguous live-path/hash shapes from historical evidence.
    for obj in receipt['history_preserved'].values():
        if isinstance(obj,dict):obj['historical_path']=obj.pop('path')
    reg=dict(registry);reg[RECEIPT]=blob(encode(receipt))
    link={'path':RECEIPT,'git_blob_sha1':reg[RECEIPT]}
    c['authority']['operational_reference_reconciliation']=link
    reg[CHECKPOINT]=blob(encode(c))
    p['operational_overlay']['checkpoint']={'path':CHECKPOINT,'git_blob_sha1':reg[CHECKPOINT],'schema':c['schema']}
    p['operational_overlay']['operational_reference_reconciliation']=link
    reg[POINTER]=blob(encode(p))
    return p,c,receipt,reg

p,c,receipt,reg=build({'status':'PENDING_LOCAL_VALIDATION'})
result=validate(p,c,basep,basec,reg,historical,receipts,cap)
mutations={
 'stale_checkpoint':lambda p,c,r,h,rs,ca:p['operational_overlay']['checkpoint'].update(git_blob_sha1='0'*40),
 'wrong_receipt_subject':lambda p,c,r,h,rs,ca:rs[10]['subject'].update(structural_group_index=9),
 'missing_terminal_receipt':lambda p,c,r,h,rs,ca:rs.pop(10),
 'failed_terminal_receipt':lambda p,c,r,h,rs,ca:rs[10].update(status='FAIL'),
 'wrong_source_pin':lambda p,c,r,h,rs,ca:ca['exact_inputs'][0].update(git_blob_sha1='0'*40),
 'pnl_open':lambda p,c,r,h,rs,ca:p.update(economic_pnl_read=True),
 'holdout_open':lambda p,c,r,h,rs,ca:p.update(holdout_open=True),
 'ga2_open':lambda p,c,r,h,rs,ca:p.update(ga2_open=True),
 'wrong_scientific_target':lambda p,c,r,h,rs,ca:p.update(target_git_blob_sha1='0'*40),
 'stale_next_capsule':lambda p,c,r,h,rs,ca:p['operational_overlay'].update(next_capsule=basep['operational_overlay']['next_capsule']),
 'stale_last_receipt':lambda p,c,r,h,rs,ca:p['operational_overlay'].update(last_durable_group_receipt=basep['operational_overlay']['last_durable_group_receipt']),
 'workflow_action_changed':lambda p,c,r,h,rs,ca:p.update(next_action='LAUNCH_GROUP11'),
 'historical_ref_missing':lambda p,c,r,h,rs,ca:p['operational_overlay']['recursive_dek_v3_candidate'].pop('ref'),
 'count_inflation':lambda p,c,r,h,rs,ca:rs[10]['result'].update(processed_signal_configs=33529),
}
cases=[]
for name,mutation in mutations.items():
    pp,cc,rr,hh,rs,ca=copy.deepcopy((p,c,reg,historical,receipts,cap));mutation(pp,cc,rr,hh,rs,ca)
    try:validate(pp,cc,basep,basec,rr,hh,rs,ca)
    except ValueError as e:cases.append({'case':name,'status':'PASS_REJECTED','error':str(e)})
    else:raise RuntimeError('Mutation accepted: '+name)
result.update(adversarial_cases=len(cases),adversarial_passed=len(cases),cases=cases)
p,c,receipt,reg=build(result)
final=validate(p,c,basep,basec,reg,historical,receipts,cap)
for name,obj in ((POINTER,p),(CHECKPOINT,c),(RECEIPT,receipt)):
    dst=root/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(encode(obj))
(Path(__file__).parent/'validation.json').write_bytes(encode({'validation':result,'final':final,
    'outputs':{name:reg[name] for name in (POINTER,CHECKPOINT,RECEIPT)}}))
print(json.dumps({'base':payload['base'],'final':final,'adversarial_passed':len(cases),'outputs':{name:reg[name] for name in (POINTER,CHECKPOINT,RECEIPT)}},indent=2))
