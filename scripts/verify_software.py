#!/usr/bin/env python3
"""Run the real native and independent-reference suites and save bound evidence.

This is a build/test adapter, never a trading runtime. It requires a successful
build receipt and verifies its binary/source identities before and after tests.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
SUITES=["parity_randomized", "qdata_parity_randomized", "qdata_negative_cases", "custody_negative_cases",
        "custody_parity_randomized", "time_authority_negative_cases", "time_authority_parity_randomized"]
TEST_FILES=["tests/test_core.cpp", "tests/test_pipeline.cpp", "tests/test_pipeline_integration.py", "tests/prepare_fixtures.py",
            "tests/check_active_authorities.py", "tests/time_fixture_lib.py", "scripts/verify_software.py",
            "reference/replay_reference.py", "reference/qdata_reference.py", "reference/custody_reference.py",
            "reference/time_authority_reference.py", "reference/pipeline_reference.py"]+[f"tests/{x}.py" for x in SUITES]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--leak-check", choices=["enabled", "disabled"], default="enabled")
    args=parser.parse_args()
    build, output=args.build.resolve(), args.out.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit("verification output must be new or empty")
    (output/"logs").mkdir(parents=True, exist_ok=True)
    (output/"tmp").mkdir()
    receipt_path=build/"BUILD_RECEIPT.json"
    receipt=json.loads(receipt_path.read_text())
    receipt_hash=sha(receipt_path)
    bindings={name:sha(ROOT/name) for name in TEST_FILES}
    env=dict(PATH="/usr/bin:/bin", LANG="C", LC_ALL="C", TZ="UTC", TMPDIR=str(output/"tmp"), PYTHONDONTWRITEBYTECODE="1",
             ASAN_OPTIONS=f"detect_leaks={1 if args.leak_check=='enabled' else 0}:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    def identity():
        if receipt.get("status")!="BUILD_PASS" or sha(receipt_path)!=receipt_hash:
            raise RuntimeError("build receipt absent, failed or changed")
        for name, expected in receipt["source_bindings"].items():
            if sha(ROOT/name)!=expected:
                raise RuntimeError("runtime source differs from binary build: "+name)
        for name, expected in receipt["test_source_bindings"].items():
            if sha(ROOT/name)!=expected:
                raise RuntimeError("compiled native test differs: "+name)
        for name, expected in receipt["executables"].items():
            if sha(build/name)!=expected:
                raise RuntimeError("binary changed: "+name)
        if bindings!={name:sha(ROOT/name) for name in TEST_FILES}:
            raise RuntimeError("test or reference changed during verification")
    identity()
    started=time.monotonic()
    def execute(name, argv):
        log=output/"logs"/(name+".log")
        begin=time.monotonic()
        with log.open("wb") as stream:
            process=subprocess.Popen(list(map(str,argv)), cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                     stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code=process.wait(timeout=150)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait();code=124
        result=dict(suite=name, exit_code=code, elapsed_seconds=round(time.monotonic()-begin,3), log_sha256=sha(log))
        print(f"{name}: {'PASS' if code==0 else 'FAIL'} ({result['elapsed_seconds']}s)", flush=True)
        if code:
            print(log.read_text(errors="replace")[-3000:], flush=True)
        return result
    results=[]
    fixtures=output/"fixtures"
    results.append(execute("prepare_fixtures", [sys.executable, ROOT/"tests/prepare_fixtures.py", build/"qros", fixtures]))
    if results[0]["exit_code"]==0:
        jobs=[("core_native",[build/"qros_tests"]),("pipeline_native",[build/"qros_pipeline_tests"]),
              ("active_authorities",[sys.executable,ROOT/"tests/check_active_authorities.py"]),
              ("pipeline_integration",[sys.executable,ROOT/"tests/test_pipeline_integration.py",build/"qros","--out",output/"integration","--leak-check",args.leak_check])]
        jobs += [(name,[sys.executable,ROOT/("tests/"+name+".py"),build/"qros",fixtures]) for name in SUITES]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            results.extend(pool.map(lambda pair:execute(*pair),jobs))
    identity()
    passed=all(r["exit_code"]==0 for r in results) and len(results)==12
    report=dict(schema="QROS_SOFTWARE_VERIFICATION_V1", status="PASS" if passed else "FAIL", purpose="TEST_ONLY",
                build_receipt_sha256=receipt_hash, source_root_sha256=receipt["source_root_sha256"],
                entrypoint_sha256=receipt["executables"]["qros"], test_and_reference_bindings=bindings, suites=results,
                elapsed_seconds=round(time.monotonic()-started,3), mt5_compiled=False, real_broker_data_replayed=False,
                holdout_opened=False, research_approved=False, leak_check_requested=args.leak_check,
                leak_check_supported_here="NOT_ASSERTED; see sanitizer logs")
    (output/"VERIFICATION_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"status":report["status"],"suites":len(results),"report":str(output/"VERIFICATION_REPORT.json")}),flush=True)
    if not passed:
        raise SystemExit(1)


if __name__=="__main__":
    main()
