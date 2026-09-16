#!/usr/bin/env python3
from qros_srl_terminal_document_guard_v1 import validate_document,GuardError
H='a'*64; G='b'*64
GOOD={'scientific_state':'REJECTED','srl_reconstruction':{'certificate_status':'PASS','capsule_root_sha256':H,'registry_root_sha256':G,'r00_r19_all_pass':True}}
def fails(d):
  try: validate_document(d); return False
  except GuardError: return True
c=[]
c.append(validate_document({'scientific_state':'DEVELOPMENT_RUNNING'})==0)
c.append(validate_document(GOOD)==1)
c.append(validate_document({'outer':[GOOD]})==1)
c.append(fails({'scientific_state':'REJECTED'}))
c.append(fails({'scientific_state':'APPROVED_FINAL','srl_reconstruction':{}}))
c.append(fails({'scientific_state':'BRANCH_EXHAUSTED','srl_reconstruction':{**GOOD['srl_reconstruction'],'capsule_root_sha256':'bad'}}))
c.append(fails({'scientific_state':'APPROVED_RESEARCH','srl_reconstruction':{**GOOD['srl_reconstruction'],'r00_r19_all_pass':False}}))
print(f'QROS_SRL_TERMINAL_DOCUMENT_GUARD_TESTS total={len(c)} pass={sum(c)} fail={len(c)-sum(c)}')
raise SystemExit(0 if all(c) else 2)
