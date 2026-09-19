from qros_fenced_runtime_lease_guard_v2 import *
def main():
 t=[]
 old=new_lease('J',9,1,'R1','2026-09-19T00:00:00Z','2026-09-19T02:00:00Z');assert validate_lease(old,'2026-09-19T00:30:00Z')[0];t.append('active_valid')
 cut={'status':'AUTHORIZED_MIGRATION_CUTOVER','old_lease_id':old['lease_id'],'old_lease_epoch':1,'old_fence_token':old['fence_token'],'old_epoch_promotion_revoked':True,'scientific_unit_same':True,'new_epoch':2}
 new=supersede_for_migration(old,'R2','2026-09-19T00:30:00Z','2026-09-19T03:00:00Z',cut);assert new['lease_epoch']==2;t.append('active_migration_supersession')
 r1={'status':'PASS','job_id':'J','group_index':9,'lease_epoch':1,'lease_id':old['lease_id'],'fence_token':old['fence_token']};assert not validate_worker_receipt(new,r1)[0];t.append('stale_epoch_rejected')
 r2={'status':'PASS','job_id':'J','group_index':9,'lease_epoch':2,'lease_id':new['lease_id'],'fence_token':new['fence_token']};assert validate_worker_receipt(new,r2)[0];t.append('new_epoch_accepted')
 bad=dict(cut);bad['old_epoch_promotion_revoked']=False
 try:supersede_for_migration(old,'R2','2026-09-19T00:30:00Z','2026-09-19T03:00:00Z',bad);raise AssertionError
 except RuntimeError:pass
 t.append('revocation_required')
 bad=dict(cut);bad['scientific_unit_same']=False
 try:supersede_for_migration(old,'R2','2026-09-19T00:30:00Z','2026-09-19T03:00:00Z',bad);raise AssertionError
 except RuntimeError:pass
 t.append('same_science_required')
 bad=dict(cut);bad['new_epoch']=3
 try:supersede_for_migration(old,'R2','2026-09-19T00:30:00Z','2026-09-19T03:00:00Z',bad);raise AssertionError
 except RuntimeError:pass
 t.append('monotonic_epoch_required')
 tam=dict(old);tam['fence_token']='x';assert not validate_lease(tam,'2026-09-19T00:30:00Z')[0];t.append('tamper_rejected')
 print('PASS',len(t),'/'+str(len(t)),','.join(t))
if __name__=='__main__':main()
