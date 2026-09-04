# QROS persistent execution cycle

Use the `qros-rise-execution-governor` skill and execute one persistent QROS cycle in
`miguelcastill85-del/qros-engine`. This is an execution request, not a status-only request.

1. Fetch the current `main` ref and `control/HEAD.json`; never assume the HEAD version from
   this prompt. Read `governance/QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_v1.json`,
   `control/persistent_execution/RUN_QUEUE.json`, `control/persistent_execution/STATE.json`,
   and `control/persistent_execution/FOREGROUND.json` from that same commit.
2. Verify HEAD lineage, mandatory governance references, source durability, holdout/exposure
   state, and current user authorization. Reconcile the stored queue against HEAD and all
   newer valid receipts. Do not repeat closed scientific work because runtime files vanished.
3. This automation is an IDLE-FILL worker, not the preferred owner while the user is actively
   driving QROS in chat. Evaluate `FOREGROUND.json` with
   `scripts/qros_persistent_foreground_guard.py --surface automation`. If foreground control
   is ACTIVE, do no scientific work in this wakeup and do not claim a lease. The automation
   may resume only on the first hourly wakeup after foreground `active_until` has expired.
4. Acquire the single-writer lease only through a fast-forward commit based on the exact
   observed `main` SHA. Never force-push. A lease protects only ACTIVE COMPUTATION; it is not
   an idle reservation. If a foreign lease is fresh, perform no scientific work. If its
   heartbeat is older than the protocol heartbeat maximum, reconcile durable receipts,
   quarantine ambiguous partials, write a recovery receipt, and reclaim with a new fence;
   do not wait for the nominal TTL merely because `expires_at` is later.
5. Execute every legitimate, dependency-ready, preregistered chunk that fits safely in this
   run. Do not stop after a micro-milestone and do not ask the user to say continue. Use exact
   identities, durable runner sources, deterministic chunks, observable progress and bounded
   retries. Search GitHub, File Library and available project surfaces before declaring an
   artifact unavailable. Deterministic rematerialization is recovery, not new research.
6. Validate schema, coverage, hashes, causality and applicable parity before promotion.
   Persist each valid chunk and its checkpoint atomically. Quarantine partial or ambiguous
   output. Heartbeat at least every 20 minutes during active computation.
7. MANDATORY TURN-END RULE: before this automation wakeup ends for ANY reason, first persist
   the latest safe checkpoint, then RELEASE THE OWNED LEASE by fencing/CAS and verify
   `STATE.lease == null`. Never intentionally leave a lease alive for the next hourly wakeup.
   The 95-minute TTL exists only for crash recovery. Execution-limit checkpoints must also
   release the lease before the wakeup returns.
8. Preserve all scientific invariants. Never open holdout without the genealogy firewall
   PASS, never score economics without the execution-unit firewall PASS, never retune from
   results, never select a single winner, never run live or MT5 unless separately authorized,
   never activate paid infrastructure, and never claim branch exhaustion without its receipts.
9. If the execution limit is reached, persist the exact resume action, release the lease and
   yield. The next hourly wakeup continues automatically only if foreground control is idle.
   Notify the user only for a material milestone, route change, real blocker, or required
   scientific decision.

The GitHub control plane is authoritative. The chat filesystem is an ephemeral execution
cache. Never claim computation continues between automation wakeups.

## Enforced implementation (revision 3)

Before dispatch, execute the current controller validation including the exact HEAD blob and
run the foreground guard. Use `scripts/qros_persistent_chat_controller.py` for ordinary
lease/checkpoint transitions and `scripts/qros_persistent_foreground_guard.py` for foreground,
stale-heartbeat and turn-end lease-leak decisions. Promote state, queue, checkpoint and
receipts together with the Git Data transaction in `scripts/qros_persistent_git_cas.py`, or
reproduce that exact transaction with the GitHub connector: read exact main, create blobs,
create a tree based on its tree, create one commit with that exact parent, re-read main, and
update `heads/main` with `force=false`. A contents-file update is not sufficient for a
scientific lease claim or multi-file checkpoint promotion.

Reject MT5, live, paid infrastructure, branch exhaustion, single-winner selection, disabling
all-passers, HEAD schema/blob drift, stale fencing tokens, CAS conflicts, automation execution
while interactive foreground is active, and any wakeup that attempts to end with a non-null
owned lease.
