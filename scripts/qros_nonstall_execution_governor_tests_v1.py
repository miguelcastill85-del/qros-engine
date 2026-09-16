#!/usr/bin/env python3
from qros_nonstall_execution_governor_v1 import *
L={'lane_id':'SRL','base_head_sha':'aaa','branch':'srl','dependency_paths':['scripts/srl','governance/srl'],'started_at':'2026-09-15T20:00:00Z','expires_at':'2026-09-15T21:00:00Z','last_progress_at':'2026-09-15T20:30:00Z','progress_fingerprint':'fp0','state':'ACTIVE'}
c=[]
c.append(classify_main_drift(L,'aaa',[]).reason=='MAIN_UNCHANGED')
c.append(classify_main_drift(L,'bbb',['research/public/x']).reason=='ORTHOGONAL_MAIN_DRIFT')
c.append(classify_main_drift(L,'bbb',['scripts/srl/x']).action=='RECONCILE')
c.append(classify_main_drift(L,'bbb',[],terminal_premerge=True).action=='RECONCILE')
c.append(classify_main_drift(L,'bbb',[],pinned_dependency_invalidated=True).action=='RECONCILE')
c.append(can_reuse_receipt({'base_neutral':True,'content_sha256':'x'},'bbb'))
c.append(not can_reuse_receipt({'base_neutral':False,'base_head_sha':'aaa'},'bbb'))
p=progress_fingerprint(['h'],['u'],'c'); c.append(p==progress_fingerprint(['h'],['u'],'c'))
c.append(classify_progress(L,'2026-09-15T20:40:00Z','fp0',False,False,False)=='KEEP_RUNNING')
c.append(classify_progress(L,'2026-09-15T21:10:00Z','fp0',False,True,False)=='RECOVER_OUTPUT_THEN_VALIDATE')
c.append(classify_progress(L,'2026-09-15T21:10:00Z','fp0',True,False,False)=='RESUME_FROM_CHECKPOINT')
c.append(classify_progress(L,'2026-09-15T21:10:00Z','fp0',False,False,False)=='RELAUNCH_FROM_LAST_VALID_CHECKPOINT')
c.append(classify_progress(L,'2026-09-15T20:40:00Z','fp0',False,False,True)=='FREEZE_BLOCKED_LANE_CONTINUE_ORTHOGONAL')
c.append(all_lanes_blocked([{'state':'BLOCKED'},{'state':'BLOCKED'}]))
c.append(not all_lanes_blocked([{'state':'BLOCKED'},{'state':'ACTIVE'}]))
try:
  b=dict(L); b.pop('base_head_sha'); classify_main_drift(b,'bbb',[]); c.append(False)
except GovernorError: c.append(True)
print(f'QROS_NONSTALL_TESTS total={len(c)} pass={sum(c)} fail={len(c)-sum(c)}')
raise SystemExit(0 if all(c) else 2)
