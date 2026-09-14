#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, tempfile
from pathlib import Path

V208='research/public1000/seed0076/QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V208_v1.json'
V209='research/public1000/seed0076/QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json'
V213='control/QROS_PUBLIC_1000_SEED_0076_GATE_A_SHARD_PLAN_V213_v1.json'
POLICY='governance/QROS_SEED_UNIVERSE_COMPILER_POLICY_v1.1.json'
STABLE='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json'
ACTIVE_EXEC='control/QROS_DETERMINISTIC_KERNEL_V251_ACTIVE_EXECUTION_VALIDATION_PASS_20260914_v1.json'
ENUM_A='scripts/qros_seed_universe_enumerator_a_v2.py'
ENUM_B='scripts/qros_seed_universe_enumerator_b_v2.py'
SHARDS='scripts/qros_seed0076_gate_a_build_shard_manifest.py'
PINS={
 V208:'4b5c2da6c544f79e13b6ed3d68d9dc8ca3d7bdcc',
 V209:'c6f7ac8b1daea6096f1e36b10bacbc5e6f2a8ebf',
 V213:'0b4f724ccf683907b05013687c581deadfc2ecc1',
 POLICY:'9dd081e87a255176108823f63f064ae28dea2bc7',
 ACTIVE_EXEC:'1a8a9c43aef8b577a676f10104ffc0fd638b36d9',
 ENUM_A:'15e4402fb39161caa5612e81d42ee8c2dd701dd8',
 ENUM_B:'e3bff26dce352bbc3c1e91ce4d2958571d35d001',
 SHARDS:'ddb21b0bfa0a6a3f015949e8cae296701a19e833',
}
EXPECTED_TICKET='aa713339ae4f67451342a24c72585520a2a01e6b27ce9a399b4248d9d50ed69b'
EXPECTED_ACTION='RECOVER_OR_REVALIDATE_RISE_FIXED_POINT_NO_PNL'


def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def sha(x): return hashlib.sha256(canonical(x)).hexdigest()
def blob(p:Path):
    b=p.read_bytes(); return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def load(p:Path): return json.loads(p.read_text(encoding='utf-8'))
def req(c,code,detail=None):
    if not c: raise RuntimeError(code if detail is None else f'{code}:{detail}')

def pin(root:Path, rel:str):
    p=root/rel; req(p.is_file(),'PIN_FILE_MISSING',rel); got=blob(p); req(got==PINS[rel],'PIN_MISMATCH',f'{rel}:{got}!={PINS[rel]}'); return got

def run_json(cmd, out:Path):
    r=subprocess.run(cmd,text=True,capture_output=True)
    req(r.returncode==0,'SUBPROCESS_FAIL',(r.stderr or r.stdout)[-1500:])
    req(out.is_file(),'SUBPROCESS_OUTPUT_MISSING',str(out)); return load(out)

def unresolved(x):
    bad=('TODO','TBD','UNKNOWN','UNDECIDED','PLACEHOLDER','FIXME')
    found=[]
    def walk(v,path='root'):
        if isinstance(v,dict):
            for k,z in v.items(): walk(z,f'{path}.{k}')
        elif isinstance(v,list):
            for i,z in enumerate(v): walk(z,f'{path}[{i}]')
        elif isinstance(v,str) and any(t in v.upper() for t in bad): found.append(path)
    walk(x); return found

def ontology_descriptor(spec):
    return {
      'base_axis_order':spec['base_axis_order'],
      'base_axes':spec['base_axes'],
      'ema_triples':spec['ema_triples'],
      'filter_families':spec['filter_families'],
      'max_active_filter_families':spec['max_active_filter_families'],
      'genealogy_radius':spec['genealogy_radius'],
      'management_axes':spec['management_axes'],
      'management_constraint_version':spec['management_constraint_version'],
      'execution_profiles':spec['execution_profiles'],
      'stress_profiles':spec['stress_profiles'],
    }

