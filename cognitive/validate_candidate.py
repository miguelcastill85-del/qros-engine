"""Reproduce software acceptance and save atomic, candidate-only receipts.

This is an engineering harness, not a scientific runner. It writes only to a
new directory under cognitive/checkpoints. It never edits control authority.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from .runtime import canonical, relative_parts, sha256, git_blob
from .compare_repairs import compare
from .shadow import run as shadow

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = "8e81e70881796288f79abfa0280e73676d19a06f"


def atomic_write(path: Path, data: bytes):
    temp = path.with_name(path.name + ".partial")
    with temp.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def run(name):
    parts = relative_parts(name)
    if len(parts) != 1:
        raise ValueError("Run name must be a single directory name")
    parent = ROOT / "cognitive/checkpoints"
    parent.mkdir(exist_ok=True)
    if parent.resolve() != parent or parent.is_symlink():
        raise ValueError("Checkpoint directory must remain inside the candidate")
    out = parent / name
    out.mkdir(exist_ok=False)
    protected = {}
    for group in ("control", "scripts", "tests", "governance", "handoff"):
        for path in (ROOT/group).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                protected[path.relative_to(ROOT).as_posix()] = sha256(path.read_bytes())
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8"}
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "cognitive/tests", "-p", "test_*.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_qros_persistent*.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_holdout_genealogy_preflight.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_execution_unit_binding_preflight.py", "-v"]]
    tests=[]
    for i, command in enumerate(commands):
        started=time.monotonic()
        p=subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=60)
        counts = re.findall(rb"Ran ([0-9]+) tests? in", p.stderr)
        count = int(counts[-1]) if counts else 0
        receipt={"command":command,"returncode":p.returncode,"tests_run":count,"stdout":p.stdout.decode(),
                 "stderr":p.stderr.decode(),"wall_seconds":time.monotonic()-started}
        tests.append(receipt)
        atomic_write(out/f"suite_{i}.json",canonical(receipt))
    paired=compare()
    shadow_receipt=shadow(ROOT,ANCHOR)
    atomic_write(out/"paired_component_comparison.json",canonical(paired))
    atomic_write(out/"shadow.json",canonical(shadow_receipt))
    changed=[p for p,h in protected.items() if not (ROOT/p).is_file() or sha256((ROOT/p).read_bytes())!=h]
    sources={p.relative_to(ROOT).as_posix():sha256(p.read_bytes()) for p in (ROOT/"cognitive").rglob("*.py")}
    success=(all(t["returncode"]==0 and t["tests_run"] > 0 for t in tests)
             and paired["after_correct"]==8 and shadow_receipt["status"]=="PASS" and not changed)
    receipt={"schema":"QRCEL_CANDIDATE_VALIDATION_V1","status":"PASS" if success else "FAIL",
             "scope":"SOFTWARE_COMPONENTS_AND_READ_ONLY_SHADOW","source_sha256":sources,
             "repair_contract_sha256":sha256((ROOT/"cognitive/REPAIR_CONTRACT.json").read_bytes()),
             "test_suites":len(tests),"tests_run":sum(t["tests_run"] for t in tests),
             "paired_cases":8,"paired_after_correct":paired["after_correct"],
             "protected_sources_checked":len(protected),"protected_sources_changed":changed,
             "shadow_status":shadow_receipt["status"],"scientific_dispatch_authorized":False,
             "full_qrcel_fixed_point":False,"model_benchmark":False,"parity":"INSUFFICIENT_EVIDENCE",
             "promoted":False,"background_running":False}
    atomic_write(out/"VALIDATION_RECEIPT.json",canonical(receipt))
    manifest={"schema":"QRCEL_CANDIDATE_CHECKPOINT_MANIFEST_V1","files":{p.name:sha256(p.read_bytes()) for p in out.iterdir() if p.is_file()}}
    atomic_write(out/"MANIFEST.json",canonical(manifest))
    print(json.dumps({"status":receipt["status"],"checkpoint":str(out),"paired_correct":paired["after_correct"],
                      "protected_changed":changed},sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-name",required=True)
    raise SystemExit(run(parser.parse_args().run_name))
