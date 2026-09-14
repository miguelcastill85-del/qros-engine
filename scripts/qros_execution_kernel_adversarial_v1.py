#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

STABLE = "control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"
SENTINELS = {"DERIVE_FROM_LEDGER_ONLY", "INVALID_FIRST_GATE", "EXPLICIT_REPAIRED_STATE_ONLY", "POLICY_DEFINED_NEXT_STATE"}


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def dump(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def blob_bytes(b: bytes):
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()


def blob_file(p: Path):
    return blob_bytes(p.read_bytes())


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def required_paths(repo: Path, target_rel: str):
    target = load(repo / target_rel)
    paths = {STABLE, target_rel}
    k = target["execution_kernel"]
    for key in ("governance", "execution_map", "decision_ledger"):
        paths.add(k[key]["path"])
    for rel in target.get("authority", {}).values():
        if isinstance(rel, str) and rel.endswith((".json", ".py")):
            paths.add(rel)
    return sorted(paths)


def mini_repo(repo: Path, target_rel: str, dest: Path):
    for rel in required_paths(repo, target_rel):
        src, dst = repo / rel, dest / rel
        if not src.is_file():
            raise RuntimeError(f"required fixture missing: {rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def compile_cmd(repo_root: Path, target_rel: str, out: Path, compiler: Path):
    return [sys.executable, str(compiler), "--repo-root", str(repo_root), "--target", target_rel, "--out", str(out)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--compiler", default="scripts/qros_execution_kernel_compile_v1.py")
    ap.add_argument("--oracle", default="scripts/qros_execution_kernel_oracle_v1.py")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    repo = Path(a.repo_root).resolve()
    compiler = (repo / a.compiler).resolve()
    oracle = (repo / a.oracle).resolve()
    cases = []

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        primary = td / "primary.json"
        r = run(compile_cmd(repo, a.target, primary, compiler))
        if r.returncode != 0:
            raise RuntimeError(f"baseline compiler failed: {r.stderr}")
        oracle_out = td / "oracle.json"
        ro = run([sys.executable, str(oracle), "--repo-root", str(repo), "--target", a.target, "--primary-ticket", str(primary), "--out", str(oracle_out)])
        if ro.returncode != 0:
            raise RuntimeError(f"baseline oracle failed: {ro.stderr}")
        cases.append({"case": "baseline_primary_oracle", "expected": "PASS", "observed": "PASS"})

        target = load(repo / a.target)
        emap = load(repo / target["execution_kernel"]["execution_map"]["path"])
        states = emap.get("states", {})
        closure_ok = True
        for sid, spec in states.items():
            if spec.get("deterministic") is not True or not spec.get("authorized_action"):
                closure_ok = False
            for edge in (spec.get("success_state"), spec.get("failure_state")):
                if edge not in states and edge not in SENTINELS:
                    closure_ok = False
        if not closure_ok:
            raise RuntimeError("execution map closure failed")
        cases.append({"case": "execution_map_closure", "expected": "PASS", "observed": "PASS"})

        def expect_fail(name, mutate):
            case_root = td / name
            mini_repo(repo, a.target, case_root)
            mutate(case_root)
            rr = run(compile_cmd(case_root, a.target, case_root / "ticket.json", compiler))
            ok = rr.returncode != 0
            cases.append({"case": name, "expected": "FAIL_CLOSED", "observed": "FAIL_CLOSED" if ok else "UNEXPECTED_PASS", "stderr_tail": rr.stderr[-500:]})
            if not ok:
                raise RuntimeError(f"mutation unexpectedly passed: {name}")

        def tload(r): return load(r / a.target)
        def tsave(r, x): dump(r / a.target, x)

        expect_fail("mutate_parent_version", lambda r: (lambda x: (x.__setitem__("supersedes_frontier_version", "V000"), tsave(r, x)))(tload(r)))

        def mutate_contract_blob(r):
            t = tload(r); rel = t["authority"]["first_gate_multiplicity_contract"]
            p = r / rel; obj = load(p); obj["status"] = "MUTATED"; dump(p, obj)
        expect_fail("mutate_authority_blob", mutate_contract_blob)

        def mutate_firewall(r):
            t = tload(r); t["economic_pnl_read"] = True; tsave(r, t)
        expect_fail("mutate_economic_firewall", mutate_firewall)

        def mutate_binding_semantic(r):
            t = tload(r); rel = t["authority"]["minimal_dev_carrier_binding"]
            p = r / rel; b = load(p); b["xau"]["verification"] = "FAIL"; dump(p, b)
            t["authority_pins"]["minimal_dev_carrier_binding_git_blob_sha1"] = blob_file(p); tsave(r, t)
        expect_fail("mutate_dev_binding_semantic", mutate_binding_semantic)

        def mutate_subject(r):
            t = tload(r); t["current_first_gate"]["first_gate_order"] = 2; tsave(r, t)
        expect_fail("mutate_current_subject", mutate_subject)

        def mutate_unknown_state(r):
            t = tload(r); t["execution_kernel"]["current_state"] = "UNDECLARED_STATE"; tsave(r, t)
        expect_fail("mutate_unknown_state", mutate_unknown_state)

        def mutate_duplicate_fifo(r):
            t = tload(r); rel = t["authority"]["promotion_ledger"]
            p = r / rel; led = load(p); led["completed_and_promoted_shards"][1]["first_gate_order"] = 1; dump(p, led)
            t["authority_pins"]["promotion_ledger_git_blob_sha1"] = blob_file(p); tsave(r, t)
        expect_fail("mutate_duplicate_fifo_order", mutate_duplicate_fifo)

    result = {
        "schema": "QROS_DETERMINISTIC_EXECUTION_KERNEL_ADVERSARIAL_RECEIPT_1.0",
        "status": "PASS" if all(c["observed"] == c["expected"] for c in cases) else "FAIL",
        "cases": cases,
        "independent_oracle_executed": True,
        "mutation_count": sum(1 for c in cases if c["expected"] == "FAIL_CLOSED")
    }
    raw = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    result["receipt_sha256"] = hashlib.sha256(raw).hexdigest()
    Path(a.out).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "cases": len(cases), "mutations": result["mutation_count"], "receipt_sha256": result["receipt_sha256"]}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(json.dumps({"status":"FAIL_CLOSED","error":str(e)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
