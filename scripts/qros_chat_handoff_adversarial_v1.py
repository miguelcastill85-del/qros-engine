#!/usr/bin/env python3
import copy, hashlib, json, shutil, subprocess, tempfile
from pathlib import Path

ROOT=Path('.')
CP='control/QROS_PUBLIC_1000_CHAT_HANDOFF_CANDIDATE.json'
VAL=str(ROOT/'scripts/qros_chat_handoff_validate_v2.py')

def bsha(data): return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def rj(root,p): return json.loads((root/p).read_text())
def wj(root,p,obj):
    f=root/p; f.parent.mkdir(parents=True,exist_ok=True); f.write_text(json.dumps(obj,sort_keys=True,separators=(',',':'))+'\n')
def run(root):
    p=subprocess.run(['python3',VAL,'--root',str(root),'--candidate-pointer',CP],text=True,capture_output=True)
    try: out=json.loads(p.stdout.strip().splitlines()[-1])
    except Exception: out={'status':'BROKEN','stdout':p.stdout,'stderr':p.stderr}
    return p.returncode,out

def fixture():
    cp=rj(ROOT,CP); h=rj(ROOT,cp['handoff_path']); paths={CP,h['authority']['current_chat_handoff_pointer_path'],cp['handoff_path']}
    paths.update(e['path'] for e in h['bootstrap_manifest']['entries'])
    td=Path(tempfile.mkdtemp(prefix='qros_handoff_'))
    for p in paths:
        src=ROOT/p; dst=td/p; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    return td

def refresh_handoff(root):
    cp=rj(root,CP); hp=cp['handoff_path']; hb=(root/hp).read_bytes(); cp['handoff_git_blob_sha1']=bsha(hb); wj(root,CP,cp)

def mutate_handoff(root,fn):
    cp=rj(root,CP); hp=cp['handoff_path']; h=rj(root,hp); fn(h); wj(root,hp,h); refresh_handoff(root)

def refresh_stable(root):
    cp=rj(root,CP); hp=cp['handoff_path']; h=rj(root,hp)
    role=next(e for e in h['bootstrap_manifest']['entries'] if e['role']=='stable_scientific_pointer'); s=bsha((root/role['path']).read_bytes()); role['git_blob_sha1']=s; h['authority']['stable_scientific_pointer_expected']['git_blob_sha1']=s; wj(root,hp,h); refresh_handoff(root)

def refresh_target(root):
    cp=rj(root,CP); hp=cp['handoff_path']; h=rj(root,hp); tr=next(e for e in h['bootstrap_manifest']['entries'] if e['role']=='stable_target'); ts=bsha((root/tr['path']).read_bytes()); tr['git_blob_sha1']=ts; ex=h['authority']['stable_scientific_pointer_expected']; ex['target_git_blob_sha1']=ts
    strole=next(e for e in h['bootstrap_manifest']['entries'] if e['role']=='stable_scientific_pointer'); st=rj(root,strole['path']); st['target_git_blob_sha1']=ts; wj(root,strole['path'],st); wj(root,hp,h); refresh_stable(root)

def expect(name,mut,code):
    td=fixture()
    try:
        mut(td); rc,out=run(td)
        ok=rc!=0 and out.get('code')==code
        return {'name':name,'expected':code,'observed':out.get('code'),'pass':ok}
    finally: shutil.rmtree(td,ignore_errors=True)

def main():
    rc,base=run(ROOT)
    if rc!=0 or base.get('status')!='PASS':
        print(json.dumps({'status':'FAIL','code':'BASELINE_FAIL','detail':base},sort_keys=True)); raise SystemExit(2)
    cases=[]
    cases.append(expect('missing_role',lambda r: mutate_handoff(r,lambda h:h['bootstrap_manifest']['entries'].pop()),'BOOTSTRAP_ALLOWED_ROLE_SET'))
    def extra(r):
        def f(h):
            h['bootstrap_manifest']['entries'].append({'role':'unauthorized_extra','path':h['authority']['current_chat_handoff_pointer_path'],'git_blob_sha1':bsha((r/h['authority']['current_chat_handoff_pointer_path']).read_bytes())}); h['bootstrap_manifest']['required_roles'].append('unauthorized_extra')
        mutate_handoff(r,f)
    cases.append(expect('extra_dependency',extra,'BOOTSTRAP_ALLOWED_ROLE_SET'))
    def badpin(r):
        mutate_handoff(r,lambda h:h['bootstrap_manifest']['entries'][0].__setitem__('git_blob_sha1','0'*40))
    cases.append(expect('wrong_dependency_pin',badpin,'DEPENDENCY_BLOB_MISMATCH'))
    cases.append(expect('stale_stable_pointer',lambda r: mutate_handoff(r,lambda h:h['authority']['stable_scientific_pointer_expected'].__setitem__('git_blob_sha1','1'*40)),'STALE_HANDOFF_STABLE_POINTER'))
    cases.append(expect('ticket_changed',lambda r: mutate_handoff(r,lambda h:h['machine_ticket'].__setitem__('ticket_id','2'*64)),'TICKET_MISMATCH_TICKET_ID'))
    cases.append(expect('precedence_changed',lambda r: mutate_handoff(r,lambda h:h['authority_precedence'].__setitem__('immutable_candidate_target_role','DYNAMIC_AUTHORITY')),'PRECEDENCE_TARGET'))
    cases.append(expect('search_enabled',lambda r: mutate_handoff(r,lambda h:h['bootstrap_manifest'].__setitem__('normal_execution_repository_search_allowed',True)),'BOOTSTRAP_SEARCH_POLICY'))
    cases.append(expect('capsule_false_claim',lambda r: mutate_handoff(r,lambda h:h['architecture_defect'].__setitem__('execution_capsule_status','IMPLEMENTED')),'CAPSULE_GAP_STATE'))
    def pnl(r):
        cp=rj(r,CP); h=rj(r,cp['handoff_path']); e=next(x for x in h['bootstrap_manifest']['entries'] if x['role']=='stable_scientific_pointer'); st=rj(r,e['path']); st['economic_pnl_read']=True; wj(r,e['path'],st); refresh_stable(r)
    cases.append(expect('economic_pnl_opened',pnl,'FIREWALL_ECONOMIC_PNL_READ'))
    def target_latch(r):
        cp=rj(r,CP); h=rj(r,cp['handoff_path']); e=next(x for x in h['bootstrap_manifest']['entries'] if x['role']=='stable_target'); tg=rj(r,e['path']); tg['scientific_execution_authorized']=True; wj(r,e['path'],tg); refresh_target(r)
    cases.append(expect('target_latch_promoted',target_latch,'TARGET_PREPROMOTION_LATCH'))
    ok=all(c['pass'] for c in cases); receipt=hashlib.sha256(json.dumps(cases,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    print(json.dumps({'status':'PASS' if ok else 'FAIL','baseline':base,'cases':len(cases),'negative_mutations':len(cases),'results':cases,'receipt_sha256':receipt},sort_keys=True,separators=(',',':')))
    raise SystemExit(0 if ok else 2)
if __name__=='__main__': main()
