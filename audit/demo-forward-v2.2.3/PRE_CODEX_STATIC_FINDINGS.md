# PRE-CODEX static findings — frozen v2.2.3 core

Status: **preliminary source-level triage, not the requested Codex decision**.

Scope is limited to the files verified byte-for-byte in `FROZEN_SOURCE_RECEIPT.json`: central executor, terminal-global bus, approved risk kernel, and runtime bootstrap. Emitter-dependent conclusions remain blocked until exact emitter source is imported.

The running Darwinex-Demo v2.2.3 must remain untouched.

## P0 — pending/partial order acknowledgement can escape the position/risk invariants

**Severity:** Critical candidate — deterministic adversarial test required.

**Source:** `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5`
- `ReservedRiskUsd()` ~line 199 counts **positions**, not pending orders.
- `SendEntry()` ~line 295 checks `AnyPositionOnAsset()` and current-position reserved risk before send.
- ~line 344 treats `TRADE_RETCODE_DONE_PARTIAL` and `TRADE_RETCODE_PLACED` as accepted success states.
- ~line 350 immediately increments `g_day_entries` and commits `LASTEV` without reconciling the resulting position/order state.

**Failure scenario:** first market request returns `PLACED` (or partial state without a fully visible final position); a second different-timestamp entry event is processed before the first request is represented as a position. `AnyPositionOnAsset()` and `ReservedRiskUsd()` can both miss the outstanding exposure/order.

**Potential consequence:** violation of one-position-per-asset and/or the 1.00% reserved-risk ceiling. A `PLACED` request that later fails/cancels also leaves in-memory daily state different from actual deals until restart.

**Required Codex test:** deterministic trade-server stub / MT5 fixture producing `PLACED`, `DONE_PARTIAL`, delayed deal, cancellation and delayed position visibility. Verify actual order+position exposure rather than only `CTrade.ResultRetcode()`.

## P1 — exit and stop-modification success is not reconciled with trade-server retcode

**Severity:** High candidate.

**Source:** executor
- `HandleModify()` ~line 358; ~line 372 logs `EXECUTED` from the boolean return of `PositionModify()`.
- `HandleClose()` ~line 376; ~line 385 logs `EXECUTED` from the boolean return of `PositionClose()`.
- `ForceNoOvernight()` ~line 389; ~line 410 does the same for forced close.

**Risk:** the code does not explicitly verify the post-request `ResultRetcode()` / resulting position state for modify/close before logging success. Codex must verify exact MQL5 `CTrade` semantics on build 6182 and reproduce server-side rejection scenarios.

**Potential consequence:** a rejected SL modification or close could be recorded as executed while the position remains unchanged/open.

## P2 — a permanent executor fault can stop management of already-open positions

**Severity:** High candidate; may become Critical depending on emitter/recovery behavior.

**Source:** executor
- `SetFault()` makes `g_fault` sticky.
- `OnTimer()` ~line 488 resets `CERT=0` and returns immediately on every subsequent timer when `g_fault` is true.
- `PollBus()`, `ProcessPending()` and `ForceNoOvernight()` are therefore skipped after a persistent fault.
- Faults include bus overflow/torn slot and several runtime risk/trade-gate failures.

**Failure scenario:** a QROS position is open; a bus-integrity or risk-state fault becomes sticky; subsequent module close/modify messages and forced day-boundary close are no longer processed.

**Potential consequence:** position falls back to broker-side SL/TP only and can miss module management or required no-overnight closure.

**Required Codex test:** inject each sticky-fault path while a protected position is open and verify an independent emergency-management path exists. None is visible in the exact central executor source.

## P3 — restart with an existing QROS position has no demonstrated state reconstruction

**Severity:** High, emitter-dependent confirmation blocked.

**Source:** executor
- `OnInit()` ~line 458 detects an existing QROS position and sets `g_recovery_lock=true` ~line 469.
- `SendEntry()` ~line 302 blocks all new entries while the lock remains set.
- No clearing/reconstruction path for `g_recovery_lock` is visible in the exact executor source.

This is fail-safe for **new entries**, but not automatically sufficient for the existing position. The central executor does not reconstruct the originating module's internal management state from the broker position.

**Potential consequence:** after MT5/Windows restart, an existing position may remain protected by its broker SL/TP but lose module-specific management/close behavior until broker exit or day boundary. Exact emitter behavior is required to close this finding.

## P4 — strict no-overnight is implemented after the server-day boundary, not before it

**Severity:** Medium/High policy mismatch.

`ForceNoOvernight()` compares the position open-date key with the **current** server-day key and closes only once they differ. Therefore a position technically survives across server midnight until the first successful post-midnight timer/close request.

Codex must classify whether the frozen contract's "no overnight" means no carry across the server calendar boundary or simply prompt forced liquidation immediately after the boundary. If strict, this is execution-semantic drift.

## P5 — bus safety assumes one producer per module; HEAD increment is not CAS-protected

**Severity:** Medium under normal deployment; High in duplicate-instance fault scenario.

**Source:** `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh`
- 32 slots per module.
- `QrosBusPublish()` reads `HEAD`, computes `seq=head+1`, writes payload, commits slot `SEQ`, then writes `HEAD`.
- There is no compare-and-swap reservation of the sequence.

With exactly one producer per module this is coherent and the reader double-checks slot commit. If two copies of the same emitter/module run against the same terminal-global namespace, both can reserve the same sequence and overwrite each other.

**Required test:** duplicate-module/second-terminal fixture against the same global namespace.

## Controls that look strong in the exact core

- Account gate explicitly requires demo trade mode, server `Darwinex-Demo`, and USD.
- Armed entries require `QDB1.EXEC.CERT==1`.
- Entry uses positive spread and BUY Ask semantics.
- Approved risk kernel sizes from `OrderCalcProfit(..., 1.0, entry, stop)`, floors volume to step, and iteratively refuses risk above target.
- Central executor checks 1.00% reserved risk from current QROS positions, daily cap 3, same-event timestamp and one-position-per-asset before entry.
- Startup sets each module's consumed sequence to current `HEAD`, preventing ordinary stale entry replay.
- Bus writes slot sequence last and reader rechecks it after payload read, providing a torn-write detector for a single producer.
- Runtime bootstrap requires exact EA identities, READY state, heartbeat, stable observed server offset, fresh positive-spread ticks, synchronized/current XAU M1 + NDX M15/H1, zero pre-existing QROS positions, correct arm state, and commits `CERT=1` only for the fully-ready armed runtime.

## Preliminary operational recommendation

Do **not** stop the current Darwinex-Demo forward solely because of this source triage. Keep v2.2.3 frozen while Codex converts P0–P5 into deterministic tests. However, P0/P1/P2 are material enough that no promotion beyond demo should occur until they are resolved or disproved.

No active code change is authorized by this document.
