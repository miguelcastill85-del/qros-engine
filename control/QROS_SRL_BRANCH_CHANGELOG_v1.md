# QROS SRL v1.3 — Branch Changelog

Branch: `srl-v1.3-hardening-20260914-final`

Base authority: `main@7a22404271a3051b1ff72d0e08e0f05ac351e6b3`

Implemented on isolated branch only:

- hardened SRL v1.3 governance spec;
- immutable Strategy Reconstruction Capsule semantics;
- separate monotonic Locator Registry;
- SHA-256 content identity and verified fetch TTL;
- independent failure-domain redundancy semantics;
- exact rematerialization exception contract;
- clean-room reconstruction core;
- exposure monotonicity guard;
- retention/TOCTOU delete guard;
- strict terminal-state reconstruction certificate guard;
- adversarial suite with corruption, missing bytes, rollback, path, symlink, mutation, output, rematerialization, certificate-history and terminal-transition attacks;
- branch-only GitHub Actions validation;
- explicit premerge gate ledger.

No alpha, economic PnL, holdout, GA2, MT5 deployment or `main` file was modified by SRL.