def rise_audit_round(spec, round_no):
    inc=spec['genealogy_radius']['included'].lower()
    fam=set(spec['filter_families'])
    axes=set(spec['base_axes'])
    management=set(spec['management_axes'])
    missing=[]
    checks={
      'root_fractal_structure': all(x in axes for x in ('fractal_window','tie_policy','rearm_mode','trigger')) and 'BREAKOUT_BUFFER' in fam,
      '3ema_ribbon_trend_marker_strength': bool(spec.get('ema_triples')) and {'TREND','TREND_STRENGTH','EMA_CROSS_RECENCY'} <= fam,
      'cci_stochastic_rsi_cycle_filters': 'MOMENTUM' in fam,
      'volatility': 'VOLATILITY' in fam,
      'session': 'SESSION' in fam,
      'multi_tf': 'MULTI_TF' in fam,
      'retest': 'RETEST_ENTRY' in fam,
      'geometry': 'GEOMETRY' in fam,
      'management_overlays': {'stop','target','breakeven','trailing','partial'} <= management,
    }
    for k,v in checks.items():
        if not v: missing.append(k)
    required_words=('fractal','3ema','trend','cci','stochastic','rsi','volatility','session','mtf','retest','geometry','management')
    for w in required_words:
        if w not in inc: missing.append('genealogy_included_token:'+w)
    excluded=spec['genealogy_radius'].get('excluded',[])
    for i,e in enumerate(excluded):
        if not e.get('dimension') or not e.get('code'): missing.append(f'exclusion_{i}_missing_dimension_or_code')
    forbidden_names=('VOLUME','ORDER_FLOW','NEWS','FUNDAMENTAL','CROSS_ASSET')
    for n in fam:
        if any(x in n.upper() for x in forbidden_names): missing.append('excluded_family_present:'+n)
    for k,v in spec['base_axes'].items():
        if not isinstance(v,list) or not v: missing.append('non_finite_or_empty_axis:'+k)
    if spec.get('max_active_filter_families') != 2: missing.append('max_active_filter_families_not_2')
    if unresolved(ontology_descriptor(spec)): missing.extend('unresolved:'+p for p in unresolved(ontology_descriptor(spec)))
    return {'round':round_no,'candidate_new_dimensions':sorted(set(missing)),'delta_count':len(set(missing))}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--out',required=True); a=ap.parse_args()
    root=Path(a.repo_root).resolve()
    pins={rel:pin(root,rel) for rel in PINS}
    stable=load(root/STABLE); active=load(root/ACTIVE_EXEC); spec0=load(root/V208); spec=load(root/V209); plan=load(root/V213); policy=load(root/POLICY)
    req(stable.get('current_version')=='V251','STABLE_VERSION')
    req(stable.get('machine_action_ticket_id')==EXPECTED_TICKET,'TICKET_ID')
    req(stable.get('machine_action_type')==EXPECTED_ACTION,'ACTION_TYPE')
    req(stable.get('active_execution_validation_status')=='PASS','ACTIVE_EXEC_VALIDATION')
    req(stable.get('economic_pnl_read') is False and stable.get('holdout_open') is False and stable.get('ga2_open') is False,'ECONOMIC_FIREWALL')
    req(active.get('status')=='PASS_EXTERNAL_INDEPENDENT_VALIDATION' and active.get('ticket',{}).get('ticket_id')==EXPECTED_TICKET,'ACTIVE_EXEC_RECEIPT')
    req(policy.get('gate_a_requirement') and 'post-expansion RISE fixed point' in policy['gate_a_requirement'],'POLICY_FIXED_POINT_REQUIREMENT')
    req(spec.get('gate_a_open') is False,'SPEC_GATE_A_ALREADY_OPEN')
    exp=spec['expected_counts']; req(exp=={'base_cells':4320,'filter_package_count':11176,'raw_signal_configs':48280320,'management_raw_cartesian':5880,'management_valid':3710,'execution_profiles':3,'stress_profiles':7},'V209_EXPECTED_COUNTS',exp)
    req(spec0['expected_counts']['raw_signal_configs']==6215760,'V208_BASELINE_COUNT')
    req(exp['raw_signal_configs']>spec0['expected_counts']['raw_signal_configs'],'POST_EXPANSION_NOT_LARGER')
    with tempfile.TemporaryDirectory() as td0:
        td=Path(td0); ao=td/'a.json'; bo=td/'b.json'; so=td/'shards.json'
        A=run_json([sys.executable,str(root/ENUM_A),str(root/V209),'--out',str(ao)],ao)
        B=run_json([sys.executable,str(root/ENUM_B),str(root/V209),'--out',str(bo)],bo)
        S=run_json([sys.executable,str(root/SHARDS),'--out',str(so)],so)
    keys=('base_tuple_count','base_tuple_root_sha256','filter_package_count','filter_package_root_sha256','raw_signal_config_count','management_valid_count','management_root_sha256','execution_profile_count','stress_profile_count')
    diffs={k:[A.get(k),B.get(k)] for k in keys if A.get(k)!=B.get(k)}; req(not diffs,'ENUMERATOR_PARITY_FAIL',diffs)
    req(A['base_tuple_count']==4320 and A['filter_package_count']==11176 and A['raw_signal_config_count']==48280320,'ENUMERATOR_COUNT_FAIL')
    req(A['management_valid_count']==3710 and A['execution_profile_count']==3 and A['stress_profile_count']==7,'OVERLAY_COUNT_FAIL')
    req(A['base_tuple_count']*A['filter_package_count']==A['raw_signal_config_count'],'CARTESIAN_COUNT_FAIL')
    req(A['management_root_sha256']==plan['universe']['management_root_sha256'],'MANAGEMENT_ROOT_V213_MISMATCH',f"{A['management_root_sha256']}!={plan['universe']['management_root_sha256']}")
    req(S['shard_count']==plan['sharding']['shard_count']==60,'SHARD_COUNT_FAIL')
    req(S['total_signal_configs']==plan['sharding']['total_signal_configs']==48280320,'SHARD_TOTAL_FAIL')
    req(S['shard_descriptor_root_sha256']==plan['sharding']['shard_descriptor_root_sha256'],'SHARD_ROOT_V213_MISMATCH')
    req(plan['sharding']['base_tuples_per_shard']*plan['sharding']['filter_packages_per_base_tuple']==plan['sharding']['signal_configs_per_shard']==804672,'SHARD_PRODUCT_FAIL')
    signal_descriptor={'definition':'SHA256_CANONICAL_FACTOR_DESCRIPTOR_V1','base_tuple_count':A['base_tuple_count'],'base_tuple_root_sha256':A['base_tuple_root_sha256'],'filter_package_count':A['filter_package_count'],'filter_package_root_sha256':A['filter_package_root_sha256'],'raw_signal_config_count':A['raw_signal_config_count'],'mapping':'EXACT_CARTESIAN_PRODUCT_BASE_TUPLE_X_FILTER_PACKAGE'}
    signal_root=sha(signal_descriptor)
    exec_descriptor={'definition':'ORDERED_FROZEN_PROFILE_LIST_V1','profiles':spec['execution_profiles']}; execution_root=sha(exec_descriptor)
    stress_descriptor={'definition':'ORDERED_FROZEN_PROFILE_LIST_V1','profiles':spec['stress_profiles']}; stress_root=sha(stress_descriptor)
    ontology=ontology_descriptor(spec); ontology_root=sha(ontology)
    rounds=[rise_audit_round(spec,1),rise_audit_round(spec,2)]
    req(all(r['delta_count']==0 for r in rounds),'RISE_NONZERO_DELTA',rounds)
    full_descriptor={'seed':'WEB_SEED_0076','scope':'FROZEN_GENEALOGY_RADIUS_AND_CANONICAL_INFORMATION_ONLY','v209_git_blob_sha1':pins[V209],'v213_git_blob_sha1':pins[V213],'compiler_policy_git_blob_sha1':pins[POLICY],'base_tuple_root_sha256':A['base_tuple_root_sha256'],'filter_package_root_sha256':A['filter_package_root_sha256'],'signal_universe_root_sha256':signal_root,'management_universe_root_sha256':A['management_root_sha256'],'execution_universe_root_sha256':execution_root,'stress_universe_root_sha256':stress_root,'shard_descriptor_root_sha256':S['shard_descriptor_root_sha256'],'ontology_root_sha256':ontology_root,'raw_signal_config_count':A['raw_signal_config_count'],'management_profile_count':A['management_valid_count'],'execution_profile_count':A['execution_profile_count'],'stress_profile_count':A['stress_profile_count']}
    receipt={'schema':'QROS_SEED0076_POST_EXPANSION_RISE_FIXED_POINT_REVALIDATION_1.0','status':'PASS','decision':'RISE_FIXED_POINT_REVALIDATED_NO_PNL','campaign':'PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA','seed':'WEB_SEED_0076','scope':'Fixed point is demonstrated only within the frozen genealogy radius and information available in the canonical V209 universe; it is not a claim that all conceivable trading concepts are exhausted.','source_pins':pins,'enumerator_parity_pass':True,'enumerator_symmetric_difference_count':0,'enumerator_a':A,'enumerator_b':B,'v213_legacy_signal_factorized_root_sha256':plan['universe']['signal_factorized_root_sha256'],'legacy_signal_factorized_root_interpretation':'PRESERVED_AS_FROZEN_V213_ANCHOR; formula is not inferred by this revalidation. Exact current universe identity is independently demonstrated by A/B factor roots, counts and the V213 shard root.','signal_factorization_descriptor':signal_descriptor,'signal_universe_root_sha256':signal_root,'management_universe_root_sha256':A['management_root_sha256'],'execution_universe_root_sha256':execution_root,'stress_universe_root_sha256':stress_root,'shard_manifest':{'shard_count':S['shard_count'],'total_signal_configs':S['total_signal_configs'],'shard_descriptor_root_sha256':S['shard_descriptor_root_sha256']},'ontology_root_sha256':ontology_root,'rise_rounds':rounds,'rise_zero_delta_round_count':2,'post_expansion_rise_fixed_point':True,'full_freeze_descriptor':full_descriptor,'full_freeze_descriptor_root_sha256':sha(full_descriptor),'development_pnl_already_observed':False,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False,'gate_a_open':False,'zip_or_market_data_required':False,'completed_ga1_recomputed':False}
    receipt['receipt_sha256']=sha(receipt)
    Path(a.out).write_text(json.dumps(receipt,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','decision':receipt['decision'],'receipt_sha256':receipt['receipt_sha256'],'signal_universe_root_sha256':signal_root,'ontology_root_sha256':ontology_root},sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
