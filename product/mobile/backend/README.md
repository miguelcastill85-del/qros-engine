# QROS Mobile M1: signed read-only synthetic gateway

This is a *test-only* protocol slice for **Android-first mobile**. It is NOT a real research API and has no authority to issue scientific transitions. The only data is a signed synthetic `DEMO-001`. No private signing key is present in the repository or on the Android app.

### Security boundary

- Separate ephemeral offline Ed25519 witness and receipt signers generated a frozen signed fixture. Public keys are pinned in the mobile client. Both signer private keys were discarded, not stored.
- An independently supplied trust-root SHA-256 is mandatory. The backend rejects a different trust file or signed snapshot. The Android client additionally pins the witness public key, receipt public key, source ID and anchor body hash. This demonstrates static anti-rollback for **one** frozen fixture, *not* a live external witness service.
- The demo HTTP server binds only `127.0.0.1` and requires a bearer token with at least 32 characters. All verbs except GET are explicitly denied; no CORS, no cookies, no real market data and no scientific state mutation.
- The Android mobile client insists on real HTTPS with normal system certificate validation and no redirect following. There is **no** public HTTPS ingress or customer pairing yet; a local-loopback HTTP server cannot be reached directly by a physical handset. A separately audited HTTPS gateway is required for end-to-end live testing.
- The fixture's data classes `TEST_ONLY_SYNTHETIC`, `SIMULATED_SAMPLE` and `scientific_authority=NONE` are enforced in both Python and Dart. Signed data authenticates this fake demo's origin, NOT profitability or scientific PASS.

### Bounded local verification

Requires Python 3.12+ and pinned `cryptography==46.0.4` in `requirements.txt`. Python `unittest` requires no further packages.

```bash
python -m pip install -r product/mobile/backend/requirements.txt
cd product/mobile/backend
python -m unittest discover -s tests -v
```

To run the local-only server, supply a random **test-only** token via an environment variable and the independently pinned exact trust SHA (for this frozen sample see `demo/PUBLIC_PIN.txt`):

```bash
export QROS_TEST_ONLY_BEARER_TOKEN="<generate-your-own-random-token-of-at-least-32-chars>"
export QROS_OUT_OF_BAND_TRUST_ROOT_SHA256="$(cat demo/PUBLIC_PIN.txt)"
python server.py --trust-root demo/trust_root.json --signed-snapshot demo/signed_snapshot.json --port 8765
```

The `PUBLIC_PIN.txt` in this repository is a demonstrative reference, not independent production custody. Production must mount the pin and signed HEAD under a separately governed trusted store, with deployment verification that the mutable API cannot replace it. Do not expose the loopback HTTP server to the public Internet.

### Gates still open

Production issuer key custody / rotation, independent **dynamic** witness with monotonic HEAD freshness, real per-user authorization, rate limiting, encrypted secret storage, privacy review, certificate-pinned HTTPS gateway, emulator/physical-phone network integration, crash recovery with backend persistence, customer accounts and billing. The scientific `main` HEAD remains untouched.
