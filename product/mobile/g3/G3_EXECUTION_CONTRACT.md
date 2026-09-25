# QROS Mobile G3 — Synthetic execution parity contract

**Phase:** DEVELOPMENT_RUNNING / TEST_ONLY / NO SCIENTIFIC PnL / no broker data.
Parent authority: G2 verified commit `ac5bc7536ae4a977c71f443a39882efebcfd4604` and mobile product HEAD v5 blob `dff6b0bb07b64fc8b528b0a4540dc601b8b984b3`. No rewrite of G1 or G2.

The product remains **Android/iOS mobile only**, with C++20 and Python executing as Linux infrastructure, not as a desktop UI. G3 does not change the Flutter APK. It creates a tested execution kernel that can be integrated behind a future authenticated research API only after independent trust boundary acceptance.

## Typed synthetic transport

First line `QROS_G3_SYNTHETIC_TIMELINE_V1`, second `TICKS|N`. N chronological quote events use `time_ms|bid|ask|bid_low|bid_high|ask_low|ask_high|session_id|session_end`, with **explicit synthetic** integer units; never silently infer broker timezone, point value or tick provenance. Source audit requires strictly ascending timestamp, session monotonic, final session end marker, Ask > Bid and internally consistent bid/ask ranges. Zero/crossed quotes are rejected in this *specific positive-spread synthetic demonstration*, not silently removed from actual broker audit records. Last section `PLANS|M`, each `id|side|signal_index|entry_index|stop_points|target_points`; it ends with `END`. Signal event must strictly precede the entry event within the *same* session. Arbitrary conditions/indicators and custom-code injection are out of scope.

## Execution semantics

- BUY fills at Ask, exits at Bid; SELL fills at Bid, exits at Ask; all prices are exact integers in synthetic points.
- Stop/target are frozen **after** first executable entry; no stop/target range from the entry event is used because its intratick order relative to entry is unknown.
- After entry, when range evidence could touch both stop and target, pessimistically record `SL_FIRST`. Actual quote worse than SL yields the first available worse observed quote; do not fabricate a stop fill across a gap.
- When target alone is crossed, allow a more favorable first observed quote only if the exact event quote demonstrates it.
- Close any open position at the last tick of its explicit session, without overnight; orders on session-end ticks are invalid.
- One open position per synthetic asset, maximum 3 fresh entries per session, never reenter on the same tick as exit. Simultaneous scheduled orders break ties by canonical ID and are marked SKIP, never duplicated.
- Each explicit synthetic plan produces exactly one `FILL` or `SKIP` record. Output rows sort lexicographically by ID, independent of input order. Status has no authority to promote scientific strategy states.

## Native independence, limits and claims

C++20 standalone executor and Python independent oracle compile/parse separately. Their output must match **byte by byte** on a frozen 3-record golden fixture plus 160 seeded randomized scenarios. Tests exercise opposing-side fills, conservative ambiguity, executable gaps, target, forced same-day close, invalid dates, future signals, spread anomalies, same-tick order collision and exact three-entry limits. C++17, float-based fills and permissive numeric parsing are forbidden.

This is a small G3 mechanical kernel, NOT a tick-audited production backtester; it does not implement realistic latency, commission, variable broker session time/DST, partial fills, order queues, all execution types, actual broker tick provenance, R-based economics, holdout gates, forward testing or MT5 parity. No commercial deployment until the missing gates are demonstrated. Pure Python/C++ parity is an engineering prerequisite, not proof of causal alpha.

## Anti-stall acceptance

G3 must modify exactly 12 identified new source files against G2 verified parent, each executable/documentation source hashed in the frozen manifest. CI verifies exact G2 input hashes, compiles both native engines with warnings fatal, executes 37 G1/M1 regressions plus 31 G2 tests plus G3 tests, compares raw byte ledger, captures a source-commit-bound receipt and publishes a bounded artifact. Any omission or mismatch fails the job; reports alone cannot satisfy it. No automatic branch-protection guarantee without repository rule evidence. Never claim ongoing execution between chat turns.
