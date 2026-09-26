# QROS Mobile G7 — device, release and external-trust boundary

**Scope:** only the immutable G6 Android debug APK, synthetic client/auth evidence,
and local canaries. G7 does **not** build or sign a release APK, deploy OIDC,
provision an independent witness or inspect broker data. No unattended actions.

## 1. Pin the prior binary and source

- Scientific `main` pointer was V259, blob `5a88937d571e4bcc938c9ce71570092e0abfae6d` when G7 started. Do not mutate `main`.
- G6 verified product commit `cf3eb9f095bd82ecab58b2b2684da5e25827c8f1`;
  `MOBILE_PRODUCT_HEAD` v9 blob `37349209f57a51f4760c831868e89ea10497e854`;
  G6 verified head blob `cefbe41887d4ff686557ac11036267ef2bbef0e3`.
- Debug APK must have **exactly 141,623,410 bytes**, SHA-256
  `2c4053a27fa5692871db717c4c5bb42e1284673b49f13fa41db6a7e2b0b52c97`.
  Debug signature verifies authenticity as Android debug, not release eligibility.

## 2. Hardware installation gate (requires physical USB Android)

No physical phone is attached to the remote CI runner and no user-authorized
pairing secrets are available. A workstation with `adb` and the exact G6 APK:

```bash
adb devices -l
python product/mobile/g7/android_device_gate.py --serial REAL_USB_SERIAL --apk /path/QROS_MOBILE_G6_ANDROID_TEST_ONLY.apk
python product/mobile/g7/android_device_gate.py --serial REAL_USB_SERIAL --apk /path/QROS_MOBILE_G6_ANDROID_TEST_ONLY.apk --install
```

The device script fails closed if the serial is absent, unauthorized or reports
emulator properties. It rehashes the APK and, **only with `--install`**, invokes
`adb install -r` and checks the package was launched. The receipt hashes the serial;
it never uploads device identifiers, tokens or test-customer credentials. A physical
`adb` property result cannot prove a visually inspected screen or authenticated
pairing. Those require a separate user-observed and source-bound receipt.

**Android transport warning:** G5 is `127.0.0.1` *on the remote Linux machine*;
`127.0.0.1` on the phone refers to the phone. G6 additionally requires a trusted
TLS certificate. Without a real independently trusted HTTPS endpoint or an audited
test bridge, the phone cannot pair with G5 simply by typing `localhost`. Do not
bypass certificate verification or log a test token.

## 3. Production OIDC gate

`oidc_canary.py` implements a bounded synthetic EdDSA/JWT verifier: out-of-band
public key pin, issuer/audience, immutable tenant and project, explicit read
scope, max 300-second lifetime and single-process JTI replay tests. Test issuer,
public key and timestamps are ephemeral. A real deployment separately requires
an independently administered issuer, JWKS rotation protocol pinned externally,
production TLS, durable distributed revocation/replay control, authenticated
onboarding and security approval. No token or signing secret is stored in Flutter.

## 4. Independent witness gate

`witness_custody.py` verifies a *simulated* distinct operator's Ed25519-signed
monotonic attestation with separately supplied public pin, canonical digest,
tenant, campaign and prior hash. Tests cannot establish real operator independence.
Real acceptance requires an actual external legal/operator entity, independently
distributed trust root, trusted external HTTPS provenance, off-host append-only
or independently auditable custody, antirollback proof and a fresh real receipt.
Do not replace these with self-signed local files or assert success using boolean
fields claimed by the client. Until obtained: `BLOCKED_BY_INFRASTRUCTURE_EXTERNAL_CUSTODY`
for that production trust gate only.

## 5. Release-signing gate

`release_gate.py --apk PATH` requires a real `apksigner verify --print-certs`
on the pinned G6 APK; **a valid Android Debug certificate is rejected for release**.
The independent production signing key, certificate pin, protected signing system,
reproducible build statement, revocation policy and legal license remain external
requirements. Never embed keystore credentials in GitHub, APK or test artifacts.

## 6. Scientific isolation and next action

All G7 fixture generation is synthetic with zero market data, economic PnL,
GA2, holdout, MT5 or live orders. Build and test source-only G7 canaries, pin a
signed G6 APK authenticity receipt, leave physical device and external custody
explicitly pending rather than delaying independent work. G7 engineering pass
**does not mean G7 deployment readiness**.
