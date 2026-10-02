# QROS Seed0076 / XAUUSD BUY M1 — V220 non-economic carriers

**Science:** `PREREGISTERED_NO_RESULTS`. Structural GA1 remains 10/60 in the `main` authority V259. First-ten-only economic scheduling is *staged* in the isolated PR #56, not promoted to `main`.

## Exact data and source pins
- XAU 2018–2019 frozen DEV: `151382388` PACKED17 rows; `2573500596` bytes; SHA-256 `3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53`.
- Unit: Bid/Ask **integer cents**, point 0.01 XAUUSD; raw data untouched.
- Exact frozen Git blobs: bars `987ef26aca2507a94247bed7663493e6682aa869`, indicator formulas `b3575c061607aaae9f4062ad623ff7083e2e0ffe`, indicator cache `21a50b167e791f4474e3c358b81e40065c048280`, structural bar oracle `b25f49273706d26ed04ad410c6ebbf89eb940af9`.
- Executed **all 17 TFs**, saving all 34 byte-exact `.npy/.npz` outputs. Their file hashes and content roots are fixed in the portable `QROS_XAU_V220_CARRIER_GROUP_MANIFEST_20260922_v1.json`.

## Portable recovery (no re-reading 151M ticks)
Five deterministic `.tar.zst` archives in personal Library `/QROS/RISE_AUDIT_MAX_V2/XAU_V220_FROZEN_CARRIERS_20260922/`:
- A: M1
- B: M2, M3
- C: M4, M5, M6
- D: M10, M12, M15, M20, M30
- E: H1, H2, H3, H4, D1, W1

**Validate before use:** compare each archive SHA-256, run `zstd -t`, restrict tar entries to the exact manifest paths, then extract to a new staging directory. SHA-256 each extracted file and compare with the manifest before promotion. Always verify the source Git blobs if code will execute. The small control bundle preserves original executable source, full receipts and adversarial checker code; **the 2.57GB DEV source is not duplicated inside these caches**, but the original eight verified Drive ZIPs remain its physical authority.

## Validation and limits
- Frozen V220 oracle: 614 checks, 0 failures. This oracle imports producer bucketing helper: **NOT fully independent**.
- Independent raw-tick check: 467 directly recomputed bars across all 17 TFs using a distinct, non-importing bucket calculation; 0 failures.
- Numeric independent `scipy.signal.lfilter`: 15 EMA/ATR full-array comparisons on M1/M5/M15; 0 failures.
- Future-only perturbation: all indicator channels tested at M1/M5/M15; historical prefixes unchanged.
- Original quote index: 74 crossed ticks / 942184 zero-spread ticks. Direct source-record-to-bar membership map stored read-only. Zero spread is **NOT automatically invalid**; direct containment is not a full causal exposure map for ATR/EMA or downstream features.
- Crucial unresolved production bindings: broker source-clock timezone/DST, exact 24 XAU BUY M1 mask blobs and alias index, frozen semantics and independent generator parity, and real quote execution provenance. **No PnL, holdout, MT5 or deployment was run.** D1/W1/session carrier outputs reproduce V220 code but broker-time validity is NOT certified.

## Next authorized delta
Attempt exact hash-targeted recovery of the **already completed** 24 XAU BUY M1 group mask blobs and global aliases. If absent, rematerialize only those missing carrier artifacts using pinned V223 worker and original frozen session-clock authority, compare exact class count `303572`, semantic SHA-256 `cf28be12f7dd94a9551fe018a4679d129d4373e6e186e17ef628f418d9b91ce4`, alias SHA-256 `4151cccd363d4d71b29d123952dc5c4dd355fb2ea27806c09cb16a5cf3c1d458`, and independent generator canaries before scoring DEV. The remaining 50 GA1 shards stay frozen. Never overwrite the existing V224 completion receipt or silently promote this experimental branch.
