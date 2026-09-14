#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

STABLE='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json'
CANDIDATE='control/QROS_PUBLIC_1000_EXECUTION_KERNEL_CANDIDATE_POINTER.json'
COMPILER='scripts/qros_execution_kernel_compile_v3.py'
ORACLE='scripts/qros_execution_kernel_oracle_v3.py'

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
def ccmd(root,target,out,validation=True):
    x=[sys.executable,str(root/COMPILER),'--repo-root',str(root),'--out',str(out)]
    if target: x += ['--target',target]
    if validation: x += ['--validation-only']
    return x

def direct_authority_pins(root: Path, tr: str):
    t=load(root/tr)
    for group in ('execution_kernel','authority'):
        for name,node in t.get(group,{}).items():
            if isinstance(node,dict) and node.get('path'):
                p=root/node['path']; must(p.is_file(),f'MISSING_DIRECT_AUTHORITY:{group}:{name}')
                want=node.get('git_blob_sha1'); must(isinstance(want,str) and len(want)==40,f'INVALID_DIRECT_PIN:{group}:{name}')
                got=blob(p); must(got==want,f'PIN_MISMATCH:{group}:{name}:{got}!={want}')
    return True

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--target',required=True); ap.add_argument('--out',required=True); a=ap.parse_args()
    repo=Path(a.repo_root).resolve(); tr=a.target; cases=[]
    direct_authority_pins(repo,tr)
    with tempfile.TemporaryDirectory() as td0:
        td=Path(td0); bp=td/'base.json'
        r=run(ccmd(repo,tr,bp,True)); must(r.returncode==0,r.stderr); base=load(bp)
        op=td/'oracle.json'; ro=run([sys.executable,str(repo/ORACLE),'--repo-root',str(repo),'--target',tr,'--validation-only','--primary-ticket',str(bp),'--out',str(op)])
        must(ro.returncode==0,ro.stderr); cases.append({'case':'baseline_primary_oracle','expected':'PASS','observed':'PASS','ticket_id':base['ticket_id']})

        def neg(name,mutate,expected,target=True,validation=True):
            root=td/name; copyrepo(repo,root); mutate(root); out=root/'ticket.json'
            rr=run(ccmd(root,tr if target else None,out,validation)); ec=code(rr)
            must(rr.returncode!=0 and expected in ec,f'{name}: {ec}')
            cases.append({'case':name,'expected':'FAIL_CLOSED:'+expected,'observed':'FAIL_CLOSED:'+ec})

        neg('parent_version_mismatch',lambda root:(lambda t:(t.__setitem__('supersedes_frontier_version','BAD_PARENT'),dump(root/tr,t)))(load(root/tr)),'CANDIDATE_PARENT_VERSION_MISMATCH')
        neg('parent_blob_mismatch',lambda root:(lambda t:(t.__setitem__('superseded_stable_pointer_blob_sha1','0'*40),dump(root/tr,t)))(load(root/tr)),'CANDIDATE_PARENT_BLOB_MISMATCH')
        neg('target_requires_validation_only',lambda root:None,'TARGET_REQUIRES_VALIDATION_ONLY',target=True,validation=False)

        # State-generic non-economic firewall: current frozen state is P01 and must reject economic_pnl_read=true.
        neg('economic_firewall',lambda root:(lambda t:(t.__setitem__('economic_pnl_read',True),dump(root/tr,t)))(load(root/tr)),'ECONOMIC_FLAG_MISMATCH')

        # Direct frozen authority byte mutation must be detected independently of chat state.
        def bad_authority(root):
            t=load(root/tr); n=t['authority']['minimal_dev_carrier_binding']; p=root/n; o=load(p); o['__mutation__']=1; dump(p,o)
        root=td/'direct_authority_pin'; copyrepo(repo,root); bad_authority(root)
        try:
            direct_authority_pins(root,tr); raise RuntimeError('direct_authority_pin: mutation accepted')
        except RuntimeError as e:
            must('PIN_MISMATCH:authority:minimal_dev_carrier_binding' in str(e),f'direct_authority_pin:{e}')
            cases.append({'case':'direct_authority_pin','expected':'FAIL_CLOSED:PIN_MISMATCH:authority:minimal_dev_carrier_binding','observed':'FAIL_CLOSED:'+str(e)})

        def make_active(root,validation='PASS',authorized=True,receipt_mode='valid',wrong_ticket=False):
            t=load(root/tr); s=load(root/STABLE)
            s.update({'current_version':t['version'],'target_path':tr,'target_git_blob_sha1':blob(root/tr),'active_validation_status':validation,'scientific_execution_authorized':authorized,'authorized_action_scope':'MACHINE_ACTION_TICKET_ONLY','machine_action_ticket_id':base['ticket_id'],'machine_action_type':base['action_type'],'machine_state_id':base['state_id'],'machine_subject':base['subject']})
            if wrong_ticket: s['machine_action_ticket_id']='0'*64
            if receipt_mode=='legacy_string': s['active_validation_receipt']='control/legacy.json'
            elif receipt_mode=='empty_dict': s['active_validation_receipt']={}
            elif receipt_mode=='bad_pin':
                rp='control/TEST_ACTIVE_VALIDATION_RECEIPT.json'; dump(root/rp,{'status':'PASS'}); s['active_validation_receipt']={'path':rp,'git_blob_sha1':'0'*40}
            elif receipt_mode=='valid':
                rp='control/TEST_ACTIVE_VALIDATION_RECEIPT.json'; dump(root/rp,{'status':'PASS'}); s['active_validation_receipt']={'path':rp,'git_blob_sha1':blob(root/rp)}
            dump(root/STABLE,s)

        neg('active_validation_pending',lambda root:make_active(root,validation='PENDING',authorized=False),'EXEC_LATCH_ACTIVE_VALIDATION_NOT_PASS',target=False,validation=False)
        neg('scientific_not_authorized',lambda root:make_active(root,validation='PASS',authorized=False),'EXEC_LATCH_SCIENTIFIC_NOT_AUTHORIZED',target=False,validation=False)
        neg('legacy_receipt_schema',lambda root:make_active(root,receipt_mode='legacy_string'),'EXEC_LATCH_RECEIPT_NODE',target=False,validation=False)
        neg('empty_receipt_node',lambda root:make_active(root,receipt_mode='empty_dict'),'PIN_MISSING:active_validation_receipt',target=False,validation=False)
        neg('bad_receipt_pin',lambda root:make_active(root,receipt_mode='bad_pin'),'PIN_MISMATCH:active_validation_receipt',target=False,validation=False)
        neg('stable_ticket_mismatch',lambda root:make_active(root,receipt_mode='valid',wrong_ticket=True),'EXEC_LATCH_TICKET_ID',target=False,validation=False)

        root=td/'free_text'; copyrepo(repo,root); t=load(root/tr); t['next_action']='MALICIOUS_FREE_TEXT'; dump(root/tr,t)
        rr=run(ccmd(root,tr,root/'t.json',True)); must(rr.returncode==0,rr.stderr); must(load(root/'t.json')==base,'free text changed ticket')
        cases.append({'case':'free_text_non_authority','expected':'IDENTICAL_TICKET','observed':'IDENTICAL_TICKET'})

        root=td/'future'; copyrepo(repo,root); t=load(root/tr); t['version']='V999999_GENERIC_TEST'; dump(root/tr,t); cp=load(root/CANDIDATE); cp['candidate_version']=t['version']; cp['candidate_target_git_blob_sha1']=blob(root/tr); dump(root/CANDIDATE,cp)
        rr=run(ccmd(root,tr,root/'t.json',True)); must(rr.returncode==0,rr.stderr); fut=load(root/'t.json'); must(fut['frontier_version']=='V999999_GENERIC_TEST' and fut['action_type']==base['action_type'],'future version hardcode')
        cases.append({'case':'generic_future_version_no_hardcode','expected':'PASS','observed':'PASS'})

    res={'schema':'QROS_DETERMINISTIC_EXECUTION_KERNEL_ADVERSARIAL_RECEIPT_6.0','status':'PASS','cases':cases,'negative_cases_require_expected_error_code':True,'negative_mutations':11,'positive_non_authority_tests':1,'generic_future_version_test':True,'direct_authority_pin_tested':True,'independent_oracle_executed':True,'state_generic_no_pre_scientific_blocker_dependency':True}
    raw=json.dumps(res,sort_keys=True,separators=(',',':')).encode(); res['receipt_sha256']=hashlib.sha256(raw).hexdigest(); Path(a.out).write_text(json.dumps(res,sort_keys=True,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'status':'PASS','cases':len(cases),'negative_mutations':11,'receipt_sha256':res['receipt_sha256']},sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
