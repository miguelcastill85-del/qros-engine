# QROS persistent execution cycle — human-first enforced

Use the QROS Governor and execute one persistent QROS cycle in `miguelcastill85-del/qros-engine`.

Before doing or reporting anything, recover current `main` and `control/HEAD.json`, then read these mandatory governance files from the same authority:

- `governance/QROS_HUMAN_INTERFACE_v1.json`
- `governance/QROS_HUMAN_REPORTING_ENFORCEMENT_v1.json`
- `governance/QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_v1.1.json`
- `control/persistent_execution/RUN_QUEUE.json`
- `control/persistent_execution/STATE.json`
- `control/persistent_execution/FOREGROUND.json`

The human interface is a hard gate, not a style suggestion. Every user-facing QROS notification must first explain in plain Spanish: what is being done, why, what was found, what it means, the exact current point, and what comes next and why. Technical identifiers, hashes, commits, blobs, fences, manifests and paths belong only in a compact secondary audit layer unless the user explicitly asks for technical-only detail.

A technical-first or technical-only user report is a control failure and must be rewritten before sending.

All execution, lease, checkpoint, holdout, source-durability, CAS, foreground-priority and scientific rules from `QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_v1.json` revision 3 remain mandatory through the v1.1 extension. Do not repeat closed science, do not open holdout without authorization, do not retune from results, do not select a single winner, and do not run MT5/live/paid infrastructure unless separately authorized.

This automation is idle-fill only while foreground is inactive. Use the maximum safe work per wakeup. Before every wakeup ends, persist the latest safe checkpoint, release any owned lease, and verify `STATE.lease == null`.

Never claim continuous computation between wakeups.
