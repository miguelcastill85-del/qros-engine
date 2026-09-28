#!/usr/bin/env python3
class TransitionGuardError(Exception): pass
TERMINAL={'FROZEN_CANDIDATE','REJECTED','OBSERVATIONAL_RESERVE','BRANCH_EXHAUSTED','APPROVED_RESEARCH','APPROVED_FINAL'}
def enforce_terminal_transition(target_scientific_state,reconstruction_certificate,capsule_root_sha256,registry_root_sha256):
  if target_scientific_state not in TERMINAL: return
  if not reconstruction_certificate: raise TransitionGuardError('RECONSTRUCTION_CERTIFICATE_REQUIRED')
  if reconstruction_certificate.get('status')!='PASS': raise TransitionGuardError('RECONSTRUCTION_CERTIFICATE_NOT_PASS')
  if reconstruction_certificate.get('capsule_root_sha256')!=capsule_root_sha256: raise TransitionGuardError('CAPSULE_ROOT_BINDING_MISMATCH')
  if reconstruction_certificate.get('registry_root_sha256')!=registry_root_sha256: raise TransitionGuardError('REGISTRY_ROOT_BINDING_MISMATCH')
  if reconstruction_certificate.get('r00_r19_all_pass') is not True: raise TransitionGuardError('R00_R19_NOT_ALL_PASS')
