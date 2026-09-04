# QROS persistent execution cycle

Use the `qros-rise-execution-governor` skill and execute one persistent QROS cycle in
`miguelcastill85-del/qros-engine`. This is an execution request, not a status-only request.

1. Fetch the current `main` ref and `control/HEAD.json`; never assume the HEAD version from
   this prompt. Read `governance/QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_v1.json`,
   `control/persistent_execution/RUN_QUEUE.json`, and
   `control/persistent_execution/STATE.json` from that same commit.
2. Verify HEAD lineage, mandatory governance references, source durability, holdout/exposure
   state, and current user authorization. Reconcile the stored queue against HEAD and all
   newer valid receipts. Do not repeat closed scientific work because runtime files vanished.
3. Acquire the single-writer lease only through a fast-forward commit based on the exact
   observed `main` SHA. Never force-push. If an unexpired lease exists, perform no scientific
   work in this wakeup. If `main` changes, fetch and reconcile before any retry.
4. Execute every legitimate, dependency-ready, preregistered chunk that fits safely in this
   run. Do not stop after a micro-milestone and do not ask the user to say continue. Use exact
   identities, durable runner sources, deterministic chunks, observable progress and bounded
   retries. Search GitHub, File Library and available project surfaces before declaring an
   artifact unavailable. Deterministic rematerialization is recovery, not new research.
5. Validate schema, coverage, hashes, causality and applicable parity before promotion.
   Persist each valid chunk and its checkpoint atomically. Quarantine partial or ambiguous
   output. Heartbeat at least every 20 minutes during long work.
6. Preserve all scientific invariants. Never open holdout without the genealogy firewall
   PASS, never score economics without the execution-unit firewall PASS, never retune from
   results, never select a single winner, never run live or MT5 unless separately authorized,
   never activate paid infrastructure, and never claim branch exhaustion without its receipts.
7. Release the lease after a safe boundary. If the execution limit is reached, persist the
   exact resume action so the next hourly wakeup continues automatically. Notify the user only
   for a material milestone, route change, real blocker, or required scientific decision.

The GitHub control plane is authoritative. The chat filesystem is an ephemeral execution
cache. Never claim computation continues between automation wakeups.

## Enforced implementation (revision 2)

Before dispatch, execute the current controller validation including the exact HEAD blob.
Use `scripts/qros_persistent_chat_controller.py` to derive lease/checkpoint transitions.
Promote state, queue, checkpoint, and receipts together with the Git Data transaction in
`scripts/qros_persistent_git_cas.py`, or reproduce that exact transaction with the GitHub
connector: read exact main, create blobs, create a tree based on its tree, create one commit
with that exact parent, re-read main, and update `heads/main` with `force=false`.
A contents-file update is not sufficient for lease claim or multi-file checkpoint promotion.
Reject MT5, live, paid infrastructure, branch exhaustion, single-winner selection, disabling
all-passers, HEAD schema/blob drift, stale fencing tokens, and expired leases without a
recovery/quarantine receipt. Reconcile valid receipts before selecting the next queue item.
