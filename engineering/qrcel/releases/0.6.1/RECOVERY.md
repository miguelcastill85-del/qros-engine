# QRCEL 0.6.1 recovery evidence

Source release: `4f4eea7eb281ae0ac5e149109ddf5b9d2d3ff6e0`. Read the current project pointer and independently verify launcher and manifest identities. Source release contains 283 listed files plus manifest.

`RECOVERY_CAPSULE.json` contains a synthetic 100-task plan, exact goal, requirement mapping, checkpoint and external prefix anchor. It is development evidence, not trading progress. Verify the capsule SHA-256 from the project pointer before parsing. Each entry has gzip+base64 bytes, compressed SHA-256, decoded size and SHA-256. Decode to a new task directory with a 4 MiB output bound per file; reject unexpected names or trailing compressed data. Verify both hashes and exact declared size before use. Do not execute the capsule as code.

Run the verified launcher with kernel entry, plan hash, historical V191 authority blob, explicit goal hash/mapping, checkpoint hash and resume-anchor hash. The final validation exercised restoration in a different directory and process: 100 completed tasks, zero newly completed, identical checkpoint hash, externally verified prefix and exact arithmetic oracle. Capability must be measured in the new runtime.

The saved SESSION bytes were rematerialized deterministically from the observed receipt by removing only its stdout-added checkpoint_directory; both saved session and checkpoint hashes matched the files observed before temporary-directory cleanup. These JSONs do not grant inherited capability.

Q06 storage compatibility is fixed in this release. Q07 admission remains pending: use a single writer per run. The observed bounded lock timeout is not corruption. A pure-local retry is permitted only after confirmed lock-owner release, with unchanged identities and remaining budget. No automatic retry of uncertain external mutations.

Full QRCEL promotion and model parity remain unverified.
