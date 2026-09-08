# Candidate 3 changelog

Parent: Candidate 2 (offline 55/0). Candidate 2 is not deployable.

Candidate 3 adds cross-version containment discovered during independent audit:
- moved executor CERT/HB/ARMED from QDB1.EXEC.* to Q24.EXEC.*;
- moved DIV3 warm-up progress from QDB1.3.INIT_* to Q24.3.INIT_*;
- introduced version-specific arm token QROS_DEMO_ARM_v224_8af000_2d6ebd;
- bootstrap no longer closes unrelated charts; chart provisioning is explicit opt-in and defaults false;
- retained all Candidate 2 execution-safety state machine, reconciliation, risk, bus, recovery and ledger changes;
- alpha/economic emitter parity remains unchanged after normalization of infrastructure-only lines.

No alpha, risk percentage, priority, holdout or economic-selection rule was changed.
