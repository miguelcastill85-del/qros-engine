# QROS MT5 RUNNERLAB v3.1 — AUDITED ARCHITECTURE

Status: DESIGN_FROZEN_FOR_PROTOTYPE
Date: 2026-09-14
Parent evidence branch: fix/r2t-d04-process-ownership-v2-20260913 @ 1fdfc0152934df03e5079d4da2d1b2be8c2d97dc
Scope: infrastructure only. No Candidate3 execution. No deployment. QDB1.EXEC.CERT remains 0.

## 1. Audit conclusion
The v3 proposal is directionally correct but not production-safe as originally stated. The principal weaknesses were: assuming a compiled C# process alone solves lifecycle correctness; relying on late Job Object assignment; insufficient separation between runtime truth and ZIP packaging; insufficient secret handling in portfolio recovery; reuse risk in result files; over-reliance on AllowLiveTrading=0; portable-mode privilege risk; mutable stage state; possible MT5 executable drift; and a common-mode verifier problem.

v3.1 corrects these at the architecture level.

## 2. Technology decision
Primary orchestrator: .NET 10 LTS, C#, self-contained win-x64 release.
Reason: first-class Windows/Win32 interop, strong typing, native process/IO primitives, current LTS support, straightforward diagnostics and deployment.
PowerShell: bootstrap/diagnostic fallback only; never scientific authority.
MQL5: minimal frozen probes only.
Independent verifier: a small separately built read-only verifier for SHA-256, manifests, receipts, schema and bundle consistency. It must not share orchestration state with RunnerLab.

## 3. Process supervision hardening
Do not use Start-Process as process identity authority.
Create terminal64.exe suspended with Win32 CreateProcess(CREATE_SUSPENDED), assign it to a dedicated Job Object before ResumeThread, verify membership with IsProcessInJob, then resume.
Set JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.
Do not enable BREAKAWAY_OK or SILENT_BREAKAWAY_OK.
Track process identity by PID + creation time + final image path + job membership, not PID alone.
Every run gets one named job and one unique workspace.
On controller crash, closing the last job handle must terminate the isolated tree.
Never attach the live Darwinex terminal to the laboratory job.

## 4. Live portfolio boundary
The active Darwinex Demo installation is READ_ONLY AUTHORITY for recovery.
RunnerLab must not stop, restart, inject, attach a debugger, alter charts, profiles, Experts, Common Files or account configuration in the active installation.
The recovery scanner uses an allowlist of files and metadata and shared-read access only.
Locked/mutable files are classified as unstable unless stable-double-read succeeds; otherwise metadata/hash is not promoted.
No decompilation claim: EX5 recovery preserves bytes and metadata only. Logic is recoverable only from source or independently reconstructed behavior.

## 5. Secret/privacy boundary
Default recovery bundles MUST EXCLUDE credentials, saved passwords, private keys/certificates, accounts.dat-style auth stores, MQL5 community credentials and unrelated personal files.
Logs are redacted for account/login identifiers before an exportable support bundle is created.
If raw sensitive evidence is required, it is stored only in a local PRIVATE bundle and is never included in a default upload bundle.
A secret-scan gate runs before packaging.

## 6. MT5 clone policy
All clones live outside Program Files under a dedicated writable root such as C:\QROS\RunnerLab\runs\<run_id>.
Do not require disabling UAC.
Do not copy saved broker credentials into R0-R2 clones.
Use /portable only on those dedicated clones.
Use /config with generated read-only custom configuration.
R0-R2 probes: AllowLiveTrading=0, AllowDllImport=0, no Candidate3, no trade API, account credentials absent.
R4 may connect only after explicit demo-account attestation and separate authorization.

## 7. Trading safety interlocks
AllowLiveTrading=0 is defense-in-depth, not the only safety gate.
R0-R2: no broker credentials + no Candidate3 + no MQL trade functions + AllowLiveTrading=0.
R4 diagnostic: terminal must attest ACCOUNT_TRADE_MODE_DEMO before any candidate test that could reach trading code. ACCOUNT_TRADE_MODE_REAL is a hard abort.
Deployment/arming is moved out of RunnerLab. RunnerLab can never set QDB1.EXEC.CERT=1.
A separate deployment tool must consume an approved immutable PASS receipt and require explicit user authorization.

## 8. Transaction/state model
Each stage identity is immutable: run_id, stage_id, attempt_id, nonce, input_hashes, executable_hashes.
Allowed transition: NOT_STARTED -> RUNNING -> PASS|FAIL|ABORTED.
No in-place overwrite of a terminal result.
Every transition appends an event to the durable journal.
Stage reruns create a new attempt_id.
Timeouts use a monotonic clock; UTC is provenance only.

