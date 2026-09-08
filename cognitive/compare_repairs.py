"""Paired DEVELOPMENT probes on frozen components and candidate; no model benchmark."""
from __future__ import annotations
import copy
import base64
import gzip
import importlib.util
import json
import tempfile
import types
from pathlib import Path

from . import runtime as v
from .tests.test_runtime import RuntimeTests, ROOT, ANCHOR, load_module


def frozen_authority_validator():
    """Recover the pinned baseline in memory; never require a prior local restore."""
    carrier = (ROOT / "control/recovery/qros_control_authority_validator_v2.py.gz.b64").read_bytes()
    if len(carrier) != 1228 or v.sha256(carrier) != "ffeec480a3a07a914a8b50a8ffc12ba5dab06b8505ad63615819eb6f2f2ba1ce":
        raise ValueError("Frozen authority carrier mismatch")
    compressed = base64.b64decode(carrier, validate=True)
    if len(compressed) != 919 or v.sha256(compressed) != "7db6eb299b6eeffeb56b9dcee5b77e06a98468aefd40bb04649558836b07e03b":
        raise ValueError("Frozen authority gzip mismatch")
    raw = gzip.decompress(compressed)
    if len(raw) != 2035 or v.sha256(raw) != "271c23579bbf2cbf5b5e3be624ab1fcb7d3ee75d8ebca5250919c297ad01b683":
        raise ValueError("Frozen authority source mismatch")
    module = types.ModuleType("old_authority")
    exec(compile(raw, "<verified-frozen-authority-v2>", "exec"), module.__dict__)
    return module


