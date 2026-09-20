#!/usr/bin/env python3
import random
from qros_turn_enforcement_guard_v2 import *
def run(seed=20260920,episodes=10000):
    r=random.Random(seed)
    for i in range(episodes):
        s=State(invocation_id=f"E{i}",authority_ref="A")
        assert preflight(s,AUTHORITY_TX).allow
        s=postflight(s,AUTHORITY_TX,success=True)
        cap=r.choice(["LOCAL_RUNTIME","FILES","DRIVE","GITHUB"])
        pf=preflight(s,ACTION_TX,capability=cap,attempt_fingerprint=f"{cap}:{i}",
                     expected_bytes=100_000_000 if r.random()<.2 else 0,
                     expected_seconds=20 if r.random()<.2 else 0,adoptable=False)
        if not pf.allow: continue
        timeout=r.random()<.1; infra=(not timeout) and r.random()<.1
        success=not timeout and not infra and r.random()>.05
        s=postflight(s,ACTION_TX,success=success,timeout=timeout,infrastructure_error=infra,
                     capability=cap,attempt_fingerprint=f"{cap}:{i}")
        assert not preflight(s,ACTION_TX,capability="OTHER",attempt_fingerprint="other").allow
        assert preflight(s,PERSIST_TX).allow
        s=postflight(s,PERSIST_TX,success=True,durable=True)
        assert s.phase=="EXIT" and s.must_exit and s.checkpoint_persisted
        assert s.logical_transactions==3 and s.platform_calls<=MAX_PLATFORM_CALLS
    print(f"PASS_CHAOS_V2 episodes={episodes}")
if __name__=="__main__": run()
