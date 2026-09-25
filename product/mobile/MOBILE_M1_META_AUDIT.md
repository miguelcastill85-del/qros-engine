# M1 independent adversarial review — static proof-of-concept, NOT external service certification

## Falsification attempts / gates

| Attack | Defensive proof | Residual limitation |
|---|---|---|
| Forge receipt or relabel mock results as scientific PASS | Server Ed25519 signature verification; Dart independent Ed25519 verification; explicit false gate flags | Signature keys from one-time offline fixture have no production custody policy |
| Replay old but signed HEAD | Independently pinned exact SHA-256 of frozen witness body; tests reject alternate root | Only **static demo** anchor. Dynamic latest monotonicity still not implemented |
| Compromise one signing key | Distinct witness and receipt public keys; swap-signature test must reject | Trust-root publisher itself must be secured and audited |
| Spoof QROS_CORE via mobile | Read-only backend implements GET only; `POST/PUT/PATCH/DELETE/OPTIONS` reject actor headers | No production state transitions exist yet |
| Intercept phone token | HTTPS-only Dart client with system CA checks and no redirects; token never logged/stored by app | No externally reachable TLS gateway deployed; do not use loopback HTTP from phone |
| Replace trust root on server | `QROS_OUT_OF_BAND_TRUST_ROOT_SHA256` required before startup | Developer testing PIN is in same repo; production requires independently mounted trusted origin |
| Tenant IDOR | API exposes exactly one fixed synthetic `DEMO-001`, no query params or customer data | Tenant authz not implemented; forbids real-user onboarding |
| Malformed JSON / >64KB / path traversal | Strict keys and payload length, reject duplicated keys, paths fixed | Independent fuzzing and CDN ingress hardening outstanding |
| Hide failed tests or promote science after CI PASS | Keep receipts as `PASS_ENGINEERING_TEST_ONLY`, preserve original scientific pointers | Android M1 debug builds cannot be described as signed production releases |

## Ordering

1. Run Python auth/crypto tests and Flutter crypto/UI tests independently.
2. Build Android debug only after both pass; hash the actual APK.
3. Freeze tested commit + artifact hash in isolated `product/mobile/MOBILE_PRODUCT_HEAD.json` descendant, not scientific `main`.
4. Perform end-to-end TLS emulator/physical Android test against an independently deployed read-only gateway only after server/credential custody and account boundaries are accepted.

## Invariants

Only an Android/iPhone mobile product is in scope. Linux backend and GitHub CI are infrastructure. Costs must remain zero additional. The demo does not include broker data, strategy alpha, economic PnL or MT5 execution.
