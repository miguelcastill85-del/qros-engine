#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, itertools, json, subprocess, sys, tempfile
from pathlib import Path

SPEC='research/public1000/seed0076/QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json'
PLAN='control/QROS_PUBLIC_1000_SEED_0076_GATE_A_SHARD_PLAN_V213_v1.json'
ENUM_A='scripts/qros_seed_universe_enumerator_a_v2.py'; ENUM_B='scripts/qros_seed_universe_enumerator_b_v2.py'; SHARDS='scripts/qros_seed0076_gate_a_build_shard_manifest.py'

def c(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def h(x): return hashlib.sha256(c(x)).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def must(x,code):
    if not x: raise RuntimeError(code)
def run(cmd,out):
    r=subprocess.run(cmd,text=True,capture_output=True); must(r.returncode==0,'ORACLE_SUBPROCESS_FAIL:'+((r.stderr or r.stdout)[-1000:])); return load(out)
def audit(spec):
    names=set(spec['filter_families']); axes=set(spec['base_axes']); mg=set(spec['management_axes']); inc=spec['genealogy_radius']['included'].lower(); errs=[]
    predicates=[
      ('fractal', {'fractal_window','tie_policy','rearm_mode','trigger'}<=axes and 'BREAKOUT_BUFFER' in names),
      ('3ema', bool(spec['ema_triples']) and {'TREND','TREND_STRENGTH','EMA_CROSS_RECENCY'}<=names),
      ('momentum', 'MOMENTUM' in names and all(x in inc for x in ('cci','stochastic','rsi'))),
      ('context', {'VOLATILITY','SESSION','MULTI_TF','RETEST_ENTRY','GEOMETRY'}<=names),
      ('management', {'stop','target','breakeven','trailing','partial'}<=mg),
    ]
    errs += [k for k,v in predicates if not v]
    for e in spec['genealogy_radius']['excluded']:
        if not e.get('dimension') or not e.get('code'): errs.append('bad_exclusion')
    if spec['max_active_filter_families']!=2: errs.append('max_active')
    return sorted(set(errs))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--primary',required=True); ap.add_argument('--out',required=True); a=ap.parse_args(); root=Path(a.repo_root).resolve(); p=load(a.primary); spec=load(root/SPEC); plan=load(root/PLAN)
    with tempfile.TemporaryDirectory() as td0:
        td=Path(td0); apath=td/'a.json'; bpath=td/'b.json'; spath=td/'s.json'
        # Reverse order from primary and compare independent executable outputs.
        B=run([sys.executable,str(root/ENUM_B),str(root/SPEC),'--out',str(bpath)],bpath)
        A=run([sys.executable,str(root/ENUM_A),str(root/SPEC),'--out',str(apath)],apath)
        S=run([sys.executable,str(root/SHARDS),'--out',str(spath)],spath)
    keys=['base_tuple_count','base_tuple_root_sha256','filter_package_count','filter_package_root_sha256','raw_signal_config_count','management_valid_count','management_root_sha256','execution_profile_count','stress_profile_count']
    must(all(A[k]==B[k] for k in keys),'ORACLE_ENUMERATOR_PARITY')
    must((A['base_tuple_count'],A['filter_package_count'],A['raw_signal_config_count'],A['management_valid_count'],A['execution_profile_count'],A['stress_profile_count'])==(4320,11176,48280320,3710,3,7),'ORACLE_COUNTS')
    must(A['management_root_sha256']==plan['universe']['management_root_sha256'],'ORACLE_MANAGEMENT_ROOT')
    must(S['shard_descriptor_root_sha256']==plan['sharding']['shard_descriptor_root_sha256'] and S['shard_count']==60 and S['total_signal_configs']==48280320,'ORACLE_SHARD_IDENTITY')
    sd={'definition':'SHA256_CANONICAL_FACTOR_DESCRIPTOR_V1','base_tuple_count':A['base_tuple_count'],'base_tuple_root_sha256':A['base_tuple_root_sha256'],'filter_package_count':A['filter_package_count'],'filter_package_root_sha256':A['filter_package_root_sha256'],'raw_signal_config_count':A['raw_signal_config_count'],'mapping':'EXACT_CARTESIAN_PRODUCT_BASE_TUPLE_X_FILTER_PACKAGE'}
    signal=h(sd); execution=h({'definition':'ORDERED_FROZEN_PROFILE_LIST_V1','profiles':spec['execution_profiles']}); stress=h({'definition':'ORDERED_FROZEN_PROFILE_LIST_V1','profiles':spec['stress_profiles']})
    ontology={'base_axis_order':spec['base_axis_order'],'base_axes':spec['base_axes'],'ema_triples':spec['ema_triples'],'filter_families':spec['filter_families'],'max_active_filter_families':spec['max_active_filter_families'],'genealogy_radius':spec['genealogy_radius'],'management_axes':spec['management_axes'],'management_constraint_version':spec['management_constraint_version'],'execution_profiles':spec['execution_profiles'],'stress_profiles':spec['stress_profiles']}; ont=h(ontology)
    r1=audit(spec); r2=audit(json.loads(json.dumps(spec,sort_keys=True)))
    must(not r1 and not r2,'ORACLE_RISE_NONZERO_DELTA')
    must(p['status']=='PASS' and p['post_expansion_rise_fixed_point'] is True and p['rise_zero_delta_round_count']==2,'ORACLE_PRIMARY_STATE')
    must(p['signal_universe_root_sha256']==signal and p['management_universe_root_sha256']==A['management_root_sha256'] and p['execution_universe_root_sha256']==execution and p['stress_universe_root_sha256']==stress and p['ontology_root_sha256']==ont,'ORACLE_PRIMARY_ROOT_MISMATCH')
    must(p['shard_manifest']['shard_descriptor_root_sha256']==S['shard_descriptor_root_sha256'],'ORACLE_PRIMARY_SHARD_ROOT')
    must(p['economic_pnl_read'] is False and p['holdout_open'] is False and p['ga2_open'] is False and p['zip_or_market_data_required'] is False,'ORACLE_FIREWALL')
    rec={'schema':'QROS_SEED0076_RISE_FIXED_POINT_ORACLE_1.0','status':'PASS','independent_implementation':True,'imports_primary':False,'primary_receipt_sha256':p['receipt_sha256'],'signal_universe_root_sha256':signal,'management_universe_root_sha256':A['management_root_sha256'],'execution_universe_root_sha256':execution,'stress_universe_root_sha256':stress,'ontology_root_sha256':ont,'shard_descriptor_root_sha256':S['shard_descriptor_root_sha256'],'rise_zero_delta_round_count':2,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}; rec['receipt_sha256']=h(rec)
    Path(a.out).write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n'); print(json.dumps({'status':'PASS','receipt_sha256':rec['receipt_sha256']},sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
