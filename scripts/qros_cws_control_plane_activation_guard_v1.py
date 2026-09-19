#!/usr/bin/env python3
from __future__ import annotations

FORBIDDEN_FLAGS=("economic_pnl_read","holdout_open","ga2_open","new_ga1_authorized","first_gate_execution_authorized")
REQUIRED_RECEIPTS=(
 "CWS_V1_1_EXTERNAL_VALIDATION_PASS",
 "CWS_AUTOCHAIN_TERMINAL_PASS",
 "CWS_SELF_APPLICATION_GATE_PASS",
 "CWS_W09C_SHADOW_PASS",
)

def evaluate(receipts,frontier,checkpoint,dek_status,cws_status,next_action,requested_capability):
    missing=[r for r in REQUIRED_RECEIPTS if receipts.get(r)!="PASS"]
    if missing:
        return {"status":"PENDING","reason":"MISSING_PREREQUISITES","missing":missing}
    if dek_status!="FROZEN_ACTIVE":
        return {"status":"BLOCKED","reason":"DEK_NOT_ACTIVE"}
    if cws_status!="VALIDATED_DESIGN_AUTOCHAIN_SHADOW_PASS":
        return {"status":"BLOCKED","reason":"CWS_STATUS"}
    if requested_capability!="CAP_NON_ECONOMIC_CONTROL":
        return {"status":"BLOCKED","reason":"CAPABILITY"}
    for f in FORBIDDEN_FLAGS:
        if frontier.get(f) is not False or checkpoint.get(f) is not False:
            return {"status":"BLOCKED","reason":"SCIENTIFIC_FIREWALL:"+f}
    if not isinstance(next_action,str) or not next_action.startswith("DEK_V3_ACTIVE:"):
        return {"status":"BLOCKED","reason":"NON_DEK_ACTION"}
    return {
      "status":"ELIGIBLE_CONTROL_PLANE_SHADOW_ACTIVE",
      "reason":"ALL_GATES_PASS",
      "scientific_effect":"NONE",
      "allowed_capability":"CAP_NON_ECONOMIC_CONTROL"
    }
