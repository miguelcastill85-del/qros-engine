from copy import deepcopy
from authority_role_reconciler import reconcile_roles, proposed_runtime_projection_v199

PATH='control/QROS_G30_V4_INVALIDATION_V5_EXECUTION_RECONCILIATION_V199_20260912_v1.json'
BLOB='b6ddd9c4a474035e31104cfa07104845f91c6a90'

def fixtures():
    head={'authority_epoch':199,'campaign':'G30','execution_lineage_reconciliation_ref':PATH,'scientific_change_class':'FORENSIC_EXECUTION_LINEAGE_CORRECTION_NO_SCIENTIFIC_RESELECTION','scientific_state':{'stage_b':'GLOBALLY_CLOSED_DO_NOT_RERUN','stage_c_results':'NOT_EXECUTED'},'forensic_recovery_state':{'NQX_6570_recovery_protocol':'IDENTIFIED_AND_DURABLY_MANIFESTED'},'remaining_execution_constraints':{'NQX_6570_final_rows':'MUST_BE_MATERIALIZED','F03_F12_descendant_execution_binding':'MUST_PASS_10_OF_10'},'next_action':'CONTINUE'}
    state={'authority_epoch':191,'campaign':'G30'}; queue={'authority_epoch':191,'campaign':'G30'}
    receipt={'authority_epoch':199,'campaign':'G30','status':'PASS_CORRECT_EXECUTION_LINEAGE_RECOVERED','scientific_change_class':'FORENSIC_AUTHORITY_CORRECTION_NO_NEW_SELECTION_NO_NEW_RESULTS'}
    return head,state,queue,receipt

def test_verified_scientific_head_runtime_stale_fail_closed():
    h,s,q,r=fixtures(); x=reconcile_roles(head=h,state=s,run_queue=q,head_receipt=r,head_receipt_path=PATH,head_receipt_blob_sha1=BLOB,engineering_reference_epoch=191)
    assert x.status=='SCIENTIFIC_HEAD_VERIFIED_RUNTIME_STALE_FAIL_CLOSED'; assert x.scientific_head_receipt_verified; assert not x.scientific_dispatch_authorized; assert x.engineering_reference_epoch==191

def test_tampered_receipt_epoch_fails():
    h,s,q,r=fixtures(); r['authority_epoch']=198
    assert reconcile_roles(head=h,state=s,run_queue=q,head_receipt=r,head_receipt_path=PATH,head_receipt_blob_sha1=BLOB).status.startswith('BLOCKED_')

def test_tampered_receipt_class_fails():
    h,s,q,r=fixtures(); r['scientific_change_class']='NEW_SELECTION'
    assert reconcile_roles(head=h,state=s,run_queue=q,head_receipt=r,head_receipt_path=PATH,head_receipt_blob_sha1=BLOB).status.startswith('BLOCKED_')

def test_wrong_receipt_path_fails():
    h,s,q,r=fixtures()
    assert reconcile_roles(head=h,state=s,run_queue=q,head_receipt=r,head_receipt_path='wrong',head_receipt_blob_sha1=BLOB).status.startswith('BLOCKED_')

def test_runtime_equal_still_reference_only():
    h,s,q,r=fixtures(); s['authority_epoch']=199; q['authority_epoch']=199
    x=reconcile_roles(head=h,state=s,run_queue=q,head_receipt=r,head_receipt_path=PATH,head_receipt_blob_sha1=BLOB,engineering_reference_epoch=191)
    assert x.status=='ROLE_SEPARATION_COHERENT_REFERENCE_ONLY'; assert not x.scientific_dispatch_authorized

def test_projection_is_non_authoritative_and_f13_excluded():
    h,_,_,_=fixtures(); p=proposed_runtime_projection_v199(h)
    assert p['authority_epoch']==199 and p['scientific_dispatch_authorized'] is False and p['promotion'] is False
    assert p['f13'].startswith('EXCLUDED') and p['tasks'][2]['status'].startswith('LOCKED')
