#!/usr/bin/env python3
from __future__ import annotations
import json,random
from qros_cws_global_execution_router_v1 import CAPABILITY_MAP,RouteRequest,route

def main():
    # full class coverage
    expected={
      "NON_ECONOMIC_CONTROL_PLANE","HEAVY_DATA","REMATERIALIZATION","DEVELOPMENT_BACKTEST","GATE_A","HOLDOUT",
      "SUPERGATE","MT5_PARITY","PORTFOLIO_ANALYSIS","GA1","GA2","ECONOMIC_PNL","RECOVERY","CHECKPOINTING","CROSS_CHAT_CONTINUATION"
    }
    assert set(CAPABILITY_MAP)==expected

    # every guarded class blocks without its capability
    for cls,cap in CAPABILITY_MAP.items():
        out=route(RouteRequest(cls,frozenset(),True,True))
        if cap is None:
            assert out["status"]=="SCHEDULE_ONE_DEK_TRANSITION"
        else:
            assert out["status"]=="BLOCKED" and out["schedule_dek"] is False and out["required_capability"]==cap

    # with exact durable capability, exactly one DEK step is eligible
    for cls,cap in CAPABILITY_MAP.items():
        caps=frozenset() if cap is None else frozenset({cap})
        out=route(RouteRequest(cls,caps,True,True))
        assert out["status"]=="SCHEDULE_ONE_DEK_TRANSITION"
        assert out["schedule_dek"] is True
        assert out["capabilities_after"]==sorted(caps)

    # no authority / no transition always fail closed or checkpoint
    for cls,cap in CAPABILITY_MAP.items():
        caps=frozenset() if cap is None else frozenset({cap})
        assert route(RouteRequest(cls,caps,True,False))["status"]=="BLOCKED"
        assert route(RouteRequest(cls,caps,False,True))["status"]=="CHECKPOINT"

    # unknown classes never route
    assert route(RouteRequest("BYPASS_DIRECT_RUNNER",frozenset({"CAP_ECONOMIC_PNL_READ"}),True,True))["status"]=="BLOCKED"

    rng=random.Random(20260919)
    unsafe=0
    scheduled=0
    cases=100000
    classes=list(CAPABILITY_MAP)
    allcaps={c for c in CAPABILITY_MAP.values() if c}
    for _ in range(cases):
        cls=rng.choice(classes)
        need=CAPABILITY_MAP[cls]
        caps=set(rng.sample(sorted(allcaps),rng.randrange(0,min(4,len(allcaps))+1)))
        authority_ok=rng.random()>.05
        transition=rng.random()>.05
        before=frozenset(caps)
        out=route(RouteRequest(cls,before,transition,authority_ok))
        if out["schedule_dek"]:
            scheduled+=1
            if not authority_ok or not transition: unsafe+=1
            if need is not None and need not in before: unsafe+=1
            if frozenset(out["capabilities_after"])!=before: unsafe+=1
        else:
            if need is not None and need not in before:
                assert out["status"] in {"BLOCKED","CHECKPOINT"}
    assert unsafe==0
    print(json.dumps({
      "status":"PASS",
      "execution_classes":len(classes),
      "adversarial_cases":cases,
      "scheduled_cases":scheduled,
      "unsafe_schedule":unsafe
    },sort_keys=True))
if __name__=="__main__": main()
