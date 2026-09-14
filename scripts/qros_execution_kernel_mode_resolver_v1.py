#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

STABLE = "control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"
CANDIDATE = "control/QROS_PUBLIC_1000_EXECUTION_KERNEL_CANDIDATE_POINTER.json"


def git_blob(path: Path) -> str:
    b = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(b)).encode("ascii") + b"\0" + b).hexdigest()


def load(root: Path, rel: str):
    p = root / rel
    if not p.is_file():
        raise RuntimeError(f"MISSING:{rel}")
    return json.loads(p.read_text(encoding="utf-8"))


def req(c, code, detail=None):
    if not c:
        raise RuntimeError(code if detail is None else f"{code}:{detail}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root = Path(a.repo_root).resolve()
    stable = load(root, STABLE)
    cand = load(root, CANDIDATE)
    target_rel = cand.get("candidate_target_path")
    req(isinstance(target_rel, str) and target_rel, "CANDIDATE_TARGET_MISSING")
    req((root / target_rel).is_file(), "CANDIDATE_TARGET_FILE_MISSING")
    target_blob = git_blob(root / target_rel)
    req(target_blob == cand.get("candidate_target_git_blob_sha1"), "CANDIDATE_TARGET_BLOB_MISMATCH")
    stable_blob = git_blob(root / STABLE)

    parent_match = (
        stable.get("current_version") == cand.get("expected_parent_version")
        and stable_blob == cand.get("expected_parent_stable_blob_sha1")
        and stable.get("target_path") != target_rel
    )
    active_identity = (
        stable.get("current_version") == cand.get("candidate_version")
        and stable.get("target_path") == target_rel
        and stable.get("target_git_blob_sha1") == target_blob
    )
    active_valid = (
        active_identity
        and stable.get("active_validation_status") == "PASS"
        and stable.get("scientific_execution_authorized") is True
        and stable.get("authorized_action_scope") == "MACHINE_ACTION_TICKET_ONLY"
    )
    active_pending = active_identity and not active_valid

    matches = [
        ("CANDIDATE_VALIDATION", parent_match),
        ("ACTIVE_VALIDATION", active_pending),
        ("ACTIVE_EXECUTION", active_valid),
    ]
    selected = [name for name, ok in matches if ok]
    req(len(selected) == 1, "MODE_NOT_UNIQUE", selected)
    mode = selected[0]
    rec = {
        "schema": "QROS_GENERIC_KERNEL_MODE_RESOLUTION_1.0",
        "status": "PASS",
        "mode": mode,
        "stable_version": stable.get("current_version"),
        "candidate_version": cand.get("candidate_version"),
        "candidate_target_path": target_rel,
        "candidate_target_git_blob_sha1": target_blob,
        "stable_pointer_git_blob_sha1": stable_blob,
    }
    Path(a.out).write_text(json.dumps(rec, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rec, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(json.dumps({"status":"FAIL_CLOSED","error":str(e)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
