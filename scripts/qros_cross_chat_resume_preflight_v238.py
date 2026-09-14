#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def load(root,rel):
    if not rel or not isinstance(rel,str): raise RuntimeError(f'INVALID_PATH:{rel!r}')
    p=root/rel
    if not p.is_file(): raise RuntimeError(f'MISSING:{rel}')
    return json.loads(p.read_text())
def exists(root,rel): return bool(rel) and (root/rel).is_file()
def dom(x): return (x.get('asset'),x.get('side'),x.get('timeframe'))
def blobsha(p):
    b=p.read_bytes(); h=hashlib.sha1(); h.update(f'blob {len(b)}\0'.encode()); h.update(b); return h.hexdigest()
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--stable-pointer',default='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json'); ap.add_argument('--out',required=True); a=ap.parse_args()
    root=Path(a.repo_root); checks=[]; errors=[]
    def ck(name,ok,detail=None):
        ok=bool(ok); checks.append({'name':name,'pass':ok,'detail':detail})
        if not ok: errors.append(name+(f':{detail}' if detail is not None else ''))
    try: stable=load(root,a.stable_pointer)
    except Exception as e: stable={}; errors.append(str(e))
    target=ledger={}
    if stable:
        ck('stable_version',stable.get('current_version')=='V238')
        ck('stable_target',stable.get('target_path')=='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER_V238_v1.json')
        ck('stable_firewalls',all(stable.get(k) is False for k in ('economic_pnl_read','holdout_open','ga2_open')))
        try: target=load(root,stable.get('target_path'))
        except Exception as e: errors.append(str(e))
    if target:
        ck('target_version',target.get('version')=='V238')
        ck('target_firewalls',all(target.get(k) is False for k in ('economic_pnl_read','holdout_open','ga2_open')))
        auth=target.get('authority',{})
        required=['machine_spec','gate_a_plan','event_ordering','pre_shard_semantics','promotion_ledger','promotion_continuity_policy','sharded_hardening_policy','derived_artifact_rematerialization','portable_ga1_wrapper_parity','resume_integrity_incident_closure','m1_groups_complete','m1_global_mask_pack','m1_global_pack_compaction','m1_group_mask_compaction','m1_storage_cleanup','m1_completion','current_config_stream_parity','cross_chat_resume_preflight','cross_chat_resume_regression']
        for k in required: ck('authority_'+k,exists(root,auth.get(k)),auth.get(k))
        try: ledger=load(root,auth['promotion_ledger'])
        except Exception as e: errors.append(str(e)); ledger={}
    if target and ledger:
        vc=target.get('verified_counts',{}); completed=target.get('completed_shards',[]); promoted=ledger.get('completed_and_promoted_shards',[])
        ck('completed_count',vc.get('ga1_formally_completed_shards')==len(completed)==6)
        ck('remaining_count',vc.get('ga1_remaining_shards')==54 and vc.get('shards_total')==60)
        ck('queue_count',vc.get('first_economic_gate_queue_count')==ledger.get('queued_shard_count')==len(promoted)==6)
        ck('ledger_firewalls',all(ledger.get(k) is False for k in ('economic_pnl_read','holdout_open','ga2_open','economic_execution_authorized')))
        tm={dom(x):x for x in completed}; lm={dom(x):x for x in promoted}; ck('domain_sets',set(tm)==set(lm))
        for d,t in sorted(tm.items()):
            l=lm.get(d)
            if not l: continue
            ck('ledger_receipt_'+str(d),t.get('completion_receipt')==l.get('completion_receipt'))
            try:r=load(root,t['completion_receipt'])
            except Exception as e: errors.append(str(e)); continue
            ck('completion_domain_'+str(d),dom(r.get('domain',{}))==d)
            ck('completion_count_'+str(d),r.get('processed_signal_configs',r.get('signal_configs'))==804672)
            ck('completion_shard_'+str(d),r.get('shard_id')==t.get('shard_id')==l.get('shard_id'))
            ck('completion_config_root_'+str(d),r.get('ordered_config_id_stream_root_sha256')==t.get('ordered_config_id_stream_root_sha256')==l.get('ordered_config_id_stream_root_sha256'))
            ck('completion_sem_root_'+str(d),r.get('semantic_class_root_sha256')==t.get('semantic_class_root_sha256')==l.get('semantic_class_root_sha256'))
            ck('completion_alias_root_'+str(d),r.get('full_alias_mapping_root_sha256')==t.get('full_alias_mapping_root_sha256')==l.get('full_alias_mapping_root_sha256'))
            ck('completion_distinct_'+str(d),r.get('distinct_mask_class_count',r.get('distinct_mask_classes'))==t.get('distinct_mask_classes')==l.get('distinct_mask_classes'))
            sg=r.get('scientific_guards',{}); ck('completion_firewall_'+str(d),not any(sg.get(k) is True for k in ('economic_pnl_read','holdout_open','ga2_open')))
        auth=target['authority']
        try:
            m1=load(root,auth['m1_completion']); pack=load(root,auth['m1_global_mask_pack']); pc=load(root,auth['m1_global_pack_compaction']); gc=load(root,auth['m1_group_mask_compaction']); clean=load(root,auth['m1_storage_cleanup']); cur=load(root,auth['current_config_stream_parity']); parity=load(root,auth['portable_ga1_wrapper_parity']); closure=load(root,auth['resume_integrity_incident_closure'])
        except Exception as e: errors.append(str(e)); m1=pack=pc=gc=clean=cur=parity=closure={}
        if m1 and pack:
            ck('m1_pack_pass',pack.get('state')=='PASS')
            for k in ('shard_id','ordered_config_id_stream_root_sha256','semantic_class_root_sha256','full_alias_mapping_root_sha256'): ck('m1_pack_'+k,pack.get(k)==m1.get(k))
        if pc: ck('m1_global_compaction',pc.get('status')=='PASS' and pc.get('scientific_content_changed') is False and pc.get('compressed_pack',{}).get('identity_verified') is True)
        if gc: ck('m1_group_compaction',gc.get('status')=='PASS' and gc.get('groups')==24 and gc.get('identity_verified_24_of_24') is True)
        if clean: ck('m1_cleanup',clean.get('status')=='PASS' and clean.get('scientific_content_changed') is False and all(clean.get(k) is False for k in ('economic_pnl_read','holdout_open','ga2_open')))
        if parity: ck('v236_parity',parity.get('status')=='PASS_BYTE_EXACT_PARITY')
        if closure: ck('incident_closed',closure.get('status')=='PASS_CLOSED_FOR_GA1_RESUME')
        cs=target.get('current_shard',{})
        if cur:
            ck('current_parity_status',cur.get('status')=='PASS' and cur.get('primary_independent_root_equal') is True)
            ck('current_domain',dom(cur.get('domain',{}))==dom(cs))
            ck('current_shard',cur.get('shard_id')==cs.get('shard_id'))
            ck('current_count',cur.get('processed_signal_configs')==cs.get('expected_signal_configs')==804672)
            ck('current_root',cur.get('ordered_config_id_stream_root_sha256')==cs.get('expected_config_root_sha256'))
    if target:
        ra=target.get('runner_authority',{})
        for name,row in sorted(ra.items()):
            p=row.get('path'); ck('runner_exists_'+name,exists(root,p),p)
            if exists(root,p): ck('runner_blob_'+name,blobsha(root/p)==row.get('git_blob_sha1'),row.get('git_blob_sha1'))
    status='PASS' if not errors else 'FAIL'
    rec={'schema':'QROS_CROSS_CHAT_RESUME_PREFLIGHT_4.0','status':status,'current_version':stable.get('current_version'),'target_path':stable.get('target_path'),'checks':checks,'errors':errors,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}
    rec['receipt_sha256']=hashlib.sha256(canonical(rec)).hexdigest(); Path(a.out).write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n'); print(json.dumps({'status':status,'checks':len(checks),'errors':errors,'receipt_sha256':rec['receipt_sha256']})); return 0 if status=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
