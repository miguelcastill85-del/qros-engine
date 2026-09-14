#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

def load(root,rel):
    if not rel or not isinstance(rel,str): raise RuntimeError(f'INVALID_PATH:{rel!r}')
    p=root/rel
    if not p.is_file(): raise RuntimeError(f'MISSING:{rel}')
    return json.loads(p.read_text(encoding='utf-8'))
def exists(root,rel): return bool(rel) and (root/rel).is_file()
def blobsha(p):
    b=p.read_bytes(); h=hashlib.sha1(); h.update(f'blob {len(b)}\0'.encode()); h.update(b); return h.hexdigest()
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def dom(x): return (x.get('asset'),x.get('side'),x.get('timeframe'))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--stable-pointer',default='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json'); ap.add_argument('--out',required=True); a=ap.parse_args()
    root=Path(a.repo_root); checks=[]; errors=[]
    def ck(n,ok,d=None):
        ok=bool(ok); checks.append({'name':n,'pass':ok,'detail':d})
        if not ok: errors.append(n+(f':{d}' if d is not None else ''))
    try: stable=load(root,a.stable_pointer)
    except Exception as e: stable={}; errors.append(str(e))
    target={}
    if stable:
        ck('stable_version',stable.get('current_version')=='V241',stable.get('current_version'))
        ck('stable_target',stable.get('target_path')=='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER_V241_v1.json',stable.get('target_path'))
        ck('stable_pre_gate_firewalls',all(stable.get(k) is False for k in ('economic_pnl_read','holdout_open','ga2_open')))
        try: target=load(root,stable.get('target_path'))
        except Exception as e: errors.append(str(e))
    if target:
        ck('target_version',target.get('version')=='V241')
        ck('target_state',target.get('state')=='DEVELOPMENT_RUNNING')
        ck('target_pre_gate_firewalls',all(target.get(k) is False for k in ('economic_pnl_read','holdout_open','ga2_open')))
        ck('new_ga1_blocked',target.get('new_ga1_authorized') is False and target.get('new_ga1_blocker')=='FIRST_GATE_BACKLOG_PENDING')
        auth=target.get('authority',{})
        req=['primary_policy_pointer','primary_policy','first_gate_multiplicity_contract','policy_supersession_receipt','promotion_ledger','gate_a_plan','m12_completion','m12_storage_cleanup','m15_config_stream_parity','xau_m1_completion','cross_chat_resume_preflight','cross_chat_resume_regression']
        for k in req: ck('authority_exists_'+k,exists(root,auth.get(k)),auth.get(k))
        try:
            pp=load(root,auth['primary_policy_pointer']); pol=load(root,auth['primary_policy']); con=load(root,auth['first_gate_multiplicity_contract']); sup=load(root,auth['policy_supersession_receipt']); led=load(root,auth['promotion_ledger']); m12=load(root,auth['m12_completion']); clean=load(root,auth['m12_storage_cleanup']); m15=load(root,auth['m15_config_stream_parity']); xau=load(root,auth['xau_m1_completion'])
        except Exception as e:
            errors.append(str(e)); pp=pol=con=sup=led=m12=clean=m15=xau={}
        if pp:
            ck('policy_pointer_active',pp.get('status')=='ACTIVE')
            ck('policy_pointer_primary_path',pp.get('primary_policy',{}).get('path')==auth.get('primary_policy'))
            ck('policy_pointer_primary_blob',pp.get('primary_policy',{}).get('git_blob_sha1')=='8d9e59d12aabbbe41444982096bf35d42a1f0350')
            ck('policy_pointer_contract_blob',pp.get('seed0076_first_gate_contract',{}).get('git_blob_sha1')=='bc5ce2b52ca5734328283fb3c1d67ee1d93905c1')
            old=pp.get('superseded_policy',{}); ck('old_policy_pin',old.get('git_blob_sha1')=='08117b1b4926f2532f16542340a64bff72197e94')
            if exists(root,old.get('path')): ck('old_policy_bytes_unchanged',blobsha(root/old['path'])==old.get('git_blob_sha1'))
        if pol:
            ck('policy_v2_active_primary',pol.get('status')=='ACTIVE_PRIMARY')
            ck('policy_v2_no_ga1_with_pending','FIRST_GATE' in pol.get('primary_invariant','') and 'FORBIDDEN' in pol.get('primary_invariant',''))
            ck('policy_v2_m15_blocked',pol.get('seed0076_binding',{}).get('preregistered_next_GA1_after_backlog',{}).get('status')=='BLOCKED_BY_FIRST_GATE_BACKLOG')
            ck('policy_v2_blob',blobsha(root/auth['primary_policy'])=='8d9e59d12aabbbe41444982096bf35d42a1f0350')
        if con:
            ck('contract_frozen_pre_pnl',con.get('status')=='FROZEN_PRE_PNL')
            ck('contract_60_shards',con.get('preregistration_guards',{}).get('shard_count')==60)
            eb=con.get('cross_shard_error_budget',{}); ck('contract_equal_fixed_budget',eb.get('method')=='FIXED_EQUAL_PARTITION_NO_RECYCLING' and eb.get('per_shard_q_exact')=='1/1200' and eb.get('unused_budget_recycled') is False)
            wm=con.get('within_shard_multiplicity',{}); ck('contract_by',wm.get('method')=='BENJAMINI_YEKUTIELI' and wm.get('alpha_recycling') is False)
            ck('contract_blob',blobsha(root/auth['first_gate_multiplicity_contract'])=='bc5ce2b52ca5734328283fb3c1d67ee1d93905c1')
        if sup:
            ck('supersession_pass',sup.get('status')=='PASS_SUPERSESSION_FROZEN')
            ck('supersession_old_pin',sup.get('superseded_policy',{}).get('git_blob_sha1')=='08117b1b4926f2532f16542340a64bff72197e94')
            ck('supersession_new_pin',sup.get('primary_policy',{}).get('git_blob_sha1')=='8d9e59d12aabbbe41444982096bf35d42a1f0350')
            ck('supersession_contract_pin',sup.get('seed0076_first_gate_contract',{}).get('git_blob_sha1')=='bc5ce2b52ca5734328283fb3c1d67ee1d93905c1')
        if led:
            rows=led.get('completed_and_promoted_shards',[]); pending=[r for r in rows if r.get('first_gate_status')=='PENDING']
            ck('ledger_v7',led.get('ledger_version')==7)
            ck('ledger_eight_rows',len(rows)==8 and led.get('queued_shard_count')==8)
            ck('ledger_fifo_orders',[r.get('first_gate_order') for r in rows]==list(range(1,9)))
            ck('ledger_all_pending',len(pending)==8 and led.get('first_gate_pending_count')==8 and led.get('first_gate_terminal_count')==0)
            ck('ledger_no_economic_results',all(r.get('economic_scoring_executed') is False and r.get('first_gate_result_receipt') is None for r in rows))
            ck('ledger_current_order1',led.get('current_first_gate_order')==1 and led.get('current_first_gate_shard_id')==rows[0].get('shard_id'))
            ck('ledger_current_xau_m1',dom(rows[0])==('XAUUSD','BUY','M1'))
            ck('ledger_new_ga1_blocked',led.get('new_ga1_authorized') is False and led.get('new_ga1_blocker')=='FIRST_GATE_BACKLOG_PENDING')
            nxt=led.get('next_preregistered_ga1',{}); ck('ledger_m15_blocked',dom(nxt)==('NQX','BUY','M15') and nxt.get('status')=='BLOCKED_BY_FIRST_GATE_BACKLOG')
            ck('ledger_firewalls',all(led.get(k) is False for k in ('economic_pnl_read','holdout_open','ga2_open')))
        if m12 and led:
            r8=led.get('completed_and_promoted_shards',[{}])[-1]
            ck('m12_completion_pass',m12.get('state')=='PASS' and m12.get('ga1_completed_shard_ordinal')==8)
            ck('m12_ledger_identity',m12.get('shard_id')==r8.get('shard_id') and m12.get('ordered_config_id_stream_root_sha256')==r8.get('ordered_config_id_stream_root_sha256') and m12.get('semantic_class_root_sha256')==r8.get('semantic_class_root_sha256') and m12.get('full_alias_mapping_root_sha256')==r8.get('full_alias_mapping_root_sha256'))
        if clean: ck('m12_cleanup_pass',clean.get('status')=='PASS' and clean.get('scientific_content_changed') is False)
        if m15:
            ck('m15_parity_pass',m15.get('status')=='PASS' and m15.get('primary_independent_root_equal') is True)
            ck('m15_parity_identity',m15.get('shard_id')=='1e31983853b9b05d2064ab725322697d5a007c2f643b1a2224272cd424e88106' and m15.get('ordered_config_id_stream_root_sha256')=='46e39c9108d4eec03d847fe3b405bdd7777976ba048f27705abfb7a3c869f947')
        if xau and led:
            r1=led.get('completed_and_promoted_shards',[{}])[0]
            ck('xau_completion_identity',xau.get('shard_id')==r1.get('shard_id') and xau.get('ordered_config_id_stream_root_sha256')==r1.get('ordered_config_id_stream_root_sha256'))
        cf=target.get('current_first_gate',{})
        ck('target_current_first_gate_xau',dom(cf)==('XAUUSD','BUY','M1') and cf.get('first_gate_order')==1 and cf.get('status')=='PREREGISTERED_PENDING_EXECUTION')
        ng=target.get('next_preregistered_ga1',{}); ck('target_m15_blocked',dom(ng)==('NQX','BUY','M15') and ng.get('status')=='BLOCKED_BY_FIRST_GATE_BACKLOG')
        vc=target.get('verified_counts',{}); ck('target_counts',vc.get('ga1_formally_completed_shards')==8 and vc.get('ga1_remaining_shards')==52 and vc.get('first_gate_pending')==8 and vc.get('first_gate_terminal')==0)
    status='PASS' if not errors else 'FAIL'
    rec={'schema':'QROS_CROSS_CHAT_RESUME_PREFLIGHT_6.0','status':status,'current_version':stable.get('current_version'),'target_path':stable.get('target_path'),'checks':checks,'errors':errors,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}
    rec['receipt_sha256']=hashlib.sha256(canonical(rec)).hexdigest(); Path(a.out).write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'status':status,'checks':len(checks),'errors':errors,'receipt_sha256':rec['receipt_sha256']})); return 0 if status=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
