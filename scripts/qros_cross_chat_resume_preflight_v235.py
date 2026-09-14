#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SELF_REL='scripts/qros_cross_chat_resume_preflight_v235.py'

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def load(root:Path, rel:str):
    if not rel or not isinstance(rel,str): raise RuntimeError(f'INVALID_PATH:{rel!r}')
    p=(root/rel).resolve()
    rr=root.resolve()
    try: p.relative_to(rr)
    except ValueError: raise RuntimeError(f'PATH_ESCAPE:{rel}')
    if not p.is_file(): raise RuntimeError(f'MISSING:{rel}')
    return json.loads(p.read_text(encoding='utf-8'))
def exists(root:Path, rel:str):
    if not rel or not isinstance(rel,str): return False
    try:
        p=(root/rel).resolve(); p.relative_to(root.resolve())
    except Exception: return False
    return p.is_file()
def dom(x): return (x.get('asset'),x.get('side'),x.get('timeframe'))
def git_blob_sha1(p:Path):
    b=p.read_bytes();h=hashlib.sha1();h.update(f'blob {len(b)}\0'.encode());h.update(b);return h.hexdigest()

def verify_integrity_chain(root:Path, stable:dict, check):
    tpath=stable.get('target_path'); want_t=stable.get('target_git_blob_sha1')
    check('target_path_exists',exists(root,tpath),tpath)
    if not exists(root,tpath): return {},{}
    got_t=git_blob_sha1(root/tpath); check('target_blob_pinned',bool(want_t) and got_t==want_t, {'want':want_t,'got':got_t})
    target=load(root,tpath)
    chain=target.get('integrity_chain',{})
    mpath=chain.get('manifest_path'); want_m=chain.get('manifest_git_blob_sha1')
    check('manifest_path_exists',exists(root,mpath),mpath)
    if not exists(root,mpath): return target,{}
    got_m=git_blob_sha1(root/mpath); check('manifest_blob_pinned',bool(want_m) and got_m==want_m, {'want':want_m,'got':got_m})
    check('stable_manifest_binding',stable.get('integrity_manifest')==mpath and stable.get('integrity_manifest_git_blob_sha1')==want_m)
    manifest=load(root,mpath)
    entries=manifest.get('entries',[])
    check('manifest_nonempty',len(entries)>0,len(entries))
    seen=set()
    for row in entries:
        rel=row.get('path'); want=row.get('git_blob_sha1')
        check(f'integrity_unique_{rel}',rel not in seen,rel);seen.add(rel)
        check(f'integrity_exists_{rel}',exists(root,rel),rel)
        if exists(root,rel):
            got=git_blob_sha1(root/rel); check(f'integrity_blob_{rel}',bool(want) and got==want,{'want':want,'got':got})
    check('self_pinned',SELF_REL in seen,SELF_REL)
    return target,manifest

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo-root',required=True);ap.add_argument('--stable-pointer',default='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json');ap.add_argument('--out',required=True);a=ap.parse_args()
    root=Path(a.repo_root);errors=[];checks=[]
    def check(name,ok,detail=None):
        ok=bool(ok);checks.append({'name':name,'pass':ok,'detail':detail})
        if not ok: errors.append(name.upper())
    try: stable=load(root,a.stable_pointer)
    except Exception as e: stable={};errors.append(str(e))
    target={};manifest={};ledger={};remat={};parity={}
    if stable:
        target,manifest=verify_integrity_chain(root,stable,check)
    if target:
        check('stable_version_matches_target',stable.get('current_version')==target.get('version'))
        check('stable_flags_closed',stable.get('economic_pnl_read') is False and stable.get('holdout_open') is False and stable.get('ga2_open') is False)
        auth=target.get('authority',{})
        required=['machine_spec','gate_a_plan','event_ordering','pre_shard_semantics','promotion_ledger','promotion_continuity_policy','sharded_hardening_policy','derived_artifact_rematerialization','portable_ga1_wrapper_parity','xau_v228_rebinding_parity','h4_group_checkpoint']
        for k in required: check(f'authority_exists_{k}',exists(root,auth.get(k)),auth.get(k))
        check('stable_hardening_matches_target',stable.get('hardening_policy')==auth.get('sharded_hardening_policy'))
        check('stable_ledger_matches_target',stable.get('promotion_ledger')==auth.get('promotion_ledger'))
        check('stable_remat_matches_target',stable.get('rematerialization_manifest')==auth.get('derived_artifact_rematerialization'))
        try: ledger=load(root,auth.get('promotion_ledger'))
        except Exception as e: errors.append(str(e))
        try: remat=load(root,auth.get('derived_artifact_rematerialization'))
        except Exception as e: errors.append(str(e))
        try: parity=load(root,auth.get('portable_ga1_wrapper_parity'))
        except Exception as e: errors.append(str(e))
    if target and ledger:
        vc=target.get('verified_counts',{});completed=target.get('completed_shards',[]);promoted=ledger.get('completed_and_promoted_shards',[])
        n=vc.get('ga1_formally_completed_shards');q=vc.get('first_economic_gate_queue_count')
        check('target_completed_count',n==len(completed));check('ledger_queue_count',ledger.get('queued_shard_count')==len(promoted));check('queue_equals_completed',q==n==ledger.get('queued_shard_count'))
        check('economic_firewall_closed',all(x is False for x in [target.get('economic_pnl_read'),target.get('holdout_open'),target.get('ga2_open'),ledger.get('economic_pnl_read'),ledger.get('holdout_open'),ledger.get('ga2_open')]))
        tm={dom(x):x for x in completed};lm={dom(x):x for x in promoted};check('completed_ledger_domain_set',set(tm)==set(lm))
        for d,t in sorted(tm.items()):
            l=lm.get(d)
            if not l: continue
            check(f'ledger_receipt_path_{d}',t.get('completion_receipt')==l.get('completion_receipt'))
            try:r=load(root,t.get('completion_receipt'))
            except Exception as e: errors.append(str(e));continue
            check(f'completion_domain_{d}',dom(r.get('domain',{}))==d)
            rc=r.get('processed_signal_configs',r.get('signal_configs'));check(f'completion_config_count_{d}',rc==804672,rc)
            dc=r.get('distinct_mask_class_count',r.get('distinct_mask_classes'));check(f'distinct_count_{d}',dc==t.get('distinct_mask_classes')==l.get('distinct_mask_classes'))
            check(f'shard_id_{d}',r.get('shard_id')==t.get('shard_id')==l.get('shard_id'))
            rr=r.get('ordered_config_id_stream_root_sha256');check(f'config_root_{d}',rr==t.get('ordered_config_id_stream_root_sha256')==l.get('ordered_config_id_stream_root_sha256'))
            sr=r.get('semantic_class_root_sha256');check(f'semantic_root_{d}',sr==t.get('semantic_class_root_sha256')==l.get('semantic_class_root_sha256'))
            ar=r.get('full_alias_mapping_root_sha256');check(f'alias_root_{d}',ar==t.get('full_alias_mapping_root_sha256')==l.get('full_alias_mapping_root_sha256'))
            sg=r.get('scientific_guards',{});check(f'completion_firewall_{d}',not any(sg.get(k) is True for k in ('economic_pnl_read','holdout_open','ga2_open')))
        cur=target.get('current_shard',{});cp_path=target.get('authority',{}).get('h4_group_checkpoint') or target.get('authority',{}).get('current_group_checkpoint')
        if cp_path:
            try:c=load(root,cp_path)
            except Exception as e:errors.append(str(e));c={}
            if c:
                check('current_checkpoint_domain',dom(c)==dom(cur));check('current_checkpoint_shard_id',c.get('shard_id')==cur.get('shard_id'));check('current_checkpoint_config_root',c.get('expected_config_root_sha256')==cur.get('expected_config_root_sha256'))
                check('current_checkpoint_group_progress',c.get('groups_pass')==cur.get('groups_pass') and c.get('groups_total')==cur.get('groups_total'));check('current_checkpoint_config_count',c.get('processed_signal_configs')==804672)
                if cur.get('group_receipts_root_sha256') is not None: check('current_checkpoint_group_receipts_root',c.get('group_receipts_root_sha256')==cur.get('group_receipts_root_sha256'))
    if target and remat:
        check('remat_firewall_closed',all(remat.get('scientific_guards',{}).get(k) is False for k in ('economic_pnl_read','holdout_open','ga2_open')))
        rd=set(tuple(x['domain'].split('/')) for x in remat.get('completed_shards',[]));td=set(dom(x) for x in target.get('completed_shards',[]));check('remat_completed_domain_set',rd==td)
    if parity:
        check('portable_parity_pass',parity.get('status')=='PASS_BYTE_EXACT_PARITY')
    status='PASS' if not errors else 'FAIL'
    rec={'schema':'QROS_CROSS_CHAT_RESUME_PREFLIGHT_3.0','status':status,'stable_pointer':a.stable_pointer,'current_version':stable.get('current_version'),'target_path':stable.get('target_path'),'checks':checks,'errors':errors,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}
    rec['receipt_sha256']=hashlib.sha256(canonical(rec)).hexdigest();Path(a.out).write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n');print(json.dumps({'status':status,'errors':errors,'receipt_sha256':rec['receipt_sha256']}));return 0 if status=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
