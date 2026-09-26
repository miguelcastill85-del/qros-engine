# QROS Mobile G8 — independent Android-emulator runtime gate

**Development-only, synthetic-only.** Parent: verified G7 product v10 commit
`3210501dba05b9514efde586a4b2aa63378e6a95`. Science `main` stable
pointer blob `5a88937d571e4bcc938c9ce71570092e0abfae6d` is not modified.

## New, independently observed capability

Install the **existing, exact G6 Android debug APK** in an Android 35 x86_64
emulator on a GitHub Actions Linux runner. The APK must match 141623410 bytes and
SHA-256 `2c4053a27fa5692871db717c4c5bb42e1284673b49f13fa41db6a7e2b0b52c97`.
GitHub Actions downloads only the previously successful G6 APK from run
`36197217037`; G8 neither rebuilds nor replaces it. The independent
Android-emulator action is SHA-pinned to
`ReactiveCircus/android-emulator-runner@a421e43855164a8197daf9d8d40fe71c6996bb0d`.

The exact source gate compares G7 v10 Git blob identities, the frozen G7
science blob referenced at development start, all G8 new-source SHA256 values,
and the exact eight-file diff against G7. It fails for source changes without a
new manifest, no-op reviews, or a modified scientific HEAD. G1–G7 do not rerun.

A passing emulator runtime receipt requires evidence of ALL of:

* adb uniquely authorized `emulator-5554`, `ro.kernel.qemu=1`, explicit SDK;
* original APK byte/hash audit, actual adb installation and Android package
  path, real main-activity launch, PID and top-resumed activity evidence;
* real Android framebuffer screenshot with valid PNG IHDR and bounded
  dimensions; raw screenshot and SHA256 preserved;
* UIAutomator accessibility hierarchy collected as raw XML and independently
  parsed. QROS text is reported only if actually observed, not fabricated;
* no package-attributable fatal crash in the captured bounded logcat window;
* durable JSON receipt with file hashes, synthetic-only and unresolved gate
  labels, and receipt write/readback.

## Strict distinction

Android emulator execution is NOT physical phone installation, real device
pairing, release-signature verification (G7 verified *debug* signature only),
real TLS/OIDC, independent witness custody, authorized live trading or causal
alpha. The emulator is never accepted by G7's physical USB-device gate.
There is no broker data, holdout, GA2, MT5 or economic testing here. G8 may pass
engineering independently while all G7 external production trust gates remain
unverified.

If the emulator infrastructure fails (missing KVM, unavailable Android image,
UIAutomator unavailable), preserve the CI failure log and exact error, then
repair the minimal source or revise the explicit gate on a descendant commit.
Do NOT silently weaken the app-launch/runtime requirement or claim the phone
is installed. No paid service activation.
