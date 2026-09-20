#!/usr/bin/env python3
from dataclasses import replace
import random
from qros_runtime_enforcement_guard_v1 import *

KINDS=sorted(ALL_KINDS)

def run(seed:int,episodes:int=10000,max_steps:int=30):
    rng=random.Random(seed)
    transitions=0
    denied=0
    timeouts=0
    for ep in range(episodes):
        st=State(invocation_id=f"E{ep}",authority_ref="A")
        for _ in range(max_steps):
            if st.must_exit:
                # Once must_exit is set, every non-persist attempt must be rejected.
                k=rng.choice(list(READ_KINDS|EXPENSIVE_KINDS))
                pf=preflight(st,k,expected_bytes=0,expected_seconds=0,adoptable=True,durable_intent=True)
                assert not pf.allow
                denied+=1
                break
            kind=rng.choice(KINDS)
            exp_bytes=rng.choice([0,1_000_000,49_999_999,50_000_001,100_000_000])
            exp_secs=rng.choice([0,1,4.9,5.1,20])
            adoptable=rng.choice([False,True])
            durable_intent=rng.choice([False,True])
            pf=preflight(st,kind,expected_bytes=exp_bytes,expected_seconds=exp_secs,
                         adoptable=adoptable,durable_intent=durable_intent,locator="L")
            if not pf.allow:
                denied+=1
                # Policy denials are terminal for this invocation in the envelope.
                st=replace(st,must_exit=True,blocked_reason=pf.reason)
                continue
            timeout=(rng.random()<0.02)
            success=not timeout and (rng.random()>0.05)
            evidence=(f"h{ep}-{transitions}" if rng.random()>0.25 else None)
            durable=(kind in PERSIST_KINDS and success)
            st=postflight(st,kind,success=success,evidence_hash=evidence,timeout=timeout,
                          durable=durable,effect_id_value=pf.effect_id)
            transitions+=1
            if timeout: timeouts+=1
            assert st.external_effects<=1, ("external effects",st)
            assert st.expensive_units<=1, ("expensive units",st)
            assert st.calls_used<=HARD_CAP_CALLS, ("hard cap",st)
            if st.calls_used>=CHECKPOINT_CALL:
                assert st.must_exit, ("checkpoint barrier",st)
            if st.terminal_durable:
                assert st.must_exit, ("terminal without exit",st)
    print(f"PASS_CHAOS episodes={episodes} transitions={transitions} denied={denied} timeouts={timeouts}")

if __name__=="__main__":
    run(20260920)
