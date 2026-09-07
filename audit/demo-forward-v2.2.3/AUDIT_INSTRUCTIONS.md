# QROS Darwinex Demo Forward v2.2.3 — Codex audit handoff

## Authority and freeze

- Repository: `miguelcastill85-del/qros-engine`
- Audit branch: `audit/demo-forward-v2.2.3-frozen-20260907`
- Branch base commit: `543cc1c688c5c245f8ffb19ea48daf5d449297d9`
- Frozen runtime package: `QROS_DARWINEX_DEMO_DEPLOYMENT_RUNTIME_v2_2_3.zip`
- Frozen runtime package SHA-256: `6e732d59808b768d84ad3a1f734a08a608262192c1f78b2e7143141b461fccde`
- MT5 build certified in deployment: `6182`
- Scientific state: `FROZEN_NO_RETUNE`
- Operational state at handoff: demo forward observed ACTIVE in Darwinex-Demo; active terminal must not be modified by this audit.

The exact frozen bytes of the package are preserved in `QROS_DEMO_FORWARD_V223_FROZEN_ONEFILE.json` as per-file base64 plus SHA-256. Reconstruct files only from that ONEFILE if needed. Do not substitute current `main` files, similarly named files, or newer descendants.

## Non-negotiable audit boundary

This is an **offline audit of a frozen copy**. Do not change, restart, replace, recompile, or deploy the currently running Darwinex-Demo terminal. Do not modify scientific parameters, signal logic, risk, priority, or portfolio rules. Do not open or reuse any G30 holdout. Do not merge findings into `main` automatically.

If a material defect is found, create a proposed descendant only, e.g. `v2.2.4`, and require the full deployment gate again before any replacement of v2.2.3: compile 0/0, parent-child parity, controller parity, forward module certs, combined canary, START_RECEIPT, armed runtime CERT=1.

## Frozen portfolio contract

- Assets: `XAUUSD` and `NDX` only.
- Modules:
  1. `XAU_M1_BUY_PDH_ACCEPTED_RETEST_v101`
  2. `NQX_M15_BUY_MULTISCALE_PULLBACK_CONSOLIDATED_v15100` profiles 17/31
  3. `NQX_DIV3_R3_FAILED_BREAK_MA_CROSS_LWMA_M15`
- Portfolio priority: XAU_M1 > NQX_17_31 > DIV3.
- 1R = 0.50% `ACCOUNT_BALANCE`.
- Maximum initial reserved risk = 1.00% balance.
- Maximum 3 new entries per server day.
- One position per asset.
- No simultaneous new entries at the same timestamp.
- No overnight.
- BUY entry Ask; BUY exit observation Bid.
- Ambiguous SL/TP: SL first.
- Gap fill: first executable price.
- Zero/crossed spread fills forbidden.
- Live account is not authorized.

## Audit objectives

Audit the frozen code for operational correctness and failure recovery, not strategy performance. Prioritize defects that could create unauthorized risk, duplicate trades, unmanaged positions, missed exits, state corruption, or divergence from the frozen research logic.

### A. Account and deployment fail-closed controls

Verify the executor cannot trade unless all of the following are true:
- `ACCOUNT_TRADE_MODE_DEMO`.
- Server exactly `Darwinex-Demo`.
- Currency `USD`.
- Runtime identities XAU/NQX/DIV3 are exact.
- All modules are `READY` with fresh heartbeats.
- Runtime `QDB1.EXEC.CERT==1`.
- Positive executable spread.
- No stale bus event can become a new order after restart.

Prove that no code path can accidentally trade live, arm before START_RECEIPT, or bypass the cert latch.

### B. Order lifecycle and risk

Trace every order path from event bus to `CTrade` and verify:
- `QrosRiskSize` is used exactly with frozen risk kernel.
- Risk uses `OrderCalcProfit` at 1 lot and volume is rounded down.
- Stop is never widened to obtain a minimum volume.
- Existing reserved risk + new risk never exceeds 1.00%.
- Daily cap 3 is reconstructed correctly across restart and broker-day boundary.
- One position per asset is enforced under simultaneous/reentrant events.
- Same-timestamp lock cannot race.
- Failed/rejected/partial fills do not leave reserved-risk or state leakage.
- Magic numbers cannot collide with unrelated positions.

