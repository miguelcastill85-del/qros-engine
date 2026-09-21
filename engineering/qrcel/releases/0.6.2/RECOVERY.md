# QRCEL 0.6.2 — recovery and evaluation

Recover the exact source release selected by control/QRCEL_ENGINEERING_CURRENT.json. Verify launcher SHA-256 and manifest Git blob before isolated execution. Q07 is closed only for cooperative invocations of this local launcher on one shared state directory. Direct API callers, old launchers and distributed state are outside this admission contract.

Use full option names. The kernel entry acquires a per-run flock before opening SQLite. Admission wait defaults to 10 seconds (0–15 allowed), within the overall wall deadline. KERNEL_ADMISSION_TIMEOUT is a safe local admission failure, not a completed task. Do not remove lock files or retry uncertain external effects.

Reproduce final validation with: python3 -I -S -B validate_release.py --source /verified/release --anchors ANCHORS.json --out /new/evidence. The validator checks release identities, runs four real kernel processes over a synthetic 100-task plan, checks exact sums and 200 events, then restores in another root and starts a session. Protocol is written before observations. TARGETED.log includes 26 affected tests, including 14 new admission/identity tests. RED_ARGUMENTS.log preserves the two failing expectations on 0.6.1; it is not a green acceptance log.

RECOVERY_CAPSULE.json stores the exact synthetic plan, goal, mapping, checkpoint and external prefix anchor as gzip+base64. Verify its externally pinned hash first, then each compressed hash and decoded hash/size. Bound decompression to 4 MiB per file, reject trailing data and unexpected filenames, and write into a new directory. These artifacts are synthetic evidence, never trading progress. SESSION.json and SESSION_CHECKPOINT.json preserve actual saved bytes; capability is not inheritable.

Kernel/runtime/goal_contract code identities were preserved. Restoration still requires their bound plan, goal, authority and source hashes, plus the external checkpoint and history anchors. Never rewrite a checkpoint binding to force migration. Do not silently roll back to earlier launchers with the identity-prefix issue.

The full-system gates remain pending: current authority transition contracts, general objective/ontology sufficiency, observed matched model/system evaluation, independent sealed custody and operational promotion. No background service, paid model use or economic dispatch was created.
