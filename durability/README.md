# QROS Artifact Durability Closure Gate v2

Run before closing every scientific stage. A hash is accepted only when the corresponding bytes exist in two independent durable stores and survive a clean restore. The script emits canonical JSON and exits `2` on every incomplete or inconsistent condition.

```bash
python3 durability/qros_artifact_closure_gate.py --manifest packet.json --store git=/mounted/git --store cas=/mounted/cas --out receipt.json
```

The orchestration layer must additionally verify authenticated remote readback, next-stage dry-run and atomic expected-parent HEAD promotion. Never use this control to open holdout or reconstruct scientific membership approximately.

Tests: `python3 -m unittest durability/test_artifact_closure_gate.py` from `durability/` or with that directory on `PYTHONPATH`.
