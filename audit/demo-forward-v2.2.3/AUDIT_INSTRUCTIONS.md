# QROS Darwinex Demo Forward v2.2.3 — Codex audit handoff

## Freeze and operational boundary

- Repository: `miguelcastill85-del/qros-engine`
- Audit branch: `audit/demo-forward-v2.2.3-frozen-20260907`
- Branch originated from `main` commit `543cc1c688c5c245f8ffb19ea48daf5d449297d9`.
- Frozen deployment package: `QROS_DARWINEX_DEMO_DEPLOYMENT_RUNTIME_v2_2_3.zip`
- Package bytes: `134189`
- Package SHA-256: `6e732d59808b768d84ad3a1f734a08a608262192c1f78b2e7143141b461fccde`
- MT5 deployment build: `6182`
- Scientific state: `FROZEN_NO_RETUNE`
- Operational state observed at handoff: Darwinex-Demo forward ACTIVE. The running terminal is outside this audit and MUST NOT be modified, restarted, replaced or recompiled.

`FROZEN_SOURCE_RECEIPT.json` is the authority for which package files have an exact byte-for-byte mirror on this branch. Do not treat similarly named files as authority.

At handoff creation, these critical files are verified exact on the branch by package SHA-256, byte length and Git blob identity:

- `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5`
- `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh`
- `frozen/MQL5/Include/QROS_RISK_KERNEL_APPROVED_v15420.mqh`
- `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5`

The exact XAU/NQX/DIV3 emitter bytes and the PowerShell deployment wrapper are identified by SHA-256 in `FROZEN_SOURCE_RECEIPT.json`, but are **not yet mirrored as exact source files on this branch**. Any conclusion that requires their exact source must be reported `BLOCKED_PENDING_EXACT_SOURCE_IMPORT`; do not infer from an approximate copy. The package itself remains the byte authority.

The final activation evidence ZIP / exact START_RECEIPT bytes were not available in this chat when this handoff was created. Do not invent their hashes. Add them append-only when recovered.

## Non-negotiable rules

This is an **offline audit of a frozen copy**.

Do not:
- touch the running Darwinex-Demo terminal;
- deploy code;
- change parameters, signal logic, risk, priority or portfolio rules;
- open/reuse G30 holdouts;
- merge findings automatically into `main`;
- rewrite v2.2.3 in place.

If a defect warrants correction, create only a proposed descendant under `audit/demo-forward-v2.2.3/proposed/v2.2.4/`. Replacement of active v2.2.3 requires the full deployment gate again: compile 0/0, parent-child parity, controller parity, forward module certs, combined canary, START_RECEIPT, armed runtime `CERT=1`.

## Frozen portfolio contract

- Assets: XAUUSD and NDX only.
- Modules: XAU M1 PDH Accepted Retest; NQX multiscale profiles 17/31; NQX DIV3 R3 failed-break MA-cross LWMA M15.
- Priority: XAU_M1 > NQX_17_31 > DIV3.
- 1R = 0.50% `ACCOUNT_BALANCE`.
- Maximum initial reserved risk = 1.00% balance.
- Maximum 3 new entries per server day.
- One position per asset.
- No simultaneous new entries at the same timestamp.
- No overnight.
- BUY entry Ask; BUY exit observation Bid.
- Ambiguous SL/TP: SL first.
- Gap: first executable price.
- Zero/crossed spread fills forbidden.
- Live accounts unauthorized.

## Audit priority A — central executor and risk

Trace every event from `QROS_DEMO_BUS_v2.mqh` through `QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5` to `CTrade`.

Verify:
- demo/server/USD fail-closed account gate;
- no entry unless armed and `QDB1.EXEC.CERT==1`;
- no stale bus replay after restart;
- risk uses approved `QrosRiskSize` / `OrderCalcProfit` and never rounds volume up;
- reserved risk + new risk <= 1.00%;
- maximum 3 entries/server day survives restart;
- one position per asset;
- same-timestamp exclusion and priority ordering;
- broker rejection, `PLACED`, `DONE_PARTIAL`, partial fills and acknowledgement loss;
- no state/risk leakage after rejected or partial orders;
- SL/TP presence and modification failures;
- no path to an orphan/unprotected position.

### Critical restart question

The frozen executor enters `g_recovery_lock=true` when a QROS position already exists at `OnInit`. Determine whether the position remains safely managed after restart/reconnect and whether the lock can clear correctly. A design that blocks new entries but leaves an existing position without reliable management is a critical defect. Do not patch the active runtime; produce a descendant proposal only if needed.

## Audit priority B — bus integrity

Audit the terminal-global 32-slot ring for:
- duplicate consumption;
- stale sequence acceptance;
- torn slot / crash between publish and HEAD update;
- ring overwrite;
- persistence across restart;
- multi-event ordering;
- simultaneous module publication;
- numeric precision of sequence/event timestamps stored in terminal globals;
- close vs entry ordering.

## Audit priority C — runtime certification

Audit `QROS_V223_RUNTIME_BOOTSTRAP.mq5` for:
- exact EA identity gates;
- module READY/heartbeat requirements;
- broker UTC offset observation without silently assuming UTC;
- fresh positive-spread ticks XAUUSD/NDX;
- synchronized/current XAU M1, NDX M15, NDX H1;
- zero QROS positions before certification;
- `CERT=1` only in armed runtime after every gate passes;
- DST/server-offset transition safety.

## Audit priority D — operational fault scenarios

Design deterministic tests for at least:

1. two entry events at the same millisecond;
2. fourth entry in one broker day;
3. zero spread and crossed spread;
4. stale ring records at startup;
5. duplicate sequence / torn sequence;
6. bus overflow >32 events;
7. broker order rejection;
8. partial fill;
9. disconnect after send before acknowledgement;
10. stop modification rejection;
11. restart with active QROS position;
12. Windows/MT5 restart with persistent terminal globals;
13. server midnight;
14. US DST/server offset transition;
15. gap through stop/target;
16. two terminal instances;
17. temporary `TERMINAL_TRADE_ALLOWED=false`;
18. terminal auto-update;
19. locked or partially written CSV;
20. late module initialization / heartbeat expiry.

## Required deliverables

Create on this audit branch only:

1. `audit/demo-forward-v2.2.3/CODEX_AUDIT_REPORT.md`
   - severity Critical / High / Medium / Low / Informational;
   - exact file/function/line;
   - deterministic failure scenario;
   - consequence;
   - whether active v2.2.3 is exposed;
   - reproducibility/test;
   - proposed correction;
   - semantic class: infrastructure-only / execution-semantic / scientific-semantic.

2. `audit/demo-forward-v2.2.3/CODEX_AUDIT_TEST_MATRIX.json`
   - deterministic test;
   - expected result;
   - observed result if executable;
   - PASS / FAIL / BLOCKED.

3. `audit/demo-forward-v2.2.3/CODEX_AUDIT_DECISION.json`
   - `SAFE_TO_CONTINUE_FORWARD_AS_IS`, or
   - `CONTINUE_WITH_MONITORING_FINDINGS`, or
   - `CRITICAL_REPLACEMENT_REQUIRED`.

4. If and only if code changes are warranted: `audit/demo-forward-v2.2.3/proposed/v2.2.4/`.

## Evidence discipline

A first-pass audit of the exact central executor/bus/risk/bootstrap can proceed immediately. Any emitter-specific conclusion remains blocked until exact emitter bytes are imported and verified against `FROZEN_SOURCE_RECEIPT.json`. Never substitute a source from `main` or another runtime version.