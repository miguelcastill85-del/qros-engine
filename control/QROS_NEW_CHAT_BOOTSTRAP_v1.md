# QROS / RISE — New Chat Bootstrap v1

This file is a mandatory continuity entrypoint for new chats, runtimes, Work/Codex sessions, and project migrations.

## Recovery order

1. Read `control/HEAD.json` from the default branch of `miguelcastill85-del/qros-engine`.
2. Follow `historical_reconciliation_ref` when present.
3. Follow `checkpoint_ref` exactly.
4. Read `control/QROS_DURABLE_SCIENTIFIC_ARTIFACT_POLICY_v1.json`.
5. Verify all referenced hashes/identities before executing scientific work.
6. Treat GitHub durable authority as superior to conversational memory, runtime `/mnt/data`, summaries, or filename guessing.

## Current campaign authority

Current HEAD at this revision: `QROS_PERSISTENT_CONTROL_HEAD_V197`.
Campaign: `QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1`.
Scope: F03–F12 only. F13 is excluded and must not be searched, recovered, or executed.
Stage B is globally closed and must not be rerun scientifically.
Frozen population: 9,237 total = 6,570 NQX + 2,667 XAUUSD = 6,183 BUY + 3,054 SELL.
Rule: all passers advance; no medoids, reranking, or retuning.

## Historical Stage C distinction

V192 was legitimately validated and promoted for Stage C 2022–2024. The validator status was PASS and the promotion receipt status was `PROMOTED_NO_RESULTS`. V192 authorized market-data read and execution for exactly 9,237 frozen configurations under the frozen Gate C, but no Stage C economic results existed at promotion and no 2022+ strategy PnL was read during validation/promotion.

Frozen V192 Gate C: at least 30 trades; PF central >=1.20, conservative >=1.10, severe >=1.00; net R positive under all three cost regimes; central result positive separately in 2022, 2023 and 2024; independent trade parity required.

Do not infer that Stage C was executed merely because V192 was promoted. Read `control/QROS_G30_V192_V196_HISTORICAL_RECONCILIATION_V197_20260911_v1.json` for the authoritative distinction.

## Critical recovery state

NQX canonical data authority was physically restored 28/28 in the 2026-09-11 recovery runtime and has carrier SHA-256 `6da9cf67310c2c6689bd82c20882e5e8b652196147a458be58796e5103a22608`.
XAU authority is 35/35 with carrier SHA-256 `c386dc3028943f7462f6091d1417a9733237be5e25b07aa5732c111ce11f92e4`, but its physical bytes were not mounted in that recovery runtime.
Exact runner identity: `qros_g30_econ_numba_v4.py`, SHA-256 `ef671e449eb7e2fbed42704c7bd9dec01de0768310f6eb48fb2265409767abe4`.
Exact runner source bytes and exact Stage-B frozen final-row payloads were not recoverable from the durable stores inspected on 2026-09-11.
Therefore neither Stage C nor the later all-years economic run was executed by that recovery attempt, and no new holdout exposure was created by it.

## Hard prohibition

Do not reconstruct the frozen population by rerunning Stage B. Do not approximate the missing runner and call it parity. Do not invent Stage C metrics. Do not touch F13. Only resume execution after exact pre-existing bytes are recovered from durable storage and hash-verified.

## Durable closure rule

No future QROS/RISE scientific stage may be considered durably closed unless runner source, independent parity implementation, full frozen configuration rows, environment lock, data contract, receipts/roots, hashes, exposure state, and checkpoint are physically persisted and recoverable from durable storage.
