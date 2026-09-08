# v2.2.4 implementation specification

Status: DEVELOPMENT_RUNNING

Parent audit decision: `CRITICAL_REPLACEMENT_REQUIRED` at commit `abcbaaa85b6161e786347d1248119cd7cf2f5ae1`.

Frozen deployment package authority independently verified in the ChatGPT runtime:
- `QROS_DARWINEX_DEMO_DEPLOYMENT_RUNTIME_v2_2_3.zip`
- bytes: `134189`
- SHA-256: `6e732d59808b768d84ad3a1f734a08a608262192c1f78b2e7143141b461fccde`

Exact package-source hashes recovered from that ZIP:
- XAU emitter `MQL5/Experts/QROS_XAU_M1_DEMO_EMITTER_v2.mq5`: bytes 15091, SHA-256 `753fef202b1374eea17477d7609cb33a3a92516de9fa979bf691ed64ee874b35`
- NQX emitter `MQL5/Experts/QROS_NQX_17_31_DEMO_EMITTER_v2.mq5`: bytes 19731, SHA-256 `4aab8846144bbff501e241c91a4051a6c5a04b2edffb1edb53f9b9222f1081fc`
- DIV3 emitter `MQL5/Experts/QROS_DIV3_R3_DEMO_EMITTER_v2_1.mq5`: bytes 21172, SHA-256 `ff1baf7ad42ecb52a72cd2ce15d1d6089f67ba31f9a6363a229d33bebe0b4fbd`
- executor `MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5`: bytes 18799, SHA-256 `106d6890542e71dd3a1c6b90838e87664fa1a66fe576e713ceb7b52acce20d43`
- bus `MQL5/Include/QROS_DEMO_BUS_v2.mqh`: bytes 4795, SHA-256 `558eb1d91a478fc226d50d1dcf7dd69f9b5d09c750d9340bab8db5883682a63a`
- approved risk kernel `MQL5/Include/QROS_RISK_KERNEL_APPROVED_v15420.mqh`: bytes 3995, SHA-256 `8af000aac09747b896cef4e8c9263aaf675dab4fefa07b3d9d4b7c1c170ab49f`
- runtime bootstrap `MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5`: bytes 13867, SHA-256 `ec3c6f787abba5f4ccd307b3a49d05b61f5c6e194a45465cbb4c1275e948ac4e`
- activation wrapper `QROS_RESUME_FROM_V2_2_CANARY_v2_2_3.ps1`: bytes 25310, SHA-256 `281bd4038f21cae55a04a49caaf7e1ec4b71332e9bff7e2d3b54753ae140745d`
- package manifest `PACKAGE_MANIFEST_SHA256_V2_2_3.json`: bytes 11453, SHA-256 `34caadd89e73b18f6f39751dd1ed813a0a6ac3b4a466ed1cf34d36b010b3a9ed`

## Scope

Implement a complete execution-safety descendant without altering alpha, signal parameters, risk percentage, module priority, holdout, G30, BUY/SELL semantics or economic selection.

The replacement must satisfy all eleven points in `REPLACEMENT_CONTRACT.md`, with priority on F01/F03/F04 and no regression on all already-passing audit scenarios.

Required core changes:
1. Durable intent state machine `RESERVED -> SENT_UNKNOWN -> WORKING/PARTIAL -> FILLED_PROTECTED -> CLOSING -> CLOSED`, with explicit REJECTED/CANCELLED only after broker/account reconciliation.
2. Reserve risk, asset ownership, same-timestamp slot and daily-entry capacity before sending; keep them reserved through unknown/partial states.
3. Reconcile order/deal/position/volume/effective price/SL/TP after every entry request and after reconnect/restart.
4. Separate entry fault from position-management fault. New entries may fail closed while reconciled open positions continue stop/close/no-overnight management.
5. Rebuild startup inventory from orders + deals + positions. Do not discard all pre-start bus intent blindly when an unresolved QROS inventory exists.
6. Check `ResultRetcode()` plus observed final state for modify/close; retain/retry durable management intent until confirmed or escalated.
7. `HistorySelect` failure blocks entries; never authorize zero daily count by omission.
8. Implement ring commit protocol that prevents old SEQ/new payload tearing and detects rollback/failed writes; add account/epoch/instance fencing.
9. Cohort arbitration must complete the timestamp cohort before applying XAU > NQX > DIV3 priority; durable dedupe by intent identity/generation.
10. Runtime CERT must bind exact executor/emitter/SET/build/account/instance health and durable receipt; invalidate on restart/reconnect/identity or offset transition.
11. Append-only session ledger with checked persistence for request/order/deal/position/retcode/effective volume/price/barriers.

## Required proof before deployment

No descendant may replace v2.2.3 until all are PASS:
- all exact source imports verified by SHA-256;
- MetaEditor build 6182 compile `0 errors / 0 warnings`;
- parent-child parity for XAU/NQX/DIV3;
- controller canonical parity 977/977;
- deterministic audit matrix with all applicable F01-F18 safe expectations PASS and no regression of the 38 original passes;
- broker/API adversarial tests on isolated Darwinex-Demo host: rejection, placed, partial, delayed/lost ACK, modify rejection, close rejection, disconnect/reconnect;
- restart with live position and restart with working/partial order;
- two-terminal ownership/fencing test;
- DST/offset transition test;
- forward module certs XAU/NQX/DIV3;
- combined canary with orders disabled;
- START_RECEIPT materialized before armed launch;
- armed runtime `CERT=1` only after complete reconciliation gate;
- trade-by-trade MT5 parity and zero unexplained violations.

The existing `proposed/v2.2.4/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5` is partial containment only and must not be deployed as the final replacement.
