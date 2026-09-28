#!/usr/bin/env python3
import argparse,json,re
from pathlib import Path
TERMINAL={'FROZEN_CANDIDATE','REJECTED','OBSERVATIONAL_RESERVE','BRANCH_EXHAUSTED','APPROVED_RESEARCH','APPROVED_FINAL'}
HEX64=re.compile(r'^[0-9a-f]{64}$')
class GuardError(Exception): pass
def _walk(x,path='$'):
    if isinstance(x,dict):
        if 'scientific_state' in x: yield x,path
        for k,v in x.items(): yield from _walk(v,path+'.'+str(k))
    elif isinstance(x,list):
        for i,v in enumerate(x): yield from _walk(v,f'{path}[{i}]')
def validate_document(doc):
    found=0
    for node,path in _walk(doc):
        state=node.get('scientific_state')
        if state not in TERMINAL: continue
        found+=1
        s=node.get('srl_reconstruction')
        if not isinstance(s,dict): raise GuardError(f'{path}:SRL_RECONSTRUCTION_REQUIRED')
        if s.get('certificate_status')!='PASS': raise GuardError(f'{path}:SRL_CERTIFICATE_NOT_PASS')
        if not HEX64.match(str(s.get('capsule_root_sha256',''))): raise GuardError(f'{path}:CAPSULE_ROOT_INVALID')
        if not HEX64.match(str(s.get('registry_root_sha256',''))): raise GuardError(f'{path}:REGISTRY_ROOT_INVALID')
        if s.get('r00_r19_all_pass') is not True: raise GuardError(f'{path}:R00_R19_NOT_ALL_PASS')
    return found
def validate_file(path):
    p=Path(path)
    if p.suffix.lower()!='.json': return 0
    try: doc=json.loads(p.read_text(encoding='utf-8'))
    except Exception as e: raise GuardError(f'{p}:JSON_INVALID:{type(e).__name__}')
    return validate_document(doc)
def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument('files',nargs='*'); ns=ap.parse_args(argv); total=0
    try:
        for f in ns.files:
            if Path(f).exists(): total+=validate_file(f)
    except GuardError as e:
        print('QROS_SRL_TERMINAL_DOCUMENT_GUARD=FAIL',e); return 2
    print(f'QROS_SRL_TERMINAL_DOCUMENT_GUARD=PASS terminal_nodes={total} files={len(ns.files)}'); return 0
if __name__=='__main__': raise SystemExit(main())
