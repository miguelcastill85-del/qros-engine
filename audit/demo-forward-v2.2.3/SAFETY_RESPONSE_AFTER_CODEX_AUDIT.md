# Safety response after Codex audit

Date: 2026-09-07

Authority audit commit: `abcbaaa85b6161e786347d1248119cd7cf2f5ae1`

Decision imported from Codex: `CRITICAL_REPLACEMENT_REQUIRED` (`INFERRED`).

The active Darwinex-Demo v2.2.3 runtime is not to be patched in place. The audit did not observe an active incident, but exact-source findings F01, F03 and F04 are critical execution-safety defects and invalidate unconditional continuation of new-entry execution.

## Operational containment

Until a fully certified descendant is available, new entries should be paused while preserving the running terminal and any existing position-management path. The intended containment state is `QDB1.EXEC.CERT=0` with Algo Trading otherwise left enabled. In the frozen executor, `SendEntry()` blocks armed entries when runtime certification is false, while `HandleModify`, `HandleClose` and `ForceNoOvernight` do not require CERT. This containment does not cure F03/F04; therefore an already-open position must not be treated as fully safe merely because new entries are blocked.

The paused interval must be recorded as `FORWARD_PAUSED_BY_SAFETY_AUDIT` and excluded from claims of uninterrupted prospective execution.

## Replacement branch

Engineering descendant branch: `fix/demo-forward-v2.2.4-hardening-20260907`.

v2.2.4 must implement the replacement contract from the audit and may not deploy until all gates pass again: exact-source import, MetaEditor compile 0/0, parent-child parity, controller parity, forward module certificates, combined canary, START_RECEIPT, and armed runtime `CERT=1`.

No alpha, signal, risk percentage, module priority, holdout or G30 rule may change as part of this replacement.
