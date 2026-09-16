#!/usr/bin/env python3
"""QROS non-stall authority-lease governor."""
from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from datetime import datetime,timezone
class GovernorError(Exception): pass
def fp(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def overlap(changed,deps):
  for c in changed:
    c=c.rstrip('/')
    for d in deps:
      d=d.rstrip('/')
      if c==d or c.startswith(d+'/') or d.startswith(c+'/'): return True
  return False
@dataclass(frozen=True)
class LeaseDecision:
  action:str; reason:str; reconcile_required:bool; keep_branch_authority:bool
def classify_main_drift(lease,live_main_sha,changed_paths,terminal_premerge=False,pinned_dependency_invalidated=False):
  req={'lane_id','base_head_sha','branch','dependency_paths','started_at','expires_at','last_progress_at','progress_fingerprint','state'}
  if not req.issubset(lease): raise GovernorError('LEASE_FIELDS_MISSING')
  if live_main_sha==lease['base_head_sha']: return LeaseDecision('CONTINUE','MAIN_UNCHANGED',False,True)
  if terminal_premerge: return LeaseDecision('RECONCILE','TERMINAL_PREMERGE_ALWAYS_RECONCILES',True,False)
  if pinned_dependency_invalidated: return LeaseDecision('RECONCILE','PINNED_DEPENDENCY_INVALIDATED',True,False)
  if overlap(changed_paths,lease['dependency_paths']): return LeaseDecision('RECONCILE','OVERLAPPING_MAIN_DRIFT',True,False)
  return LeaseDecision('CONTINUE','ORTHOGONAL_MAIN_DRIFT',False,True)
def classify_progress(lease,now_iso,observed_progress_fingerprint,partial_checkpoint_present,durable_output_present,declared_blocker):
  if declared_blocker: return 'FREEZE_BLOCKED_LANE_CONTINUE_ORTHOGONAL'
  now=datetime.fromisoformat(now_iso.replace('Z','+00:00')).astimezone(timezone.utc)
  exp=datetime.fromisoformat(lease['expires_at'].replace('Z','+00:00')).astimezone(timezone.utc)
  if observed_progress_fingerprint!=lease['progress_fingerprint']: return 'PROGRESS_ADVANCED_RENEW_LEASE'
  if now<=exp: return 'KEEP_RUNNING'
  if durable_output_present: return 'RECOVER_OUTPUT_THEN_VALIDATE'
  if partial_checkpoint_present: return 'RESUME_FROM_CHECKPOINT'
  return 'RELAUNCH_FROM_LAST_VALID_CHECKPOINT'
def progress_fingerprint(hashes,units,checkpoint): return fp({'durable_artifact_hashes':sorted(hashes),'completed_units':sorted(units),'current_checkpoint':checkpoint})
def can_reuse_receipt(receipt,new_base_sha): return bool(receipt.get('content_sha256')) if receipt.get('base_neutral') is True else receipt.get('base_head_sha')==new_base_sha
def all_lanes_blocked(lanes): return bool(lanes) and all(x.get('state')=='BLOCKED' for x in lanes)
