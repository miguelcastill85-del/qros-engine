"""Read-only forensic oracle. Never imports or executes QRCEL.

Inputs: recovered pointer/remote manifests/capsule, pinned release source,
and materialized evidence directory. Run before publishing a continuation.
"""
import argparse
import base64
import collections
import hashlib
import json
from pathlib import Path
import zlib


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()


def check(ok, name):
    if not ok:
        raise ValueError(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recovered", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    r = args.recovered
    load = lambda p: json.loads(p.read_bytes())
    pointer = load(r / "pointer.json")
    manifest_bytes = (r / "release_manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    check(sha(manifest_bytes) == pointer["release"]["manifest_sha256"], "manifest sha256")
    blob = hashlib.sha1(b"blob " + str(len(manifest_bytes)).encode() + b"\0" + manifest_bytes).hexdigest()
    check(blob == pointer["release"]["manifest_blob_sha1"], "manifest git identity")
    for path, digest in manifest["files_sha256"].items():
        check(sha((args.source / path).read_bytes()) == digest, "source " + path)
    check(manifest["files_sha256"][pointer["release"]["bootstrap_path"]] == pointer["release"]["bootstrap_sha256"], "launcher binding")
    em = load(r / "evidence_manifest.json")
    check(em["release_commit"] == pointer["release"]["commit"], "evidence release binding")
    for path, digest in em["files_sha256"].items():
        check(sha((args.evidence / path).read_bytes()) == digest, "evidence " + path)
    capsule_bytes = (r / "capsule.json").read_bytes()
    check(sha(capsule_bytes) == pointer["large_synthetic_recovery_capsule"]["sha256"], "capsule pointer")
    capsule = json.loads(capsule_bytes)
    check(capsule["schema"] == "QRCEL_GZIP_BASE64_RECOVERY_CAPSULE_V1", "capsule schema")
    check(set(capsule["files"]) == {"PLAN.json", "GOAL.json", "MAPPING.json", "CHECKPOINT.json", "RESUME_ANCHOR.json"}, "capsule closure")
    decoded = {}
    for name, item in capsule["files"].items():
        compressed = base64.b64decode(item["data"], validate=True)
        check(sha(compressed) == item["compressed_sha256"], "compressed " + name)
        stream = zlib.decompressobj(31)
        data = stream.decompress(compressed, 4194305)
        check(len(data) <= 4194304 and stream.eof and not stream.unused_data and not stream.unconsumed_tail, "bounded decode " + name)
        check(len(data) == item["uncompressed_bytes"] and sha(data) == item["sha256"], "decoded " + name)
        decoded[name] = json.loads(data)
    c = decoded["CHECKPOINT.json"]
    plan, goal, mapping, anchor = (decoded[x + ".json"] for x in ("PLAN", "GOAL", "MAPPING", "RESUME_ANCHOR"))
    check(c["schema"] == "QRCEL_KERNEL_CHECKPOINT_V1" and c["scientific_effect_authorized"] is False, "checkpoint scope")
    check(c["plan"] == plan and c["goal_contract"] == goal and c["goal_mapping"] == mapping, "checkpoint primary inputs")
    check(c["binding"]["plan_sha256"] == sha(canonical(plan)), "plan binding")
    check(c["binding"]["goal_binding"]["goal_sha256"] == sha(canonical(goal)), "goal binding")
    check(c["binding"]["goal_binding"]["mapping"] == mapping, "mapping binding")
    for name, digest in c["binding"]["source_sha256"].items():
        check(digest == manifest["files_sha256"]["cognitive/" + name], "checkpoint runtime identity " + name)
    check(sha(canonical(c["binding"])) == anchor["binding_sha256"], "external binding anchor")
    check(len(plan["tasks"]) == len(c["completed"]) == len(goal["requirements"]) == len(mapping) == 100, "counts")
    ids = {t["task_id"] for t in plan["tasks"]}
    check(len(ids) == 100 and ids == set(c["completed"]) == set(mapping.values()), "coverage")
    check(set(mapping) == {g["id"] for g in goal["requirements"]}, "requirement IDs")
    expected = {"fraction": str(128 * (10**64 - 1))}
    tasks = {t["task_id"]: t for t in plan["tasks"]}
    for task in plan["tasks"]:
        check(task["operation"] == "EXACT_SUM" and task["parent_ids"] == [], "oracle preconditions")
        check(task["inputs"] == {"numbers": ["9" * 64] * 128, "include_parent_sums": False}, "oracle inputs")
        check(sha(canonical(task["inputs"])) == task["inputs_sha256"], "task input digest")
        row = c["completed"][task["task_id"]]
        check(row["output"] == expected and row["sha256"] == sha(canonical(expected)), "analytic result")
    for requirement in goal["requirements"]:
        task = tasks[mapping[requirement["id"]]]
        check(requirement["inputs_sha256"] == task["inputs_sha256"] and requirement["operation"] == task["operation"] and requirement["parent_ids"] == task["parent_ids"], "requirement semantics")
    prev = None
    events = collections.defaultdict(list)
    for seq, record in enumerate(c["ledger"]):
        payload = record["payload"]
        check(payload["seq"] == seq and payload["previous"] == prev and sha(canonical(payload)) == record["sha256"], "ledger chain")
        event = payload["event"]
        check(event["task_id"] in ids, "ledger task")
        events[event["task_id"]].append(event["type"])
        if event["type"] == "COMPLETE":
            row = c["completed"][event["task_id"]]
            check(event["output_sha256"] == row["sha256"] and event["evidence_sha256"] == sha(canonical(row["evidence"])), "ledger result binding")
        prev = record["sha256"]
    check(len(c["ledger"]) == anchor["event_count"] == 200 and prev == anchor["head_sha256"], "ledger external extent")
    check(set(events) == ids and all(v == ["START", "COMPLETE"] for v in events.values()), "no partial or duplicate tasks")
    fresh = load(args.evidence / "FRESH_VALIDATION.json")
    check(fresh["restored"]["receipt"]["checkpoint_sha256"] == capsule["files"]["CHECKPOINT.json"]["sha256"], "receipt checkpoint")
    check(fresh["restored"]["receipt"]["newly_completed"] == 0, "historical no replay receipt")
    result = {"schema": "QRCEL_FORENSIC_VERIFICATION_V1", "status": "PASS", "method": "standalone stdlib hash/decode/analytic oracle; no QRCEL imports", "release_commit": pointer["release"]["commit"], "source_files_verified": len(manifest["files_sha256"]), "evidence_files_verified": len(em["files_sha256"]), "capsule_files_verified": len(decoded), "analytic_results_verified": 100, "ledger_events_verified": 200, "new_task_executions": 0, "new_model_calls": 0, "scientific_dispatches": 0, "full_qrcel_complete": False, "checkpoint_sha256": capsule["files"]["CHECKPOINT.json"]["sha256"], "pointer_sha256": sha((r / "pointer.json").read_bytes()), "verifier_sha256": sha(Path(__file__).read_bytes())}
    args.out.write_bytes(json.dumps(result, indent=2, sort_keys=True).encode() + b"\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
