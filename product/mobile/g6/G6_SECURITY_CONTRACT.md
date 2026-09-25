# QROS Mobile G6 — Android verified G5 snapshot client

Status: DEVELOPMENT_RUNNING / TEST_ONLY / synthetic only.

G6 integrates the already verified G5 signed-snapshot contract into Flutter without replacing M1's frozen signed-demo verifier. The Android client may only display a snapshot after strict schema checks, a pinned out-of-band Ed25519 public key, exact tenant/project/campaign identity, G4 audit receipt constraints, a consecutive witness step, audit digest binding and exact head recomputation all pass.

The network client accepts HTTPS only, system trust only, no redirects, no user-info/query/fragment, bounded JSON, `Cache-Control: no-store`, bearer token in the Authorization header and explicit project header. The G5 canonical JSON response must re-encode byte-for-byte canonically before parsing acceptance; this closes duplicate-key/parser ambiguity for the transport. Tokens stay in widget memory and are never logged or persisted.

The checked-in public key is a **synthetic test fixture trust root**. Its deterministic signing seed exists only in `product/mobile/g6/generate_fixture.py` for reproducible CI tests and must not appear anywhere under `product/mobile/flutter_app`. It has no production authority.

G6 does not claim public HTTPS, production OIDC, independent external custody, real provider license, broker data, scientific approval, holdout, GA2, MT5 parity, live trading, release signing or physical-device installation. The Android build remains a debug TEST_ONLY artifact until those independent gates pass.
