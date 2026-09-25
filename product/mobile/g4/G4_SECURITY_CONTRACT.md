# QROS Mobile G4 — Data authority, license, timezone and independent witness contract

Status: **DEVELOPMENT_RUNNING / TEST_ONLY / no real market ingestion / no economic tests**. Exact starting authority: mobile product HEAD v6 Git blob `619565d1668243d3cc289c730a61340105c9417f` and independently read-backed G3 current head Git blob `55eac915ee9026ee5e84dfebbd51e9daa8dae86b`, on verified G3 promotion commit `0b529a2624fd43794cbe2185702f2bac7d3b209e`. Scientific `main` remains V259 pointer blob `5a88937d571e4bcc938c9ce71570092e0abfae6d`, holdout and GA2 sealed.

## Authenticated data source and rights

G4 provides an exact raw source SHA-256 pin and independent Ed25519 issuer-signed entitlement bound to **authenticated tenant ID from the server**, source hash, source ID, license ID, purpose, expiry, class and redistribution denial. A user-supplied body cannot authorize a different tenant or claim to be QROS_CORE. The issuer public key must be pinned from an independent trusted location; a public key supplied alongside a payload cannot establish entitlement. The test harness creates ephemeral issuer and witness keys **in memory**; it writes no private signing key to code, APK or durable receipt. Production validation of rights, key governance, revocation and contractual jurisdiction is explicitly absent.

The test source class `SYNTHETIC_ONLY` is never relabeled live. A future `LICENSED_PRIVATE` source requires actual provider-issued evidence and an operational legal approval gate not implemented here. No broker ticks are bundled in the product or redistributed. Test-only JSONL rows are synthetic and bounded, not generalized MT5 broker carrier format.

## Chronology and bid/ask

For each synthetic row, require exact broker IANA timezone (e.g. `America/New_York` only when contract pins that as simulated broker policy), ISO local millisecond timestamp, **explicit offset and DST fold 0/1**, integer bid/ask and explicit session ID + session-end marker. Compute UTC via zoneinfo and verify round-trip, rejecting nonexistent local times, contradictory DST offsets, non-monotonic/duplicate UTC events, session continuation after end, unclosed final sessions, invalid prices and missing original newline. Never silently default to UTC or guess Darwinex timezone. On real broker data, timezone/roll/DST/session requires independent source proof before any scientific use.

Zero/crossed spreads are **preserved in diagnostics** and flagged `execution_eligible=false` for this synthetic positive-spread execution gate; they are not dropped, hidden, reinterpreted as free advantage or imputed. Gaps above a spec-pinned threshold remain in the original carrier and are counted. This synthetic check lacks actual tick coverage, multi-stream Bid/Ask reconciliation, instrument roll chains, precise broker point metadata, late broker corrections and realistic market costs. It grants no real tick backtesting permission.

## Local witness: security boundary and limitation

Separate local witness process/trust-store signs a body with `witness_id, sequence, previous_sha256, tenant, campaign, subject_sha256, created_utc`. Ed25519 root is independently pinned in the *test verifier*. Append uses file lock, CAS expected head, `O_NOFOLLOW`, `fsync(log)` and `fsync(directory)`; head is recomputed by replaying and verifying every signed record. Restart after SIGKILL **after log fsync** preserves exactly one event and rejects duplicate append against stale prior head. A known external prior `(sequence,sha256)` is needed to reject deleted log tails or stale replay. Without independently administered, remotely immutable storage, operator separation, real tenant authentication and key management **this is not production external witness**. This implementation never asserts production immutability; a single operator controlling both stores can rewrite the log and pin unless out-of-band custody exists.

The multi-tenant source log is private and must never be returned verbatim to tenants. A production read-only HTTPS interface must implement tenant-scoped proof disclosures, JWT/OIDC auth and object-level authorization, independent signing-key custody, replay checkpoint storage and key rotation protocol before it is opened to mobile clients. M1 signed synthetic fixture and G1 debug APK remain intact. No new APK is built by G4.

## Anti-stall gate

Only these G4 files may be introduced compared with exact G3 verified commit; the mandatory `anti_stall_gate.py` checks actual code, independent tests, local fixture/integration, SHA-256 frozen file manifest, exact old `MOBILE_PRODUCT_HEAD.json` and `g3_verified/G3_CURRENT_HEAD.json` git blobs, no retroactive source changes, immutable scientific restrictions and nonempty next action. The GitHub workflow runs that gate before Python security tests and independent end-to-end integration, and publishes a bounded receipt. A successful CI check does not itself enforce repository branch-protection rules; do not claim it does until independently verified.

## Acceptance and next automatic action

G4 success requires GitHub Actions success, independent raw artifact download and SHA256 verification, failure-case tests, strict timezone/DST and crossed/zero quote canaries, entitlement signature and tenant isolation tests, monotonic signed external-witness *test prototype* with process-crash recovery, exact source manifest and durable readback-verified G4 HEAD. The next legitimate milestone after G4 is a consented production architecture gate for real provider rights, separately administered witness, HTTPS tenant-scoped ingress and physical Android installation. The test-only G4 cannot open true economic PnL, holdout, GA2 or real strategy research.
