#!/usr/bin/env python3
from qros_srl_terminal_state_guard_v1 import *
G={'status':'PASS','capsule_root_sha256':'c','registry_root_sha256':'r','r00_r19_all_pass':True}
def fail(**kw):
  try: enforce_terminal_transition(**kw); return False
  except TransitionGuardError: return True
c=[]
enforce_terminal_transition('DEVELOPMENT_RUNNING',None,None,None); c.append(True)
enforce_terminal_transition('REJECTED',G,'c','r'); c.append(True)
c.append(fail(target_scientific_state='REJECTED',reconstruction_certificate=None,capsule_root_sha256='c',registry_root_sha256='r'))
c.append(fail(target_scientific_state='APPROVED_FINAL',reconstruction_certificate={**G,'status':'FAIL'},capsule_root_sha256='c',registry_root_sha256='r'))
c.append(fail(target_scientific_state='BRANCH_EXHAUSTED',reconstruction_certificate=G,capsule_root_sha256='x',registry_root_sha256='r'))
c.append(fail(target_scientific_state='OBSERVATIONAL_RESERVE',reconstruction_certificate=G,capsule_root_sha256='c',registry_root_sha256='x'))
c.append(fail(target_scientific_state='APPROVED_RESEARCH',reconstruction_certificate={**G,'r00_r19_all_pass':False},capsule_root_sha256='c',registry_root_sha256='r'))
print(f'QROS_SRL_TRANSITION_GUARD_TESTS total={len(c)} pass={sum(c)} fail={len(c)-sum(c)}')
raise SystemExit(0 if all(c) else 2)
