#!/usr/bin/env python3
"""Validate operational pointer consistency; never dispatch a scientific action."""
import copy
import hashlib
import json
from pathlib import Path

POINTER='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json'
CHECKPOINT='control/QROS_PUBLIC_1000_CURRENT_W09C_EXECUTION_CHECKPOINT.json'
CANDIDATE_REF='09bc8f59edc2425a0ea8fda230f311d1da9ec2a7'

def blob(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def encode(obj):
    return (json.dumps(obj,indent=2,ensure_ascii=False)+'\n').encode()

def require(condition, code):
    if not condition:raise ValueError(code)

def refs(obj):
    if isinstance(obj,dict):
        if 'path' in obj and 'git_blob_sha1' in obj:yield obj
        for child in obj.values():yield from refs(child)
    elif isinstance(obj,list):
        for child in obj:yield from refs(child)

def validate(pointer,checkpoint,base_pointer,base_checkpoint,registry,historical,receipts,capsule):
    count=0
    for obj in (pointer,checkpoint):
        for ref in refs(obj):
            expected=(historical.get((ref['path'],ref['ref'])) if ref.get('ref') else registry.get(ref['path']))
            require(expected==ref['git_blob_sha1'],'REFERENCE_HASH_MISMATCH:'+ref['path'])
            count+=1
    target=pointer['target_path']
    require(pointer['target_git_blob_sha1']==registry[target],'SCIENTIFIC_TARGET_HASH_MISMATCH')
    require(pointer['target_git_blob_sha1']==base_pointer['target_git_blob_sha1'],'SCIENTIFIC_TARGET_CHANGED')
    require(checkpoint['authority']['stable_frontier']['path']==target,'MUTABLE_POINTER_CYCLE')
    require(pointer['operational_overlay']['checkpoint']['git_blob_sha1']==blob(encode(checkpoint)),'CHECKPOINT_BYTES_MISMATCH')
    require(pointer['operational_overlay']['checkpoint']['schema']==checkpoint['schema'],'CHECKPOINT_SCHEMA_MISMATCH')
    for key in ('economic_pnl_read','holdout_open','ga2_open','new_ga1_authorized','first_gate_execution_authorized'):
        require(pointer.get(key) is False and checkpoint['scientific_guards'].get(key) is False,'ECONOMIC_GUARD_CHANGED')
    for key in ('scientific_state','verified_counts','w09c_required_bindings','subject','scientific_execution_authorized','resume_contract','next_action'):
        require(pointer[key]==base_pointer[key],'SCIENTIFIC_OR_WORKFLOW_STATE_CHANGED:'+key)
    for key in ('data','semantic_progress','scientific_state','scientific_guards','durability_guard','last_execution_block','next_automatic_action'):
        require(checkpoint[key]==base_checkpoint[key],'CHECKPOINT_SCIENCE_OR_EXECUTION_CHANGED:'+key)
    require(checkpoint['authority']['heavy_execution_supervisor']==base_checkpoint['authority']['heavy_execution_supervisor'],'SUPERVISOR_ACTIVATED_WITHOUT_BINDING')
    require(pointer['operational_overlay']['execution_state']==base_pointer['operational_overlay']['execution_state'],'WORKFLOW_STATE_CHANGED')
    progress=checkpoint['semantic_progress'];n=progress['groups_durably_closed']
    require(len(receipts)==n and sorted(receipts)==progress['closed_indices'],'RECEIPT_COVERAGE_MISMATCH')
    total=0
    for idx,r in receipts.items():
        require(r['status']=='PASS' and r['campaign']==pointer['campaign'],'RECEIPT_STATUS_OR_CAMPAIGN_MISMATCH')
        require(r['subject']['structural_group_index']==idx,'RECEIPT_SUBJECT_MISMATCH')
        for key in ('asset','side','timeframe','shard_id'):
            require(r['subject'][key]==pointer['subject'][key],'RECEIPT_SUBJECT_MISMATCH')
        total+=r.get('result',r.get('worker_receipt',{}))['processed_signal_configs']
    require(total==progress['processed_signal_configs_durable'],'COVERAGE_COUNT_MISMATCH')
    require(pointer['operational_overlay']['last_durable_group_receipt']==progress['last_receipt'],'STALE_LAST_RECEIPT')
    require(pointer['operational_overlay']['next_capsule']==progress['next_capsule'],'STALE_NEXT_CAPSULE')
    require(capsule['subject']['structural_group_index']==progress['next_group_index'],'CAPSULE_SUBJECT_MISMATCH')
    previous=capsule['preconditions']['previous_group_receipt']
    require(all(previous[k]==progress['last_receipt'][k] for k in ('path','git_blob_sha1')),'CAPSULE_PREDECESSOR_MISMATCH')
    for ref in capsule['exact_inputs']:
        require(registry.get(ref['path'])==ref['git_blob_sha1'],'CAPSULE_SOURCE_PIN_MISMATCH')
    require(checkpoint['pending']['semantic_mask_root_rematerialization']==f'IN_PROGRESS_{n}_OF_{progress["groups_total"]}_DURABLY_CLOSED','STALE_PENDING_COUNT')
    return {'status':'PASS_OPERATIONAL_REFERENCE_RECONCILIATION','checked_references':count,
            'receipt_metadata_count':n,'reported_configs_preserved':total,'capsule_source_pins':len(capsule['exact_inputs']),
            'scientific_execution':False,'runtime_or_artifact_reexecution':False}
