# QROS Mobile G5 — test-only HTTPS read-only tenant gateway

Authority: G4 frozen product v7 Git blob `bebeca3f38d3116066516609205795eb3ed91c23`, G4 current verified head blob `bea1c0366bcde2b43f99188f52c2390351f7557d`, exact G4 promotion commit `58b00efa53ff58b36216764c2c813f4a022a09a4`. G1 Android APK remains the last built mobile binary; no new APK or real Android device can be claimed by this backend-only ticket.

## Scope / trust model

Implement HTTPS loopback-only (`127.0.0.1`) **synthetic** gateway for isolated tenant/project read-only demo snapshots. Proofs originate from the G4 Ed25519 signed synthetic entitlement → strict timezone/rights/BidAsk data audit → separate signed local witness chain, not from user text. The network gateway receives **only public witness keys and prevalidated immutable synthetic snapshots**, no witness signing key or raw broker carrier. Each tenant has its own synthetic trust root and separate signed witness chain to avoid cross-tenant chain disclosure. The network client independently pins each witness root from test harness/out-of-band trusted configuration and verifies entire snapshot, audit SHA256 and last-seen witness head; the HTTPS certificate chain is validated with a test CA and system SSL hostname verification. No `badCertificateCallback`, insecure HTTP fallback, redirection, credentials in URLs or CORS preflight.

Ephemeral bearer tokens with >=256 bits randomness exist only in process RAM in this synthetic prototype. They are bound to a single tenant/project, allowed scoped read-only action and explicit expiration. Future production service **must use authorized identity provider/JWT/OIDC validation, persistent backend authz, tenant-level audit, revocation, rate limits and proper key-management**; this demo registry is not production IAM. No source code writes tokens, TLS test credentials or test witness private keys into shipped packages. Temporary test TLS private keys exist only inside auto-deleted test workspaces on CI.

The client is Python as an independent acceptance oracle for what the existing Flutter Android signed-demo client must eventually prove; the G5 code does **not** silently modify G1 APK or claim Flutter backend pairing. Device acceptance and HTTPS public ingress require supported environment and actual device evidence. The historical M1 mobile UI still has pinned static signed fixture; G5 dynamic local demo is a service seam, not a production replacement.

## Fail-closed boundaries

Only `GET /v1/demo-snapshot` or `GET /v1/status` with one correct bearer + matching project and scope are admitted over verified TLS. All writes (`POST/PUT/PATCH/DELETE/HEAD`) and CORS `OPTIONS` are denied; query-string actor tricks, unknown paths and public binds are denied. Every response disables caching, advertises no CORS or dynamic scripts and avoids leaking tokens. A signed receipt cannot grant scientific approvals: `scientific_approval=false`, `economic_backtests=0`, `holdout_open=false`, `ga2_open=false` are exact contract requirements at construction, server response and independent client verification. Cross-tenant read, wrong project, forged witness key, stale sequence, same-sequence fork, audit payload tampering and untrusted certificate must all fail closed. Stable same-anchor readback is idempotent; freshness beyond the last independently known head needs actual external custody and a separately maintained pin.

## Mandatory G5 verification

- 22+ (or actual CI measured count) G5 Python local HTTPS tests with real TLS socket, true per-tenant tokens and source/G4 dynamic crypto proofs; all pass in CPython 3.12 GitHub Actions.
- Exact G4 source HEAD/receipt/manifest pins and no changes to G1–G4 or scientific main. G5 source manifest binds every new source file; `anti_stall_gate.py` checks actual Git tree diff from G4 v7. A PR-level CI is **not** repository branch protection.
- Generate and independently download a CI artifact containing end-to-end G5 integration receipt and source-commit-bound test receipt. Public HTTPS, independently administered external witness, physical Android, real license checks, broker ticks and trading remain NOT_DEPLOYED / NOT_RUN / NOT_AUTHORIZED.

## Next action after test-only G5

Implement actual external witness under separately governed credentials/custody, proper HTTPS tenant authz and physical Android app pairing only when these facilities can be independently verified. Where real device or independent custody cannot be accessed, persist a narrowly scoped infrastructure dependency without revoking G1–G5 engineering PASS; proceed with independent UI/contract tests rather than falsely claiming production readiness or reopening holdout/GA2.
