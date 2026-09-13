#!/usr/bin/env python3
"""Build and verify a deterministic G32 recovery packet.

The ZIP is a byte backup for cross-chat restoration.  It intentionally omits
its own ZIP hash and the later remote-readback receipt, avoiding circular
identity.  The internal manifest authenticates every scientific payload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath


MANIFEST_NAME = "G32_RECOVERY_PACKET_MANIFEST_V1.json"
SCHEMA = "QROS_G32_RECOVERY_PACKET_MANIFEST_V1"
EXCLUDED_NAMES = {MANIFEST_NAME, "QROS_G32_RECOVERY_PACKET_V1.zip"}


def canonical_bytes(value: object) -> bytes:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return unicodedata.normalize("NFC", text).encode("utf-8") + b"\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def eligible_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if "__pycache__" in rel.parts or path.suffix == ".pyc" or path.name in EXCLUDED_NAMES:
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def build_manifest(root: Path) -> dict:
    records = []
    for path in eligible_files(root):
        rel = path.relative_to(root).as_posix()
        records.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    required = {
        "HYPOTHESIS_PAYLOAD": "research/public_hypotheses/QROS_1000_ESTRATEGIAS_PUBLICAS_XAU_NQX_v1.csv",
        "TRIAGE_LEDGER": "research/public_hypotheses/QROS_1000_HYPOTHESIS_CAUSAL_TRIAGE_V1.jsonl",
        "SOURCE_AND_COLLISION_AUDIT": "control/G32_HYPOTHESIS_SELECTION_RECEIPT_V1.json",
        "PREREGISTRATION": "control/PREREG_G32_MAMA_FAMA_ADAPTIVE_PHASE_CROSS_V1.json",
        "ONTOLOGY_PAYLOAD": "control/G32_UNIVERSE_ONTOLOGY_V2.json",
        "ENUMERATION_PAYLOAD": "control/G32_EXACT_ENUMERATION_PARITY_RECEIPT_V1.json",
        "DEPENDENCY_DAG": "control/G32_PREDEVELOPMENT_STATE_V1.json",
        "NEXT_STAGE_PACKET": "control/G32_PREDEVELOPMENT_STATE_V1.json",
        "RESTORE_PROGRAM": "research/g32/qros_g32_recovery_packet.py",
    }
    available = {x["path"] for x in records}
    missing = sorted(set(required.values()) - available)
    if missing:
        raise ValueError(f"mandatory recovery roles missing: {missing}")
    return {
        "schema": SCHEMA,
        "status": "CANONICALIZED_NO_RESULTS",
        "campaign": "QROS_G32_PUBLIC_MAMA_FAMA_ADAPTIVE_PHASE_CROSS_v1",
        "canonical_order": "UTF8_NFC_PATH_ASCENDING",
        "file_count": len(records),
        "files": records,
        "mandatory_roles": required,
        "guards": {
            "market_data_in_packet": False,
            "pnl_in_packet": False,
            "holdout_in_packet": False,
            "runtime_paths_are_authority": False,
        },
    }


def build(root: Path, output: Path) -> dict:
    manifest = build_manifest(root)
    manifest_bytes = canonical_bytes(manifest)
    manifest_path = root / MANIFEST_NAME
    manifest_path.write_bytes(manifest_bytes)

    fixed = (1980, 1, 1, 0, 0, 0)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=True) as archive:
        for path in eligible_files(root) + [manifest_path]:
            rel = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(rel, fixed)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return {
        "packet": str(output),
        "bytes": output.stat().st_size,
        "sha256": sha256_file(output),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "files": manifest["file_count"],
    }


def safe_member(name: str) -> bool:
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and ".." not in p.parts and "" not in p.parts


def verify(packet: Path, run_tests: bool) -> dict:
    with zipfile.ZipFile(packet, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP member")
        if not all(safe_member(name) for name in names):
            raise ValueError("unsafe ZIP path")
        corrupt = archive.testzip()
        if corrupt:
            raise ValueError(f"CRC failure: {corrupt}")
        manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        if manifest.get("schema") != SCHEMA:
            raise ValueError("unexpected recovery manifest schema")
        expected_names = {x["path"] for x in manifest["files"]} | {MANIFEST_NAME}
        if set(names) != expected_names:
            raise ValueError("ZIP membership differs from manifest")
        for record in manifest["files"]:
            data = archive.read(record["path"])
            if len(data) != record["bytes"] or sha256_bytes(data) != record["sha256"]:
                raise ValueError(f"payload mismatch: {record['path']}")

        tests = {"executed": 0, "passed": 0, "status": "NOT_REQUESTED"}
        if run_tests:
            with tempfile.TemporaryDirectory(prefix="qros_g32_restore_") as temp:
                restore_root = Path(temp) / "restored"
                restore_root.mkdir()
                archive.extractall(restore_root)
                result = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", str(restore_root / "tests"), "-p", "test_*.py", "-v"],
                    cwd=restore_root,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                if result.returncode:
                    raise RuntimeError("restored regression suite failed\n" + result.stdout)
                marker = "Ran "
                count = 0
                for line in result.stdout.splitlines():
                    if line.startswith(marker) and " tests" in line:
                        count = int(line.split()[1])
                tests = {"executed": count, "passed": count, "status": "PASS"}

    return {
        "schema": "QROS_G32_LOCAL_RESTORE_CANARY_V1",
        "status": "RESTORE_PASS",
        "packet_bytes": packet.stat().st_size,
        "packet_sha256": sha256_file(packet),
        "zip_crc": "PASS",
        "safe_paths": "PASS",
        "membership": "PASS",
        "payload_hashes": f"PASS_{manifest['file_count']}_OF_{manifest['file_count']}",
        "tests": tests,
        "market_data_read": False,
        "pnl_read": False,
        "holdout_opened": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--root", type=Path, required=True)
    build_parser.add_argument("--output", type=Path, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--packet", type=Path, required=True)
    verify_parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    if args.command == "build":
        result = build(args.root.resolve(), args.output.resolve())
    else:
        result = verify(args.packet.resolve(), args.run_tests)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
