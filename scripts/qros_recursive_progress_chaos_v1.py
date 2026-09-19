#!/usr/bin/env python3
import random
from dataclasses import replace
from qros_recursive_progress_kernel_v1 import *

rnd=random.Random(260919)
EPISODES=10000
MAX_STEPS=40
crashes=effects=terminal=0
for ep in range(EPISODES):
    s=State(campaign_id="C",unit_id=f"U{ep}")
    inputs_ready=False; output=False; terminal_receipt=None; runtime=None
    for step in range(MAX_STEPS):
        o=Observation(
            authority_ok=rnd.random()>0.001,
            terminal_receipt=terminal_receipt,
            exact_outputs_present=output,
            exact_outputs_valid=output,
            inputs_ready=inputs_ready,
            direct_locator_available=rnd.random()<0.65,
            connector_blobs_available=rnd.random()<0.9,
            same_runtime_claim_live=s.open_effect_id is not None and runtime=="R" and rnd.random()<0.35,
            foreign_runtime_claim=s.open_effect_id is not None and runtime=="OLD" and rnd.random()<0.65,
            proven_dead=s.open_effect_id is not None and rnd.random()<0.08,
            fencing_supported=True,
            cas_conflict=rnd.random()<0.002,
            current_runtime_id="R",
            evidence_hash=sha256_obj({"ep":ep,"step":step,"inputs":inputs_ready,"output":output,"term":terminal_receipt}) if rnd.random()<0.7 else s.last_evidence_hash,
            route_failed=rnd.random()<0.02,
            connector_write_blocked=rnd.random()<0.002,
        )
        t=compile_transition(s,o)
        assert t.action not in FORBIDDEN
        assert t.durable_before_effect
        if t.effect: effects+=1
        ns=t.next_state
        if rnd.random()<0.12:
            crashes+=1
            assert compile_transition(s,o)==t
        if t.action in {"MATERIALIZE_DIRECT_LOCATOR","FETCH_EXACT_CONNECTOR_BLOBS"}:
            if rnd.random()<0.88:
                inputs_ready=True
                ns=replace(ns,open_effect_id=None,open_effect_action=None,phase="READY")
        elif t.action=="LAUNCH_EXACTLY_ONCE":
            runtime="R"
            if rnd.random()<0.55:
                output=True; runtime=None
        elif t.action=="FENCED_CUTOVER":
            runtime=None
            ns=replace(ns,open_effect_id=None,open_effect_action=None,phase="READY")
        elif t.action=="VALIDATE_EXISTING_OUTPUTS":
            terminal_receipt="PASS"
        elif t.action=="ADVANCE_UNIT":
            terminal+=1; break
        elif t.action in {"BLOCK_DURABLE","FAIL_CLOSED"}:
            terminal+=1; break
        elif t.action=="CHECKPOINT_EXIT":
            ns=replace(ns,call_count=0)
        s=ns
    else:
        assert s.last_action is not None
print(f"PASS episodes={EPISODES} max_steps={MAX_STEPS} crashes={crashes} effects={effects} terminal={terminal}")
