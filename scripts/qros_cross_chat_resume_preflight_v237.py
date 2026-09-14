#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def load(root:Path, rel:str):
    if not rel or not isinstance(rel,str): raise RuntimeError(f'INVALID_PATH:{rel!r}')
    p=root/rel
    if not p.is_file(): raise RuntimeError(f'MISSING:{rel}')
    return json.loads(p.read_text(encoding='utf-8'))
def exists(root:Path, rel:str): return bool(rel) and (root/rel).is_file()
def dom(x): return (x.get('asset'),x.get('side'),x.get('timeframe'))
def git_blob_sha1(p:Path):
    b=p.read_bytes();h=hashlib.sha1();h.update(f'blob {len(b)}\0'.encode());h.update(b);return h.hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo-root',required=True);ap.add_argument('--stable-pointer',default='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json');ap.add_argument('--out',required=True);a=ap.parse_args()
    root=Path(a.repo_root);errors=[];checks=[]
    def check(name,ok,detail=None):
        ok=bool(ok);checks.append({'name':name,'pass':ok,'detail':detail})
        if not ok: errors.append(name.upper()+(f':{detail}' if detail is not None else ''))
    try: stable=load(root,a.stable_pointer)
    except Exception as e: stable={};errors.append(str(e))
    target=ledger={}
    if stable:
        try: target=load(root,stable.get('target_path'))
        except Exception as e: errors.append(str(e))
    if target:
        check('stable_version_matches_target',stable.get('current_version')==target.get('version')=='V237')
        check('stable_target_path_matches',stable.get('target_path')=='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER_V237_v1.json')
        check('stable_flags_closed',all(stable.get(k) is False for k in ('economic_pnl_read','holdout_open','ga2_open')))
        check('target_flags_closed',all(target.get(k) is False for k in ('economic_pnl_read','holdout_open','ga2_open')))
        auth=target.get('authority',{})
        required=['machine_spec','gate_a_plan','event_ordering','pre_shard_semantics','promotion_ledger','promotion_continuity_policy','sharded_hardening_policy','derived_artifact_rematerialization','portable_ga1_wrapper_parity','resume_integrity_incident','resume_integrity_incident_closure','h4_rematerialization_reconciliation','h4_global_mask_pack','h4_storage_cleanup','h4_completion','current_config_stream_parity','cross_chat_resume_preflight','cross_chat_resume_regression']
        for k in required: check(f'authority_exists_{k}',exists(root,auth.get(k)),auth.get(k))
        try: ledger=load(root,auth.get('promotion_ledger'))
        except Exception as e: errors.append(str(e));ledger={}
    if target and ledger:
        vc=target.get('verified_counts',{}); completed=target.get('completed_shards',[]); promoted=ledger.get('completed_and_promoted_shards',[])
        check('target_completed_count',vc.get('ga1_formally_completed_shards')==len(completed)==5)
        check('target_remaining_count',vc.get('ga1_remaining_shards')==55 and vc.get('shards_total')==60)
        check('ledger_queue_count',ledger.get('queued_shard_count')==len(promoted)==5)
        check('queue_equals_completed',vc.get('first_economic_gate_queue_count')==5)
        check('economic_firewall_closed',all(x is False for x in [ledger.get('economic_pnl_read'),ledger.get('holdout_open'),ledger.get('ga2_open'),ledger.get('economic_execution_authorized')]))
        tm={dom(x):x for x in completed}; lm={dom(x):x for x in promoted}
        check('completed_ledger_domain_set',set(tm)==set(lm))
        for d,t in sorted(tm.items()):
            l=lm.get(d)
            if not l: continue
            check(f'ledger_receipt_path_{d}',t.get('completion_receipt')==l.get('completion_receipt'))
            try:r=load(root,t.get('completion_receipt'))
            except Exception as e: errors.append(str(e));continue
            rd=r.get('domain',{}); check(f'completion_domain_{d}',dom(rd)==d)
            rc=r.get('processed_signal_configs',r.get('signal_configs')); check(f'completion_config_count_{d}',rc==804672,rc)
            dc=r.get('distinct_mask_class_count',r.get('distinct_mask_classes')); check(f'distinct_count_{d}',dc==t.get('distinct_mask_classes')==l.get('distinct_mask_classes'))
            check(f'shard_id_{d}',r.get('shard_id')==t.get('shard_id')==l.get('shard_id'))
            check(f'config_root_{d}',r.get('ordered_config_id_stream_root_sha256')==t.get('ordered_config_id_stream_root_sha256')==l.get('ordered_config_id_stream_root_sha256'))
            check(f'semantic_root_{d}',r.get('semantic_class_root_sha256')==t.get('semantic_class_root_sha256')==l.get('semantic_class_root_sha256'))
            check(f'alias_root_{d}',r.get('full_alias_mapping_root_sha256')==t.get('full_alias_mapping_root_sha256')==l.get('full_alias_mapping_root_sha256'))
            sg=r.get('scientific_guards',{}); check(f'completion_firewall_{d}',not any(sg.get(k) is True for k in ('economic_pnl_read','holdout_open','ga2_open')))
        auth=target['authority']
        try:h4=load(root,auth['h4_completion']); pack=load(root,auth['h4_global_mask_pack']); clean=load(root,auth['h4_storage_cleanup']); remat=load(root,auth['h4_rematerialization_reconciliation']); parity=load(root,auth['portable_ga1_wrapper_parity']); closure=load(root,auth['resume_integrity_incident_closure']); curp=load(root,auth['current_config_stream_parity'])
        except Exception as e: errors.append(str(e)); h4=pack=clean=remat=parity=closure=curp={}
        if h4 and pack:
            check('h4_pack_state',pack.get('state')=='PASS')
            for k in ('shard_id','ordered_config_id_stream_root_sha256','semantic_class_root_sha256','full_alias_mapping_root_sha256'):
                check('h4_pack_'+k,pack.get(k)==h4.get(k))
        if clean:
            check('h4_cleanup_pass',clean.get('status')=='PASS' and clean.get('scientific_content_changed') is False)
            check('h4_cleanup_firewall',all(clean.get(k) is False for k in ('economic_pnl_read','holdout_open','ga2_open')))
        if remat:
            check('h4_remat_pass',remat.get('status')=='PASS' and remat.get('groups_verified')==24 and remat.get('v232_scientific_fields_match') is True)
            check('h4_remat_firewall',remat.get('economic_pnl_read') is False and remat.get('holdout_open') is False and remat.get('ga2_open') is False)
        if parity:
            check('v236_parity_pass',parity.get('status')=='PASS_BYTE_EXACT_PARITY')
            check('v236_parity_decision',parity.get('decision')=='ADOPT_V236_FOR_DETERMINISTIC_GA1_REMATERIALIZATION_ONLY')
        if closure: check('incident_closure_pass',closure.get('status')=='PASS_CLOSED_FOR_GA1_RESUME')
        cur=target.get('current_shard',{})
        if curp:
            check('current_parity_pass',curp.get('status')=='PASS' and curp.get('primary_independent_root_equal') is True)
            check('current_parity_domain',dom(curp.get('domain',{}))==dom(cur))
            check('current_parity_shard',curp.get('shard_id')==cur.get('shard_id'))
            check('current_parity_count',curp.get('processed_signal_configs')==cur.get('expected_signal_configs')==804672)
            check('current_parity_root',curp.get('ordered_config_id_stream_root_sha256')==cur.get('expected_config_root_sha256'))
    if target:
        ra=target.get('runner_authority',{})
        for name,row in sorted(ra.items()):
            p=row.get('path'); want=row.get('git_blob_sha1'); check(f'runner_exists_{name}',exists(root,p),p)
            if exists(root,p): check(f'runner_blob_{name}',git_blob_sha1(root/p)==want,want)
        try: parity=load(root,target['authority']['portable_ga1_wrapper_parity'])
        except Exception: parity={}
        ca=parity.get('corrected_authority',{}) if parity else {}
        if ca:
            check('v236_cached_path_pin',ca.get('cached_wrapper_path')==ra.get('portable_cached_wrapper',{}).get('path'))
            check('v236_cached_blob_pin',ca.get('cached_wrapper_git_blob_sha1')==ra.get('portable_cached_wrapper',{}).get('git_blob_sha1'))
            check('v236_worker_path_pin',ca.get('base_worker_path')==ra.get('base_group_worker',{}).get('path'))
            check('v236_worker_blob_pin',ca.get('base_worker_git_blob_sha1')==ra.get('base_group_worker',{}).get('git_blob_sha1'))
    status='PASS' if not errors else 'FAIL'
    rec={'schema':'QROS_CROSS_CHAT_RESUME_PREFLIGHT_3.0','status':status,'stable_pointer':a.stable_pointer,'current_version':stable.get('current_version'),'target_path':stable.get('target_path'),'checks':checks,'errors':errors,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}
    rec['receipt_sha256']=hashlib.sha256(canonical(rec)).hexdigest();Path(a.out).write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n');print(json.dumps({'status':status,'errors':errors,'receipt_sha256':rec['receipt_sha256']}));return 0 if status=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
