#!/usr/bin/env python3
"""Fail-closed external CI preflight. Produces *software-only* evidence.

CI source pinning and byte oracle are independent of evidence_guard.py's logic.
A successful GitHub job does NOT attest model snapshots or custodian independence.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SOURCE = HERE / "CORE_SOURCE.tar.gz.b64"
PLAN = HERE / "EXTERNAL_EVIDENCE_PLAN_v1.json"
CHECKPOINT = HERE / "DURABLE_CHECKPOINT.json"
INTENT = HERE / "RUN_EXTERNAL_INTENT.json"
PLAN_BLOB_SHA1 = "990bc6809e98184d83f07b6856bd37f2887b981f"
ALLOWED_MEMBERS = {"PREREGISTRATION.json", "evidence_guard.py", "test_evidence_guard.py"}


def require(ok, label):
    if not ok:
        raise RuntimeError("FAIL_CLOSED:" + label)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def main():
    require(os.getenv("GITHUB_ACTIONS") == "true", "NOT_GITHUB_ACTIONS")
    require(os.getenv("RUNNER_ENVIRONMENT") == "github-hosted", "NOT_GITHUB_HOSTED")
    require(os.getenv("RUNNER_OS") == "Linux", "NOT_LINUX")
    commit = os.getenv("GITHUB_SHA", "")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    require(bool(re.fullmatch("[0-9a-f]{40}", commit)), "COMMIT_ID")
    require(run_id.isdigit(), "RUN_ID")

    raw_plan = PLAN.read_bytes()
    require(git_blob(raw_plan) == PLAN_BLOB_SHA1, "PLAN_DRIFT")
    plan = json.loads(raw_plan)
    checkpoint = json.loads(CHECKPOINT.read_bytes())
    intent = json.loads(INTENT.read_bytes())
    require(intent.get("schema") == "QROS_RSI_G1_EXTERNAL_RUN_INTENT_1.0", "INTENT_SCHEMA")
    require(intent.get("one_off") is True, "INTENT_NOT_ONE_OFF")
    require(intent.get("operator_confirmed_hard_zero_paid_spend") is True, "COST_GUARD_UNCONFIRMED")
    require(intent.get("plan_git_blob_sha1") == PLAN_BLOB_SHA1, "INTENT_PLAN_DRIFT")
    require(intent.get("frozen_source_git_blob_sha1") == checkpoint["immutable_source"]["git_blob_sha1"], "INTENT_SOURCE_DRIFT")
    require(intent.get("runner_script_git_blob_sha1") == git_blob(Path(__file__).read_bytes()), "RUNNER_SCRIPT_DRIFT")
    require(plan["decision"] == "E1_WORKFLOW_PREP_ONLY_NO_AUTOMATIC_BILLABLE_RUN", "PLAN_CHANGED")
    require(checkpoint["improvement"]["status"] == "RESEARCH_CANDIDATE", "G1_PROMOTION_STATE_DRIFT")

    original = SOURCE.read_bytes()
    require(git_blob(original) == checkpoint["immutable_source"]["git_blob_sha1"], "GIT_SOURCE_DRIFT")
    require(original.endswith(b"\n") and original.count(b"\n") == 1, "SOURCE_ENCODING")
    encoded = original[:-1]
    require(digest(encoded) == checkpoint["immutable_source"]["encoded_payload_sha256_without_final_newline"], "B64_PAYLOAD_DRIFT")
    packed = base64.b64decode(encoded, validate=True)
    require(digest(packed) == checkpoint["immutable_source"]["decoded_tar_gz_sha256"], "TAR_GZ_DRIFT")

    with tempfile.TemporaryDirectory() as temp:
        dest = Path(temp)
        with tarfile.open(fileobj=io.BytesIO(packed), mode="r:gz") as archive:
            entries = archive.getmembers()
            require({x.name for x in entries} == ALLOWED_MEMBERS and len(entries) == 3, "TAR_MEMBER_SET")
            require(all(x.isfile() and x.name == Path(x.name).name for x in entries), "TAR_UNSAFE_PATH")
            for member in entries:
                payload = archive.extractfile(member).read()
                expected = {
                    "PREREGISTRATION.json": checkpoint["immutable_source"]["preregistration_sha256"],
                    "evidence_guard.py": checkpoint["immutable_source"]["code_sha256"],
                    "test_evidence_guard.py": checkpoint["immutable_source"]["test_sha256"],
                }[member.name]
                require(digest(payload) == expected, "MEMBER_HASH_" + member.name)
                (dest / member.name).write_bytes(payload)

        prereg = json.loads((dest / "PREREGISTRATION.json").read_bytes())
        require(prereg["candidate_id"] == checkpoint["improvement"]["id"], "CANDIDATE_IDENTITY")
        require(len(prereg["frozen_tests"]) == 14, "PREREG_CASE_COUNT")
        # Execute unchanged archived tests; never generate replacement tests or re-tune parameters.
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", "test_evidence_guard"],
            cwd=dest, capture_output=True, text=True, timeout=170,
            env={**os.environ, "PYTHONPATH": str(dest)},
        )
        log = proc.stdout + "\n---stderr---\n" + proc.stderr
        require(proc.returncode == 0, "UNIT_TESTS_FAILED")
        require(bool(re.search(r"Ran 14 tests in", log)), "NOT_14_TESTS")
        require("OK" in log and "FAILED" not in log and "(skipped=" not in log, "TEST_RESULT_BAD")

        receipt = {
            "schema": "QROS_RSI_G1_GITHUB_EXTERNAL_SYNTHETIC_RUN_RECEIPT_1.0",
            "scope": "EXTERNAL_HOSTED_SOFTWARE_RERUN_ONLY",
            "not_proof_of": [
                "provider_model_snapshot", "actual_model_run", "matched_system_superiority",
                "independent_custodian", "fresh_sealed_corpus", "scientific_promotion"
            ],
            "repository": os.getenv("GITHUB_REPOSITORY"),
            "git_commit": commit,
            "github_run_id": run_id,
            "github_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
            "github_run_url": "https://github.com/" + os.getenv("GITHUB_REPOSITORY", "") + "/actions/runs/" + run_id,
            "runner_environment": os.getenv("RUNNER_ENVIRONMENT"),
            "runner_os": os.getenv("RUNNER_OS"),
            "python_version": sys.version.split()[0],
            "plan_git_blob_sha1": PLAN_BLOB_SHA1,
            "g1_source_git_blob_sha1": git_blob(original),
            "frozen_prereg_sha256": digest((dest / "PREREGISTRATION.json").read_bytes()),
            "frozen_code_sha256": digest((dest / "evidence_guard.py").read_bytes()),
            "frozen_tests_sha256": digest((dest / "test_evidence_guard.py").read_bytes()),
            "test_log_sha256": digest(log.encode()),
            "tests_run": 14, "tests_failed": 0,
            "scientific_authority_modified": False,
            "promotion_allowed": False,
        }
        (HERE / "EXTERNAL_RUN_RECEIPT.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        (HERE / "EXTERNAL_TEST_LOG.txt").write_text(log, encoding="utf-8")
        print("QROS_G1_EXTERNAL_SOFTWARE_RERUN=PASS_14_OF_14")
        print(json.dumps({k: receipt[k] for k in ("git_commit", "github_run_id", "test_log_sha256", "promotion_allowed")}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print("EXTERNAL_EVIDENCE_FAIL_CLOSED:" + str(exc), file=sys.stderr)
        sys.exit(1)
