from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

SAFE_FORENSIC_HEAD_CLASSES={'FORENSIC_EXECUTION_LINEAGE_CORRECTION_NO_SCIENTIFIC_RESELECTION'}
SAFE_FORENSIC_RECEIPT_CLASSES={'FORENSIC_AUTHORITY_CORRECTION_NO_NEW_SELECTION_NO_NEW_RESULTS'}

@dataclass(frozen=True)
class RoleReconciliation:
    status:str
    scientific_head_epoch:Optional[int]
    runtime_state_epoch:Optional[int]
    runtime_queue_epoch:Optional[int]
    engineering_reference_epoch:Optional[int]
    scientific_head_receipt_verified:bool
    runtime_stale:bool
    scientific_dispatch_authorized:bool
    reason:str
    def to_dict(self): return asdict(self)

def reconcile_roles(*, head:Dict[str,Any], state:Dict[str,Any], run_queue:Dict[str,Any], head_receipt:Dict[str,Any], head_receipt_path:str, head_receipt_blob_sha1:str, engineering_reference_epoch:Optional[int]=None)->RoleReconciliation:
    he=head.get('authority_epoch'); se=state.get('authority_epoch'); qe=run_queue.get('authority_epoch')
    campaigns={head.get('campaign'),state.get('campaign'),run_queue.get('campaign'),head_receipt.get('campaign')}
    receipt_verified=(isinstance(he,int) and head_receipt.get('authority_epoch')==he and len(campaigns)==1 and None not in campaigns and head.get('execution_lineage_reconciliation_ref')==head_receipt_path and isinstance(head_receipt_blob_sha1,str) and len(head_receipt_blob_sha1)==40 and head.get('scientific_change_class') in SAFE_FORENSIC_HEAD_CLASSES and head_receipt.get('scientific_change_class') in SAFE_FORENSIC_RECEIPT_CLASSES and str(head_receipt.get('status','')).startswith('PASS_'))
    if not receipt_verified:
        return RoleReconciliation('BLOCKED_UNVERIFIED_SCIENTIFIC_HEAD_RECEIPT',he,se,qe,engineering_reference_epoch,False,True,False,'Head-specific receipt does not satisfy frozen forensic no-reselection contract')
    runtime_stale=not (se==he and qe==he)
    if runtime_stale:
        return RoleReconciliation('SCIENTIFIC_HEAD_VERIFIED_RUNTIME_STALE_FAIL_CLOSED',he,se,qe,engineering_reference_epoch,True,True,False,'Scientific HEAD receipt is coherent, but execution STATE/RUN_QUEUE are older or split; no dispatch until explicit runtime reconciliation')
    return RoleReconciliation('ROLE_SEPARATION_COHERENT_REFERENCE_ONLY',he,se,qe,engineering_reference_epoch,True,False,False,'Role coherence observed; QSLE remains non-authoritative absent promotion receipt')

def proposed_runtime_projection_v199(head:Dict[str,Any])->Dict[str,Any]:
    if head.get('authority_epoch')!=199: raise ValueError('EXPECTED_V199_HEAD')
    sci=head.get('scientific_state',{}); recovery=head.get('forensic_recovery_state',{}); constraints=head.get('remaining_execution_constraints',{})
    return {'schema':'QSLE_NON_AUTHORITATIVE_RUNTIME_PROJECTION_V1','authority_epoch':199,'campaign':head.get('campaign'),'role':'EXECUTION_RUNTIME_PROJECTION_ONLY','scientific_dispatch_authorized':False,'f13':'EXCLUDED_DO_NOT_SEARCH_DO_NOT_RECOVER_DO_NOT_EXECUTE','stage_b':sci.get('stage_b'),'stage_c_results':sci.get('stage_c_results'),'tasks':[{'id':'RECONCILE_F03_F12_DESCENDANT_BINDINGS','status':'PENDING','contract':constraints.get('F03_F12_descendant_execution_binding')},{'id':'MATERIALIZE_NQX_6570','status':'PENDING','contract':constraints.get('NQX_6570_final_rows'),'observed_recovery':recovery.get('NQX_6570_recovery_protocol')},{'id':'STAGE_C_ECONOMIC_EXECUTION','status':'LOCKED_PENDING_PRIOR_TWO_PASS'}],'source_head_next_action':head.get('next_action'),'promotion':False}