## 9. Durable control store
Control state is local SQLite on the same host.
Use WAL + synchronous=FULL for durable commits.
Do not place the control DB on Dropbox/network shares.
Receipts and manifests are content-addressed by SHA-256.
Critical standalone files use FileStream.Flush(true) before publication.
ZIP evidence is a DERIVED ARTIFACT, not the scientific authority.
If ZIP creation fails after a PASS, runtime PASS remains preserved; packaging can be deterministically rebuilt from the committed content-addressed evidence set.

## 10. Stale-artifact elimination
Never reuse RESULT.csv across phases.
Every phase receives a unique one-shot output path containing run_id/stage_id/attempt_id/nonce.
Writers create new files only; an existing path is a hard collision.
Readers require exact echoed run_id/stage_id/attempt_id/nonce/test_id before accepting evidence.
Unexpected older rows are ignored and cannot cause early failure or PASS.
This permanently addresses D14-class stale-result defects.

## 11. Filesystem/path safety
All writable paths must canonicalize inside the per-run root.
Reject .. traversal, alternate roots and reparse-point escapes.
Do not follow symlink/junction/reparse targets outside the workspace.
Cleanup is allowlist-based from the run manifest; never recursive-delete an unverified arbitrary path.

## 12. MT5/version drift
Freeze and record terminal64.exe SHA-256, MetaEditor SHA-256 and reported MT5 build before the run.
Re-check at stage boundaries and at run completion.
Any executable/build drift invalidates the affected qualification run and requires a new environment fingerprint.
Do not silently auto-promote results across builds.

## 13. Evidence architecture
Scientific result commit order:
1) stage observation captured;
2) stage receipt validated;
3) SQLite transaction committed;
4) immutable evidence objects hashed/published;
5) independent verifier checks receipt/manifests;
6) optional ZIP bundle generated last.
A packaging failure cannot rewrite a stage PASS as a runtime FAIL.

## 14. Independent verification
RunnerLab must not be its only verifier.
A second read-only verifier checks SHA-256, JSON schema, event-chain continuity, stage prerequisites, no contradictory states and bundle reconstruction.
It has no capability to launch/kill MT5 or modify certification state.
Critical R2/R4 promotion requires agreement between orchestrator receipt and independent verifier.

## 15. Recovery and idempotency
Named global mutex prevents two RunnerLab controllers from managing the same MT5 lab root concurrently.
Startup reconciliation scans RUNNING attempts. If their Job Object/process tree is gone, mark attempt CRASHED/ABORTED, never PASS.
Safe stages may be retried under a new attempt_id from the last committed checkpoint.
Immutable PASS evidence is never recomputed unless exact deterministic rematerialization is required.

## 16. UI policy
CLI/state engine is authority. GUI/dashboard is a read-only projection.
The UI may never generate scientific state by itself.
Every displayed PASS must link to the underlying receipt and hashes.

## 17. Regression suite derived from observed failures
Mandatory prequalification regressions include:
- launcher closes immediately;
- PowerShell generic-list incompatibility;
- process lifetime proxy/child PID drift (D04);
- stale result early return (D14);
- evidence ZIP namespace/packaging failure (D15);
- stale lock;
- second executor fence;
- release/reacquire;
- process orphan after controller crash;
- wrong/changed executable hash;
- manifest corruption;
- schema corruption;
- timeout;
- denied filesystem permission;
- path traversal/reparse escape;
- partial evidence write;
- corrupted ZIP after valid runtime PASS;
- account mode REAL injected into an R4-like test.

## 18. Promotion gates
RunnerLab itself must pass SELF0 unit/static, SELF1 property/mutation, SELF2 crash/restart, SELF3 Windows process isolation, SELF4 MT5 clone safety, SELF5 evidence durability/rebuild, SELF6 independent-verifier parity.
Only then may it run formal QROS R0-R4 qualification.

## 19. Benchmark verdict
Current PowerShell chain: suitable as diagnostic evidence generator, not suitable as long-term control plane.
Original RunnerLab v3: correct direction but still had race, durability, packaging, secret and authority vulnerabilities.
RunnerLab v3.1: accepted as the prototype architecture, subject to real Windows/MT5 benchmark before promotion.

## 20. Non-negotiable invariants
- Live Darwinex terminal is never modified during recovery/qualification.
- Candidate3 remains frozen unless R0-R3 pass and R4 is explicitly authorized.
- QDB1.EXEC.CERT remains 0; RunnerLab cannot arm it.
- No real account trading.
- No silent use of stale artifacts.
- No result promotion from ZIP existence alone.
- No PASS without immutable receipt + independent verification.
