# QROS Mobile G2 — Anti-stall executable control v1

**Scope:** Mobile-only product, synthetic structural enumeration. This is a
CI-controlled engineering acceptance gate, **not** a service that can compel
an assistant to continue after its chat turn ends. It is not an external
immutable authority, branch protection, production signing, a scientific
PASS, or a claim of future market performance.

## Fail-closed delivery contract

The G2 pull-request workflow refuses to report PASS unless all these checks
complete on the **same exact source commit**:

1. Read the exact G1 parent `6a878ed10e26c616d6f326563ff3fa24bfdc7f3b`
   and immutable mobile product HEAD v4 Git blob
   `1a684a92fe65d1d53aeaabe5ddaf803c6710beef`.
2. Require the exact set of 11 G2 files to be new in the branch compared
   with the frozen G1 commit. A no-op, missing test or modifications to a
   pre-existing baseline file **fail**. Pin SHA-256 of the executable code,
   tests, this note and the CI workflow in `G2_SOURCE_MANIFEST.json`.
3. Validate the frozen G1 fixture SHA-256, and its Python canonical IR and
   144-birth ordered enumeration without altering the G1 source.
4. Build an independently implemented native C++20 mixed-radix enumerator
   with all compiler warnings fatal. Compare every G1 row against a separate
   Python itertools oracle. Run randomized subset and malformed-schema tests.
5. Re-audit interrupted local-file shard execution after subprocess exit at
   AFTER_SHARD, AFTER_RECEIPT and AFTER_CHECKPOINT. Missing and forged files
   must be rejected; incomplete unreceipted shards quarantined. Recovery must
   avoid recomputing previously verified shards.
6. Run adversarial anti-stall tests, including a fake zero-delta checkout,
   baseline mutation, modified gate source, forged approval and missing
   native code. A human report cannot satisfy these unit tests.
7. Only after every preceding step, compare 1,000,000 synthetically
   generated **structural strings**, Python vs C++ row by row and record
   throughput and checksum on the actual CI runner. This is **not**
   1,000,000 backtests, a simulation of prices, or an alpha measurement.
8. Publish a source-commit-pinned CI receipt; any failed step blocks
   engineering PASS. Include explicit next legitimate action and remaining
   product release gates.

The original M1 signing demo and G1 APK remain untouched. The latest G1
source baseline is independently tested, and the scientific `main` pointer,
GA2, holdout, real broker data and live trading stay closed.

## What this mechanism cannot promise

A GitHub workflow rejects noncompliant results but cannot make a model run
indefinitely or stop users with direct write privileges from bypassing an
unprotected branch. Requiring the CI status check in branch protection must
be separately enabled by an authorized repository administrator; do **not**
claim this has been configured without GitHub confirmation. The present G2
receipt chain is local and can be rolled back by an operator until a dynamic,
independently governed external witness is deployed and verified. Preserve
these as open product-release gates.

## Next gate

After a successful immutable G2 CI run: independently rehash the downloaded
receipt and verify its source commit, then write the G2 verified engineering
receipt and update product HEAD only for the mobile branch. Continue to G3
small, tick-accurate synthetic Bid/Ask engine parity with scientific authority
still disabled. Fail closed if CI does not finish or reveals a counterexample.
