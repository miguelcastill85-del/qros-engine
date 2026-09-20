#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from typing import FrozenSet, Optional

CAPABILITY_MAP={
 "NON_ECONOMIC_CONTROL_PLANE":None,
 "HEAVY_DATA":"CAP_NON_ECONOMIC_CONTROL",
 "REMATERIALIZATION":"CAP_REMATERIALIZE",
 "DEVELOPMENT_BACKTEST":"CAP_DEV_BACKTEST",
 "GATE_A":"CAP_GATE_A",
 "HOLDOUT":"CAP_HOLDOUT_OPEN",
 "SUPERGATE":"CAP_SUPERGATE",
 "MT5_PARITY":"CAP_MT5_PARITY",
 "PORTFOLIO_ANALYSIS":"CAP_PORTFOLIO_ANALYSIS",
 "GA1":"CAP_GA1",
 "GA2":"CAP_GA2",
 "ECONOMIC_PNL":"CAP_ECONOMIC_PNL_READ",
 "RECOVERY":"CAP_NON_ECONOMIC_CONTROL",
 "CHECKPOINTING":None,
 "CROSS_CHAT_CONTINUATION":None,
}

@dataclass(frozen=True)
class RouteRequest:
    execution_class:str
    durable_capabilities:FrozenSet[str]
    dek_transition_available:bool
    authority_ok:bool=True

def route(req:RouteRequest):
    if req.execution_class not in CAPABILITY_MAP:
        return {"status":"BLOCKED","reason":"UNKNOWN_EXECUTION_CLASS","schedule_dek":False}
    if not req.authority_ok:
        return {"status":"BLOCKED","reason":"AUTHORITY_NOT_RECONCILED","schedule_dek":False}
    need=CAPABILITY_MAP[req.execution_class]
    if need is not None and need not in req.durable_capabilities:
        return {"status":"BLOCKED","reason":"MISSING_CAPABILITY:"+need,"schedule_dek":False,"required_capability":need}
    if not req.dek_transition_available:
        return {"status":"CHECKPOINT","reason":"NO_DEK_TRANSITION","schedule_dek":False,"required_capability":need}
    return {
      "status":"SCHEDULE_ONE_DEK_TRANSITION",
      "reason":"AUTHORIZED_BY_EXTERNAL_DURABLE_CAPABILITY",
      "schedule_dek":True,
      "required_capability":need,
      "capabilities_after":sorted(req.durable_capabilities)
    }
