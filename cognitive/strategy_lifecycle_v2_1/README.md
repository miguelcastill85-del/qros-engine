# QROS Strategy Lifecycle Engine v2.1 — Durable Reference Kernel

Status: `REFERENCE_KERNEL_VALIDATED_NOT_SCIENTIFIC_AUTHORITY`

This package extends QSLE v2.0 with a physical SQLite durability layer and a read-only bridge to the existing QROS control triplet. It does **not** promote QSLE, alter scientific results, open holdout, touch F13, or replace current QROS authority.

## Durable storage

`durable_store.py` implements:
- SQLite WAL + `synchronous=FULL`;
- append-only scientific and authority journals;
- optimistic campaign versions;
- idempotency keys with intent hashes;
- leases + fencing tokens for stale-worker rejection;
- atomic event/projection/exposure commit;
- monotonic exposure table;
- role-separated scientific / engineering-reference / runtime authority pointers;
- event, payload, evidence, exposure and state-byte integrity checks;
- schema/trigger drift detection;
- projection replay from journal state bytes;
- fsync + atomic checkpoint replacement and SHA-256 receipt.

## Existing control integration

`control_bridge.py` is strictly read-only. It never selects authority by recency. On the observed repository snapshot of 2026-09-12:
- `control/HEAD.json` -> authority epoch 199, blob `dc7f7f68f127b279ffff36f0ec8f80d23d2e41c1`;
- `control/persistent_execution/STATE.json` -> epoch 191, blob `48a212b105a5cf21425c79a2bb7fb349d3c061a9`;
- `control/persistent_execution/RUN_QUEUE.json` -> epoch 191, blob `1fa745bb9a57d3944de2c2521bd67b0f0520a029`;
- `control/CONTROL_AUTHORITY_MANIFEST_v3.json` -> epoch 191, blob `5afce6279994b8625bd79fb2d5d13924e3c561e7`.

The bridge therefore returns `BLOCKED_SPLIT_AUTHORITY` and `scientific_dispatch_authorized=false`, while allowing V191 to remain an engineering reference. No V199 promotion is inferred.

`MASTER_INVENTORY` and lifecycle `RUN_QUEUE` are modeled as deterministic **projections** and never become scientific authority by themselves.

## Validation observed in this runtime

- Pytest: 45/45 PASS.
- RISE-Q persistence black-box: 15/15 PASS.
- Deterministic stress: 80 campaigns, 640 committed transitions, 188 injected pre-commit crashes recovered, 108 injected post-commit crashes recovered exactly once, 16 stale-worker rejections, 160 exposures, event/projection integrity PASS, durable checkpoint PASS.
- `python -m compileall -q .`: PASS.

These results mean zero known failures in the executed suites, not proof that no undiscovered bug can exist.

## Durable carrier

The exact ZIP is persisted as six Base64 parts under `package/`. Run `RECONSTRUCT_AND_VERIFY.py` to reconstruct the ZIP. Each part has a pinned byte count and SHA-256 and the decoded archive must equal:

`accc29e249145ce98b918efde91fec96c3a1be4c1ea8f4ebad9488afd398d087`

Use `python RECONSTRUCT_AND_VERIFY.py --audit` to reconstruct and rerun pytest, the isolated RISE-Q persistence audit and compileall.

## Promotion gates still open

QSLE remains non-authoritative until at least:
1. independent execution on a separate durable filesystem/runtime;
2. real process kill / abrupt power-loss style test outside the in-process fault hooks;
3. schema migration test across a released older database;
4. external checkpoint SHA storage/readback from project-controlled durable storage;
5. explicit reconciliation of the existing QROS scientific/control authority split;
6. shadow integration with existing controller without scientific writes;
7. RISE fixed-point on the integrated stack;
8. explicit promotion receipt.

No scientific campaign should be migrated into QSLE before those gates pass.