### C. Position management and exits

Verify exact handling of:
- SL/TP placement at entry.
- Stop modification failures.
- Break-even / module-specific management.
- Partial fills.
- Position close failures.
- Market closure and illiquid spread.
- Gap through stop/target.
- SL-first semantics when both are ambiguous.
- End-of-day/no-overnight closure.

Find any path where a position can remain open without a controller, SL, or exit route.

### D. Restart, reconnect, and crash recovery

Audit scenarios:
- MT5 restart with no positions.
- MT5 restart with a QROS position already open.
- Windows restart.
- Internet loss/recovery.
- Broker reconnect/session reset.
- Terminal auto-update.
- Global variables persist but CSV/log files are missing or stale.
- CSV file is locked or partially written.
- Two QROS terminals accidentally start simultaneously.
- Runtime profile restores old charts/EAs.

The current v2 executor deliberately fails closed if a QROS position exists at init. Determine whether this is operationally safe for a real forward: a fail-closed EA that refuses to initialize while a position remains open may also leave that position unmanaged. Treat this as a critical audit item and propose a separate recovery design if needed; do not patch the active runtime.

### E. Bus/event integrity

Audit `QROS_DEMO_BUS_v2.mqh` and all producer/consumer usage for:
- sequence wraparound;
- terminal-global persistence;
- ring overwrite;
- duplicate consumption;
- stale event acceptance;
- ordering across modules;
- timestamp timezone assumptions;
- crash between publish and consume;
- memory visibility/reentrancy;
- close event vs new entry event ordering.

### F. Time, sessions, DST, and no-overnight

Do not assume UTC. Verify every place where server time, GMT, local time, daily reset, end-of-day, or date reconstruction is used. Check US DST transition behavior and whether the runtime can continue across a Darwinex server offset change without resetting the forward or miscounting daily entries.

### G. Parity preservation

Static-review the child emitters against frozen parents. Any proposed correction must be classified as:
- infrastructure-only;
- execution-semantic;
- scientific-semantic.

Execution/scientific changes require new lineage and full parity/revalidation. Do not label a semantic change as infrastructure-only.

### H. Adversarial tests to design

Create deterministic tests/fixtures for at least:
- two modules publish at exactly same millisecond;
- 4th entry in same server day;
- zero spread then fresh spread;
- crossed spread;
- stale bus record at startup;
- duplicate bus sequence;
- order rejection;
- partial fill;
- disconnect between order and acknowledgement;
- stop modification rejection;
- restart with active QROS position;
- DST transition;
- server midnight;
- tick gap through SL and TP;
- terminal-global variables from prior run;
- two terminal instances;
- malformed/locked CSV;
- missing history at init;
- late DIV3 initialization.

## Required Codex deliverables

1. `CODEX_AUDIT_REPORT.md`
   - severity: Critical / High / Medium / Low / Informational;
   - exact file/function/line;
   - failure scenario;
   - consequence;
   - whether active v2.2.3 is exposed;
   - reproducibility/test case;
   - proposed correction;
   - semantic classification.

2. `CODEX_AUDIT_TEST_MATRIX.json`
   - deterministic tests;
   - expected result;
   - observed result if executable in Codex environment;
   - status PASS/FAIL/BLOCKED.

3. `CODEX_AUDIT_DECISION.json`
   - `SAFE_TO_CONTINUE_FORWARD_AS_IS`, or
   - `CONTINUE_WITH_MONITORING_FINDINGS`, or
   - `CRITICAL_REPLACEMENT_REQUIRED`.

4. If and only if code changes are warranted, place them under `proposed/v2.2.4/` and never overwrite the frozen files.

## Important evidence boundary

The running activation was observed on-screen as `DEMO_FORWARD_ACTIVE`, `cert=1`, MT5 build 6182. The final runtime evidence ZIP and exact START_RECEIPT bytes were not available in this chat at the moment this handoff file was created. Therefore do not invent their hashes. When they become available, add them as an append-only authority receipt and bind them to this branch.