def compare() -> dict:
    old_a = frozen_authority_validator()
    old_h = load_module("old_holdout", ROOT / "scripts/qros_holdout_genealogy_preflight.py")
    old_u = load_module("old_units", ROOT / "scripts/qros_execution_unit_binding_preflight.py")
    old_c = load_module("old_controller", ROOT / "scripts/qros_persistent_chat_controller.py")
    cf = load_module("controller_test_fixture", ROOT / "tests/test_qros_persistent_chat_controller.py")
    hf = load_module("holdout_test_fixture", ROOT / "tests/test_holdout_genealogy_preflight.py")
    uf = load_module("units_test_fixture", ROOT / "tests/test_execution_unit_binding_preflight.py")
    case = RuntimeTests()
    case.setUp()
    rows = []
    def result(fn):
        try:
            value = fn()
            return {"accepted": True, "value": value}
        except ValueError as exc:
            return {"accepted": False, "error": str(exc), "type": type(exc).__name__}
    def row(identity, expected, before, after):
        rows.append({"id": identity, "expected_acceptance": expected, "before": before, "after": after,
                     "before_correct": before["accepted"] is expected, "after_correct": after["accepted"] is expected})
    def old_authority():
        r = old_a.validate(*(case.root / path for path in [v.MANIFEST, *v.PATHS.values()]), require_execution=True)
        if r["status"] != "PASS":
            raise ValueError(r["errors"])
        return r
    try:
        # Same bytes and self-reporting packet seen by old checker and new inspector.
        packet = hf.valid_packet()
        contracts = {}
        for key, path in packet["authority_refs"].items():
            doc = {"schema": "QROS_BOUND_EVIDENCE_V1", "status": "FAIL", "failures": [],
                   "campaign_id": packet["campaign_id"], "root_genealogy_id": packet["root_genealogy_id"],
                   "scope": "SYNTHETIC_ONLY", "role": key, "authority_manifest_sha256": "a" * 64,
                   "claims": {"complete": True}}
            packet["authority_sha256"][key] = case.write(path, doc)
            contracts[key] = v.EvidenceContract(path, packet["authority_sha256"][key], doc["schema"],
                doc["campaign_id"], doc["root_genealogy_id"], key, doc["scope"], "a"*64, (("complete",True),))
        row("F01", False, result(lambda: old_h.build_receipt(packet, case.root)),
            result(lambda: v.check_bound_packet(case.snapshot, contracts, packet)))

        doc, contract, new_packet = case.units()
        doc["frozen_semantics"]["atr_stop_mult"] = "99"
        import dataclasses
        contract = dataclasses.replace(contract, sha256=case.write(contract.path, doc))
        packet = uf.valid_packet()
        # Old checker ignores all referenced content; new one compares it with packet bindings.
        for key, path in packet["authority_refs"].items():
            packet["authority_sha256"][key] = case.write(path, doc)
        row("F02", False, result(lambda: old_u.build_receipt(packet, case.root)),
            result(lambda: v.inspect_units(case.snapshot, contract, new_packet)))

        m = case.authority()
        m["single_active_authority"]["head"]["path"] = "wrong.json"
        case.write(v.MANIFEST, m)
        anchor = v.git_blob(v.canonical(m))
        row("F03", False, result(old_authority), result(lambda: v.observe_authority(case.snapshot, anchor)))

        m = case.authority()
        for key in ("campaign", "authority_epoch", "schema"):
            m.pop(key)
        for role, path in v.PATHS.items():
            obj = json.loads(case.snapshot.read(path))
            for key in ("campaign", "authority_epoch", "schema"):
                obj.pop(key)
            data = v.canonical(obj)
            case.write(path, data)
            m["single_active_authority"][role]["git_blob_sha1"] = v.git_blob(data)
        case.write(v.MANIFEST, m)
        anchor = v.git_blob(v.canonical(m))
        row("F04", False, result(old_authority), result(lambda: v.observe_authority(case.snapshot, anchor)))

        protocol = json.loads((ROOT/"governance/QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_v1.json").read_bytes())
        obs = v.observe_authority(v.Snapshot(ROOT), ANCHOR)
        row("F05", True, result(lambda: old_c.validate(protocol, obs.queue, obs.state, obs.head)),
            result(lambda: v.inspect_active_queue(obs)))

        protocol, queue, state, head = cf.fixtures()
        a = queue["queue"][0]
        b = copy.deepcopy(a)
        b["item_id"] = "G30-TEST-B"
        a["prerequisites"] = [b["item_id"]]
        b["prerequisites"] = [a["item_id"]]
        queue["queue"].append(b)
        row("F06", False, result(lambda: old_c.validate(protocol, queue, state, head)),
            result(lambda: v.check_dag(queue["queue"])))

        protocol, queue, state, head = cf.fixtures()
        queue["queue"][0]["prerequisites"] = ["MISSING_RUNTIME_CAPABILITY"]
        row("F07", False, result(lambda: old_c.next_item(queue)),
            result(lambda: v.next_ready(queue["queue"])))

        checkpoint, kwargs = case.checkpoint()
        checkpoint.update(queue_item_id="TEST_ONLY", scientific_outcome="NONE", output_sha256="NOT_A_HASH",
                          holdout_exposure="SEALED_NO_ACCESS")
        kwargs["expected_holdout_exposure"] = "SEALED_NO_ACCESS"
        row("F08", False, result(lambda: old_c.validate_checkpoint(checkpoint, protocol)),
            result(lambda: v.verify_checkpoint(case.snapshot, checkpoint, **kwargs)))
    finally:
        case.doCleanups()
    return {"schema": "QRCEL_PAIRED_COMPONENT_REPAIR_V1", "scope": "DEVELOPMENT_SYNTHETIC_KNOWN_FAILURES",
            "model_benchmark": False, "statistical_parity_claim": False, "cases": rows,
            "before_correct": sum(r["before_correct"] for r in rows),
            "after_correct": sum(r["after_correct"] for r in rows), "total": len(rows),
            "scientific_writes": 0, "economic_reads": 0}


if __name__ == "__main__":
    receipt = compare()
    print(json.dumps(receipt, sort_keys=True, indent=2))
    raise SystemExit(0 if all(r["after_correct"] for r in receipt["cases"]) else 1)
