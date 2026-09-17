# QROS Artifact Durability Closure

## Local artifact closure gate v2

Run before closing every scientific stage. A hash is accepted only when the corresponding bytes exist in two independent durable stores and survive a clean restore. The gate emits canonical JSON and fails closed on incomplete or inconsistent conditions.

## GitHub terminal publication FSM v1

`qros_github_closure_fsm.py` closes the orchestration gap between a valid local artifact set and durable GitHub publication without mutating the scientific frontier. Publication identity freezes the operation id, expected parent commit, payload SHA-256, required GitHub path-to-blob mapping, and scientific-authority snapshot.

State is monotonic:

`PREPARED -> COMMIT_CREATED -> REF_PROMOTED -> CLOSED`

`CLOSED`, `CONFLICT`, and `BLOCKED` are terminal fixed points. Stale parents, wrong commit parents, ref mismatches, or remote readback mismatches fail closed. Retryable failures have a finite retry budget. Duplicate events after terminal closure are idempotent no-ops.

`CLOSED` is reachable only after authenticated remote readback proves that the promoted GitHub HEAD equals the intended commit and every required path resolves to its frozen blob SHA. The readback event closes atomically so there is no dangling post-readback state that can re-enter the publication loop.

The FSM is infrastructure-only: it must not open holdout, economic PnL, GA2, FIRST_GATE, or mutate the stable scientific authority.

For GitHub publication, build the complete tree against the frozen parent, create exactly one commit, fast-forward the branch without force, read back the branch and every required path, then feed those exact observations to the FSM. If the parent moved, stop and rebuild from the new authority; never force-push or reuse a stale operation identity.

Tests:

```bash
PYTHONPATH=durability python3 -m unittest \
  durability/test_artifact_closure_gate.py \
  durability/test_github_closure_fsm.py
```
