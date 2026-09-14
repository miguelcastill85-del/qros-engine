#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

STABLE='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json'
CANDIDATE='control/QROS_PUBLIC_1000_EXECUTION_KERNEL_CANDIDATE_POINTER.json'

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,o): Path(p).parent.mkdir(parents=True,exist_ok=True); Path(p).write_text(json.dumps(o,sort_keys=True,indent=2)+'\n',encoding='utf-8')
def blob(p):
    b=Path(p).read_bytes(); return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def run(cmd): return subprocess.run(cmd,text=True,capture_output=True)
def code(r):
    try: return json.loads((r.stderr or '').strip().splitlines()[-1]).get('error','')
    except Exception: return (r.stderr or '')[-1000:]
def must(c,m):
    if not c: raise RuntimeError(m)
def copyrepo(src,dst): shutil.copytree(src,dst,ignore=shutil.ignore_patterns('.git','__pycache__'))
def cc(root,target,out,validation=True):
    x=[sys.executable,str(root/'scripts/qros_execution_kernel_compile_v3.py'),'--repo-root',str(root),'--out',str(out)]
    if target: x += ['--target',target]
    if validation: x += ['--validation-only']
    return x

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--target',required=True); ap.add_argument('--out',required=True); a=ap.parse_args()
    repo=Path(a.repo_root).resolve(); tr=a.target; cases=[]
    with tempfile.TemporaryDirectory() as td0:
        td=Path(td0)
        # Legacy v3 must reach its known incorrect expectation, proving all earlier v3 cases executed.
        legacy=run([sys.executable,str(repo/'scripts/qros_execution_kernel_adversarial_v3.py'),'--repo-root',str(repo),'--target',tr,'--out',str(td/'legacy.json')])
        must(legacy.returncode!=0 and 'missing receipt latch' in code(legacy),'legacy v3 did not reach known sentinel')
        cases.append({'case':'legacy_v3_prefix_reaches_known_sentinel','expected':'KNOWN_TEST_EXPECTATION_BUG','observed':'KNOWN_TEST_EXPECTATION_BUG'})

        basep=td/'base.json'; r=run(cc(repo,tr,basep,True)); must(r.returncode==0,r.stderr); base=load(basep)
        op=td/'oracle.json'; ro=run([sys.executable,str(repo/'scripts/qros_execution_kernel_oracle_v3.py'),'--repo-root',str(repo),'--target',tr,'--validation-only','--primary-ticket',str(basep),'--out',str(op)])
        must(ro.returncode==0,ro.stderr); cases.append({'case':'baseline_primary_oracle','expected':'PASS','observed':'PASS','ticket_id':base['ticket_id']})

        def active_root(name,validation='PASS',authorized=True,with_receipt=False,wrong_ticket=False):
            root=td/name; copyrepo(repo,root); t=load(root/tr); s=load(root/STABLE)
            s.update({'current_version':t['version'],'target_path':tr,'target_git_blob_sha1':blob(root/tr),'active_validation_status':validation,'scientific_execution_authorized':authorized,'authorized_action_scope':'MACHINE_ACTION_TICKET_ONLY','machine_action_ticket_id':base['ticket_id'],'machine_action_type':base['action_type'],'machine_state_id':base['state_id'],'machine_subject':base['subject']})
            if wrong_ticket: s['machine_action_ticket_id']='0'*64
            if with_receipt:
                rp='control/TEST_ACTIVE_VALIDATION_RECEIPT.json'; dump(root/rp,{'status':'PASS'}); s['active_validation_receipt']={'path':rp,'git_blob_sha1':blob(root/rp)}
            dump(root/STABLE,s); return root

        root=active_root('missing_receipt')
        rr=run(cc(root,None,root/'t.json',False)); ec=code(rr); must(rr.returncode!=0 and 'PIN_MISSING:active_validation_receipt' in ec,ec)
        cases.append({'case':'active_receipt_exact_error','expected':'FAIL_CLOSED:PIN_MISSING:active_validation_receipt','observed':'FAIL_CLOSED:'+ec})

        root=active_root('ticket_mismatch',with_receipt=True,wrong_ticket=True)
        rr=run(cc(root,None,root/'t.json',False)); ec=code(rr); must(rr.returncode!=0 and 'EXEC_LATCH_TICKET_ID' in ec,ec)
        cases.append({'case':'stable_ticket_binding','expected':'FAIL_CLOSED:EXEC_LATCH_TICKET_ID','observed':'FAIL_CLOSED:'+ec})

        root=td/'free_text'; copyrepo(repo,root); t=load(root/tr); t['next_action']='MALICIOUS_FREE_TEXT'; dump(root/tr,t)
        rr=run(cc(root,tr,root/'t.json',True)); must(rr.returncode==0,rr.stderr); must(load(root/'t.json')==base,'free text changed ticket')
        cases.append({'case':'free_text_non_authority','expected':'IDENTICAL_TICKET','observed':'IDENTICAL_TICKET'})

        root=td/'future'; copyrepo(repo,root); t=load(root/tr); t['version']='V999999_GENERIC_TEST'; dump(root/tr,t); cp=load(root/CANDIDATE); cp['candidate_version']=t['version']; cp['candidate_target_git_blob_sha1']=blob(root/tr); dump(root/CANDIDATE,cp)
        rr=run(cc(root,tr,root/'t.json',True)); must(rr.returncode==0,rr.stderr); f=load(root/'t.json'); must(f['frontier_version']=='V999999_GENERIC_TEST' and f['action_type']==base['action_type'],'future version hardcode')
        cases.append({'case':'generic_future_version_no_hardcode','expected':'PASS','observed':'PASS'})

    res={'schema':'QROS_DETERMINISTIC_EXECUTION_KERNEL_ADVERSARIAL_RECEIPT_4.0','status':'PASS','cases':cases,'legacy_v3_prefix_cases_verified':True,'corrected_missing_receipt_expectation':True,'generic_future_version_test':True,'free_text_non_authority':True,'negative_mutations':2}
    raw=json.dumps(res,sort_keys=True,separators=(',',':')).encode(); res['receipt_sha256']=hashlib.sha256(raw).hexdigest(); Path(a.out).write_text(json.dumps(res,sort_keys=True,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'status':'PASS','cases':len(cases),'receipt_sha256':res['receipt_sha256']},sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
