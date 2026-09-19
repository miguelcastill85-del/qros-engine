import copy
from qros_legacy_authority_fence_v1 import validate_cutover,validate_promotion

def base():
  legacy={'status':'RUNNING_ADOPTABLE','subject':{'structural_group_index':9},'runtime':{'job_id':'OLD','job_spec_sha256':'S','claim_token':'C','bootstrap_birth':'linux:B:1','worker_birth':'linux:B:2'}}
  cut={'status':'ACTIVE','group_index':9,'capsule_blob_sha1':'CAP','legacy_job_id':'OLD','legacy_job_spec_sha256':'S','legacy_claim_token':'C','legacy_bootstrap_birth':'linux:B:1','legacy_worker_birth':'linux:B:2','legacy_promotion_revoked':True,'terminal_receipt_absent_at_cutover':True,'recovery_job_id':'NEW'}
  return legacy,cut

def main():
  t=[];l,c=base();assert validate_cutover(c,l)[0];t.append('cutover_pass')
  for key in ['legacy_job_id','legacy_job_spec_sha256','legacy_claim_token','legacy_bootstrap_birth','legacy_worker_birth']:
    l,c=base();c[key]='X';assert not validate_cutover(c,l)[0];t.append('mismatch_'+key)
  l,c=base();c['legacy_promotion_revoked']=False;assert not validate_cutover(c,l)[0];t.append('revocation_required')
  l,c=base();c['terminal_receipt_absent_at_cutover']=False;assert not validate_cutover(c,l)[0];t.append('absence_proof_required')
  l,c=base();assert not validate_promotion(c,{'status':'PASS','job_id':'OLD','group_index':9,'capsule_blob_sha1':'CAP'})[0];t.append('late_legacy_rejected')
  l,c=base();assert validate_promotion(c,{'status':'PASS','job_id':'NEW','group_index':9,'capsule_blob_sha1':'CAP'})[0];t.append('recovery_promotes')
  l,c=base();assert not validate_promotion(c,{'status':'PASS','job_id':'OTHER','group_index':9,'capsule_blob_sha1':'CAP'})[0];t.append('other_job_rejected')
  l,c=base();assert not validate_promotion(c,{'status':'PASS','job_id':'NEW','group_index':8,'capsule_blob_sha1':'CAP'})[0];t.append('group_mismatch_rejected')
  l,c=base();assert not validate_promotion(c,{'status':'PASS','job_id':'NEW','group_index':9,'capsule_blob_sha1':'BAD'})[0];t.append('capsule_mismatch_rejected')
  print('PASS',len(t),'/'+str(len(t)),','.join(t))
if __name__=='__main__':main()
