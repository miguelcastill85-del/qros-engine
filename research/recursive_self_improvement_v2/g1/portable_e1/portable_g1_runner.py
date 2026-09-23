#!/usr/bin/env python3
"""Offline rerun of frozen QROS RSI G1 synthetic tests.

This confirms byte identity and software behavior on an independently-operated
computer if the operator actually runs it there. A self-reported receipt does
NOT attest model provenance, organizational independence or a scientific gain.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tarfile
import tempfile
import uuid
import zipfile

ZIP_SHA256 = "499864661e001bce9bea15fd003e59c9419777e864ef2997de2b47500abd1d5f"
TAR_SHA256 = "4092a9f5a85b587b2040ca8e8005a08ebe22beb42649052ff31cc891b2c6fc9f"
PINNED = {
    "PREREGISTRATION.json": "90bb79a3f64e2aee3683a009198001849b288afd098c89e3f201afd87471bae3",
    "evidence_guard.py": "62b7a3417359d86c7d4fa781dfeb25a6969d00354c0a42bb0b1abeea0a28a76f",
    "test_evidence_guard.py": "9163c046a8cf30b691952123181e45437c5249989e054c87031f21d7416c2855",
}
PACKAGE_PREFIX = "QROS_RSI_v2_G1/"
REQUIRED_PACKAGE_ENTRIES = {
    "PREREGISTRATION.json", "evidence_guard.py", "test_evidence_guard.py",
    "UNIT_TESTS.log", "RESULTS.json", "MANIFEST.json", "META_AUDIT.md",
    "CORE_SOURCE.tar.gz", "CORE_SOURCE.tar.gz.b64", "SOURCE_BUNDLE.tar.gz",
}


def need(cond, code):
    if not cond:
        raise ValueError("FAIL_CLOSED:" + code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def extract_untrusted_bytes(package_bytes):
    with zipfile.ZipFile(io.BytesIO(package_bytes)) as z:
        names = z.namelist()
        need(len(names) == 10 and set(names) == {PACKAGE_PREFIX + n for n in REQUIRED_PACKAGE_ENTRIES}, "PACKAGE_MEMBERS")
        need(z.testzip() is None, "ZIP_CRC")
        raw = {n: z.read(PACKAGE_PREFIX + n) for n in REQUIRED_PACKAGE_ENTRIES}
    need(sha(raw["CORE_SOURCE.tar.gz"]) == TAR_SHA256, "CORE_TAR_DRIFT")
    with tarfile.open(fileobj=io.BytesIO(raw["CORE_SOURCE.tar.gz"]), mode="r:gz") as tar:
        members = tar.getmembers()
        need(len(members) == 3 and {m.name for m in members} == set(PINNED), "CORE_TAR_MEMBERS")
        need(all(m.isfile() and Path(m.name).name == m.name for m in members), "UNSAFE_TAR_PATH")
        for m in members:
            packed_value = tar.extractfile(m).read()
            need(sha(packed_value) == PINNED[m.name], "PIN_DRIFT_" + m.name)
            need(raw[m.name] == packed_value, "ZIP_CORE_MISMATCH_" + m.name)
    prereg = json.loads(raw["PREREGISTRATION.json"])
    need(prereg["candidate_id"] == "RSI-G1-E_CONTRACT-SIGNED_OBSERVATION_GUARD", "GENEALOGY")
    need(len(prereg["frozen_tests"]) == 14, "TEST_PRE_REG_COUNT")
    return raw


def run(package_path: Path, out_dir: Path):
    need(package_path.is_file(), "PACKAGE_NOT_FOUND")
    orig = package_path.read_bytes()
    need(sha(orig) == ZIP_SHA256, "PACKAGE_SHA256")
    raw = extract_untrusted_bytes(orig)
    try:
        installed = importlib.metadata.version("cryptography")
    except importlib.metadata.PackageNotFoundError as e:
        raise ValueError("FAIL_CLOSED:MISSING_CRYPTOGRAPHY_46_0_4_NO_AUTO_INSTALL") from e
    need(installed == "46.0.4", "CRYPTOGRAPHY_VERSION_NOT_PINNED")

    with tempfile.TemporaryDirectory(prefix="qros-g1-external-") as t:
        work = Path(t)
        for name in PINNED:
            (work / name).write_bytes(raw[name])
        p = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", "test_evidence_guard"],
            cwd=work, capture_output=True, text=True, timeout=180,
            env={**os.environ, "PYTHONPATH": str(work)},
        )
        log = p.stdout + "\n--- STDERR ---\n" + p.stderr
        need(p.returncode == 0, "TEST_EXECUTION_FAILED")
        need(bool(re.search(r"Ran 14 tests in", log)), "TEST_COUNT")
        need("\nOK\n" in log and "FAILED" not in log and "skipped=" not in log, "TESTS_NOT_ALL_PASS")

    now = datetime.now(timezone.utc)
    script_path = Path(__file__).resolve()
    receipt = {
        "schema": "QROS_G1_PORTABLE_OFFCHAT_EVIDENCE_RECEIPT_1.0",
        "run_id": str(uuid.uuid4()),
        "run_utc": now.isoformat(),
        "original_zip_sha256": ZIP_SHA256,
        "original_tar_sha256": TAR_SHA256,
        "runner_script_sha256": sha(script_path.read_bytes()),
        "frozen_member_sha256": dict(sorted(PINNED.items())),
        "test_log_sha256": sha(log.encode()),
        "frozen_synthetic_tests_run": 14,
        "frozen_synthetic_tests_failed": 0,
        "python_version": platform.python_version(),
        "cryptography_version": installed,
        "os_family": platform.system(),
        "machine_architecture": platform.machine(),
        "execution_context": (
            "OPERATOR_WINDOWS_HOST_SELF_REPORTED_NOT_EXTERNALLY_ATTESTED"
            if os.name == "nt" else "LOCAL_OR_UNKNOWN_NOT_EXTERNALLY_ATTESTED"
        ),
        "independent_evaluator": False,
        "independent_custodian": False,
        "actual_provider_snapshot_verified": False,
        "model_runs_performed": 0,
        "model_improvement_demonstrated": False,
        "scientific_promotion_allowed": False,
        "github_hosted_evidence": False,
        "independently_auditable_test_source": True,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_bytes = (json.dumps(receipt, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    manifest = "RECEIPT_JSON_SHA256 " + sha(receipt_bytes) + "\nTEST_LOG_SHA256 " + sha(log.encode()) + "\n"
    final_name = "QROS_G1_PC_RECEIPT_" + now.strftime("%Y%m%dT%H%M%SZ") + "_" + receipt["run_id"][:8] + ".zip"
    with tempfile.NamedTemporaryFile(prefix=".qros-g1-", suffix=".zip", dir=out_dir, delete=False) as tmp:
        staged = Path(tmp.name)
    try:
        with zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            z.writestr("E1_PORTABLE_RECEIPT.json", receipt_bytes)
            z.writestr("E1_FROZEN_UNIT_TESTS.log", log)
            z.writestr("E1_MANIFEST_SHA256.txt", manifest)
        os.replace(staged, out_dir / final_name)
    finally:
        if staged.exists():
            staged.unlink()
    print("PASS_14_OF_14_SYNTHETIC; NO_MODEL_EFFICACY_CLAIM")
    print("EXTERNAL_RECEIPT: " + str(out_dir / final_name))
    return receipt


def main():
    a = argparse.ArgumentParser(description="Offline G1 frozen test rerun; no network/no paid services")
    here = Path(__file__).resolve().parent
    a.add_argument("--package", type=Path, default=here / "QROS_RSI_v2_G1_EVIDENCE_PACKAGE.zip")
    a.add_argument("--out-dir", type=Path, default=here / "EVIDENCE_OUTPUT")
    args = a.parse_args()
    try:
        run(args.package, args.out_dir)
    except (ValueError, OSError, subprocess.TimeoutExpired, zipfile.BadZipFile, tarfile.TarError, KeyError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
