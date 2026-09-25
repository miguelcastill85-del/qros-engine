# QROS Research Studio: M2 isolated adversarial audit — 2026-09-25

Authority: product/PRODUCT_HEAD.json at branch product/qros-research-studio-mvp-v1, commit e8fcc1ef626a5cc4f6382a10e1189d5bdf7f85dd.
Scientific main remains authoritative for science. This branch is experimental and must not be merged into scientific main.

## Delta implemented

- C++20 per-campaign append-only event ledger with canonical event schema and domain-separated SHA-256 chained digests.
- Expected entire-head compare-and-swap with cooperative local directory locking.
- Re-execute existing deterministic M1 policy during every ledger replay; record denied AI/user attempts without changing state.
- Refuse stale heads, mixed campaigns, malformed hashes, damaged files, sequence gaps, missing intermediate events and mismatched independently pinned terminal heads.
- Recover committed events by reconstructing the head after process restart.
- Register as a separate CMake test and source-identity inputs.

## Evidence status

Local isolated compilation: PASS, GNU C++20 with warnings as errors.
Local isolated adversarial test: PASS, 20 checks.
Local adapters: OpenSSL SHA-256 provider and semantically reconstructed M1 transition evaluator. The complete original repository and its original SHA-256/M1 object files were not linked for this local test.
GitHub readback: the new header, source and test files have Git blob SHA-1 values matching local git hash-object; CMake readback confirms test registration.
Full-repository build/CTest: NOT RUN.
Native Windows build: NOT RUN.
Power-loss, fsync and process kill/restart fault injection: NOT RUN.
Remote CI: NOT RUN; do not activate additional cost.
Production scientific evidence attestation: NOT AVAILABLE.

## META-AUDIT: blockers before M2 promotion

1. The TransitionContext flags remain TEST_ONLY fixture inputs. They must be bound to independently verified authority receipts, not exposed as client-settable booleans.
2. The test-only C++ request carries an actor enum, including QROS_CORE. The public/mobile API must never permit clients to claim that privileged actor; provide a separate server-side signer/authority boundary.
3. SHA-256 chain integrity cannot detect tail rollback unless its latest digest is pinned in a separately controlled authority. Implement external immutable head receipts.
4. Stream flush plus filesystem rename supports process-level restart but does not prove power-loss durability; add fsync for files/directories, Windows equivalents, and crash injection.
5. Local create_directory locking is cooperative only. It is not cross-host transactional CAS, and abandoned locks/pending files need explicit fail-closed reconciliation.
6. Add symlink/path-race, concurrency/fuzzing, malformed-record and platform regression tests; keep broker data and holdouts inaccessible.
7. Build and run the entire existing M0/M1 regression suite with the actual source-hashed QROS SHA-256 implementation before any promotion.
8. Publication and user payments are outside this experiment.

## Decision

Keep original product/PRODUCT_HEAD.json unchanged and M2 pending. Only TEST_ONLY isolated engineering prototype is observed. Next automatic action: full native build and adversarial crash/restart hardening on the same isolated branch. Do not merge into scientific main.