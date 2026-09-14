#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path

def load(root:Path, rel:str):
    p=root/rel
    if not p.is_file(): raise RuntimeError(f'MISSING:{rel}')
    return json.loads(p.read_text(encoding='utf-8'))

def dom(x): return (x.get('asset'),x.get('side'),x.get('timeframe'))
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--stable-pointer',default='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json'); ap.add_argument('--out',required=True); a=ap.parse_args()
    root=Path(a.repo_root); errors=[]; checks=[]
    try: stable=load(root,a.stable_pointer)
    except Exception as e: stable={};errors.append(str(e))
    target={};ledger={}
    if stable:
        try: target=load(root,stable['target_path'])
        except Exception as e: errors.append(str(e))
    if target:
        checks.append(('stable_version_matches_target',stable.get('current_version')==target.get('version')))
        if not checks[-1][1]: errors.append('STABLE_TARGET_VERSION_MISMATCH')
        lpath=target.get('governance',{}).get('promotion_ledger')
        try: ledger=load(root,lpath)
        except Exception as e: errors.append(str(e))
    if target and ledger:
        vc=target.get('verified_counts',{})
        completed=target.get('completed_shards',[]); promoted=ledger.get('completed_and_promoted_shards',[])
        n=vc.get('ga1_formally_completed_shards')
        q=vc.get('first_economic_gate_queue_count')
        tests=[
          ('target_completed_count', n==len(completed)),
          ('ledger_queue_count', ledger.get('queued_shard_count')==len(promoted)),
          ('queue_equals_completed', q==n==ledger.get('queued_shard_count')),
          ('economic_pnl_closed', target.get('economic_pnl_read') is False and ledger.get('economic_pnl_read') is False),
          ('holdout_closed', target.get('holdout_open') is False and ledger.get('holdout_open') is False),
          ('ga2_closed', target.get('ga2_open') is False and ledger.get('ga2_open') is False),
        ]
        for name,ok in tests:
            checks.append((name,ok))
            if not ok: errors.append(name.upper())
        lm={dom(x):x for x in promoted}
        tm={dom(x):x for x in completed}
        if set(lm)!=set(tm): errors.append('COMPLETED_LEDGER_DOMAIN_SET_MISMATCH')
        for d,t in tm.items():
            l=lm.get(d)
            if not l: continue
            if t.get('completion_receipt')!=l.get('completion_receipt'): errors.append(f'RECEIPT_PATH_MISMATCH:{d}')
            try: r=load(root,t['completion_receipt'])
            except Exception as e: errors.append(str(e));continue
            rd=r.get('domain',{})
            if dom(rd)!=d: errors.append(f'COMPLETION_DOMAIN_MISMATCH:{d}')
            rc=r.get('processed_signal_configs',r.get('signal_configs'))
            if rc!=804672: errors.append(f'COMPLETION_CONFIG_COUNT_MISMATCH:{d}:{rc}')
            dc=r.get('distinct_mask_class_count',r.get('distinct_mask_classes'))
            if dc!=t.get('distinct_mask_classes') or dc!=l.get('distinct_mask_classes'): errors.append(f'DISTINCT_COUNT_MISMATCH:{d}')
            if r.get('semantic_class_root_sha256')!=l.get('semantic_class_root_sha256'): errors.append(f'SEMANTIC_ROOT_MISMATCH:{d}')
            sg=r.get('scientific_guards',{})
            if any(sg.get(k) is True for k in ('economic_pnl_read','holdout_open','ga2_open')): errors.append(f'COMPLETION_FIREWALL_FAIL:{d}')
        cur=target.get('current_shard',{})
        cp=target.get('authority',{}).get('h4_group_checkpoint') or target.get('authority',{}).get('current_group_checkpoint')
        if cp:
            try: c=load(root,cp)
            except Exception as e: errors.append(str(e));c={}
            if c:
                if dom(c)!=dom(cur): errors.append('CURRENT_CHECKPOINT_DOMAIN_MISMATCH')
                if c.get('shard_id')!=cur.get('shard_id'): errors.append('CURRENT_CHECKPOINT_SHARD_ID_MISMATCH')
                if c.get('expected_config_root_sha256')!=cur.get('expected_config_root_sha256'): errors.append('CURRENT_CHECKPOINT_CONFIG_ROOT_MISMATCH')
                if c.get('groups_pass')!=cur.get('groups_pass') or c.get('groups_total')!=cur.get('groups_total'): errors.append('CURRENT_CHECKPOINT_GROUP_PROGRESS_MISMATCH')
                if c.get('processed_signal_configs')!=804672: errors.append('CURRENT_CHECKPOINT_CONFIG_COUNT_MISMATCH')
    status='PASS' if not errors else 'FAIL'
    rec={'schema':'QROS_CROSS_CHAT_RESUME_PREFLIGHT_1.0','status':status,'stable_pointer':a.stable_pointer,'current_version':stable.get('current_version'),'target_path':stable.get('target_path'),'checks':[{'name':n,'pass':bool(v)} for n,v in checks],'errors':errors,'economic_pnl_read':False,'holdout_open':False}
    rec['receipt_sha256']=hashlib.sha256(canonical(rec)).hexdigest();Path(a.out).write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':status,'errors':errors,'receipt_sha256':rec['receipt_sha256']}));return 0 if status=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
