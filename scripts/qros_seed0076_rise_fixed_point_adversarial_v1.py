#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path
PRIMARY='scripts/qros_seed0076_rise_fixed_point_revalidate_v1.py'; ORACLE='scripts/qros_seed0076_rise_fixed_point_oracle_v1.py'; STABLE='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json'; SPEC='research/public1000/seed0076/QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json'; PLAN='control/QROS_PUBLIC_1000_SEED_0076_GATE_A_SHARD_PLAN_V213_v1.json'; ACTIVE='control/QROS_DETERMINISTIC_KERNEL_V251_ACTIVE_EXECUTION_VALIDATION_PASS_20260914_v1.json'; ENUM_B='scripts/qros_seed_universe_enumerator_b_v2.py'
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,x): Path(p).write_text(json.dumps(x,sort_keys=True,indent=2)+'\n',encoding='utf-8')
def run(cmd): return subprocess.run(cmd,text=True,capture_output=True)
def err(r):
    try:return json.loads((r.stderr or '').strip().splitlines()[-1]).get('error','')
    except:return (r.stderr or '')[-1000:]
def must(x,m):
    if not x: raise RuntimeError(m)
def copyrepo(src,dst): shutil.copytree(src,dst,ignore=shutil.ignore_patterns('.git','__pycache__'))
def pcmd(root,out): return [sys.executable,str(root/PRIMARY),'--repo-root',str(root),'--out',str(out)]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--out',required=True); a=ap.parse_args(); repo=Path(a.repo_root).resolve(); cases=[]
    with tempfile.TemporaryDirectory() as td0:
        td=Path(td0); base=td/'base.json'; r=run(pcmd(repo,base)); must(r.returncode==0,'baseline:'+r.stderr); cases.append({'case':'baseline','expected':'PASS','observed':'PASS'})
        def neg(name,mut,expect):
            root=td/name; copyrepo(repo,root); mut(root); o=root/'out.json'; rr=run(pcmd(root,o)); e=err(rr); must(rr.returncode!=0 and expect in e,f'{name}:{e}'); cases.append({'case':name,'expected':'FAIL_CLOSED:'+expect,'observed':'FAIL_CLOSED:'+e})
        def m_action(root):
            x=load(root/STABLE); x['machine_action_type']='BUILD_FIRST_GATE_SCORER'; dump(root/STABLE,x)
        neg('wrong_authorized_action',m_action,'ACTION_TYPE')
        def m_pnl(root):
            x=load(root/STABLE); x['economic_pnl_read']=True; dump(root/STABLE,x)
        neg('economic_firewall',m_pnl,'ECONOMIC_FIREWALL')
        def m_exec(root):
            x=load(root/STABLE); x['active_execution_validation_status']='PENDING'; dump(root/STABLE,x)
        neg('active_execution_not_pass',m_exec,'ACTIVE_EXEC_VALIDATION')
        def m_spec(root):
            x=load(root/SPEC); x['expected_counts']['raw_signal_configs']+=1; dump(root/SPEC,x)
        neg('v209_byte_mutation',m_spec,'PIN_MISMATCH')
        def m_plan(root):
            x=load(root/PLAN); x['universe']['management_root_sha256']='0'*64; dump(root/PLAN,x)
        neg('v213_byte_mutation',m_plan,'PIN_MISMATCH')
        def m_active(root):
            x=load(root/ACTIVE); x['status']='FAIL'; dump(root/ACTIVE,x)
        neg('active_receipt_byte_mutation',m_active,'PIN_MISMATCH')
        def m_enum(root):
            p=root/ENUM_B; p.write_text(p.read_text(encoding='utf-8')+'\n# mutation\n',encoding='utf-8')
        neg('independent_enumerator_byte_mutation',m_enum,'PIN_MISMATCH')
        # Independent oracle must reject a semantically altered primary receipt.
        bad=load(base); bad['ontology_root_sha256']='0'*64; badp=td/'bad_primary.json'; dump(badp,bad); oo=td/'oracle.json'; rr=run([sys.executable,str(repo/ORACLE),'--repo-root',str(repo),'--primary',str(badp),'--out',str(oo)]); e=err(rr); must(rr.returncode!=0 and 'ORACLE_PRIMARY_ROOT_MISMATCH' in e,'oracle altered primary:'+e); cases.append({'case':'oracle_rejects_altered_primary_root','expected':'FAIL_CLOSED:ORACLE_PRIMARY_ROOT_MISMATCH','observed':'FAIL_CLOSED:'+e})
    rec={'schema':'QROS_SEED0076_RISE_FIXED_POINT_ADVERSARIAL_1.0','status':'PASS','cases':cases,'negative_cases':8,'baseline_pass':True,'economic_firewall_tested':True,'byte_identity_tested':True,'independent_oracle_tamper_tested':True}; rec['receipt_sha256']=hashlib.sha256(json.dumps(rec,sort_keys=True,separators=(',',':')).encode()).hexdigest(); Path(a.out).write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n'); print(json.dumps({'status':'PASS','cases':len(cases),'receipt_sha256':rec['receipt_sha256']},sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
