#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tarfile
import tempfile
from pathlib import Path
from typing import Iterable

SCHEMA = "QROS_CAS_V2_ARTIFACT_MANIFEST_v1"


def sha256_file(path: Path, chunk: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def iter_files(root: Path) -> Iterable[Path]:
    for p in sorted(root.rglob("*")):
        if p.is_file():
            yield p


def build_bundle(src: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
    with tarfile.open(tmp, "w") as tf:
        if src.is_dir():
            for p in iter_files(src):
                tf.add(p, arcname=p.relative_to(src.parent), recursive=False)
        else:
            tf.add(src, arcname=src.name, recursive=False)
    os.replace(tmp, out)


def manifest_for(bundle: Path, logical_name: str, artifact_class: str, campaign_id: str | None) -> dict:
    return {
        "schema": SCHEMA,
        "logical_name": logical_name,
        "artifact_class": artifact_class,
        "campaign_id": campaign_id,
        "bundle_name": bundle.name,
        "bytes": bundle.stat().st_size,
        "sha256": sha256_file(bundle),
        "locator": {
            "backend": "DROPBOX",
            "path": None,
            "file_id": None,
        },
        "state": "LOCAL_PACKED_NOT_REMOTE_CONFIRMED",
        "rules": {
            "remote_write_required_before_local_eviction": True,
            "raw_sha256_required_on_rehydration": True,
            "missing_or_mismatched_remote_object": "FAIL_CLOSED_AND_REMATERIALIZE_IF_EXACT_POLICY_ALLOWS",
            "scientific_state_must_not_change_on_storage_failure": True,
        },
    }


def cmd_pack(a: argparse.Namespace) -> None:
    src = Path(a.source).resolve()
    out = Path(a.output).resolve()
    if not src.exists():
        raise SystemExit(f"source_not_found:{src}")
    build_bundle(src, out)
    m = manifest_for(out, a.logical_name, a.artifact_class, a.campaign_id)
    mp = Path(a.manifest).resolve()
    mp.parent.mkdir(parents=True, exist_ok=True)
    tmp = mp.with_suffix(mp.suffix + ".tmp")
    tmp.write_text(json.dumps(m, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, mp)
    print(json.dumps({"status": "PACKED", "bundle": str(out), "manifest": str(mp), "bytes": m["bytes"], "sha256": m["sha256"]}, sort_keys=True))


def cmd_bind(a: argparse.Namespace) -> None:
    mp = Path(a.manifest).resolve()
    m = json.loads(mp.read_text(encoding="utf-8"))
    if m.get("schema") != SCHEMA:
        raise SystemExit("manifest_schema_mismatch")
    m["locator"] = {"backend": "DROPBOX", "path": a.dropbox_path, "file_id": a.file_id}
    m["state"] = "REMOTE_WRITE_REPORTED_PENDING_READBACK"
    tmp = mp.with_suffix(mp.suffix + ".tmp")
    tmp.write_text(json.dumps(m, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, mp)
    print(json.dumps({"status": m["state"], "manifest": str(mp), "dropbox_path": a.dropbox_path, "file_id": a.file_id}, sort_keys=True))


def cmd_verify(a: argparse.Namespace) -> None:
    mp = Path(a.manifest).resolve()
    candidate = Path(a.file).resolve()
    m = json.loads(mp.read_text(encoding="utf-8"))
    if m.get("schema") != SCHEMA:
        raise SystemExit("manifest_schema_mismatch")
    if not candidate.exists():
        raise SystemExit("candidate_missing")
    got_size = candidate.stat().st_size
    got_sha = sha256_file(candidate)
    exp_size = int(m["bytes"])
    exp_sha = m["sha256"]
    ok = got_size == exp_size and got_sha == exp_sha
    print(json.dumps({"status": "PASS" if ok else "FAIL_CLOSED", "expected_bytes": exp_size, "observed_bytes": got_size, "expected_sha256": exp_sha, "observed_sha256": got_sha}, sort_keys=True))
    if not ok:
        raise SystemExit(2)


def main() -> None:
    p = argparse.ArgumentParser(description="QROS CAS V2 deterministic pack/bind/verify helper")
    sp = p.add_subparsers(dest="cmd", required=True)

    q = sp.add_parser("pack")
    q.add_argument("--source", required=True)
    q.add_argument("--output", required=True)
    q.add_argument("--manifest", required=True)
    q.add_argument("--logical-name", required=True)
    q.add_argument("--artifact-class", required=True)
    q.add_argument("--campaign-id")
    q.set_defaults(func=cmd_pack)

    q = sp.add_parser("bind")
    q.add_argument("--manifest", required=True)
    q.add_argument("--dropbox-path", required=True)
    q.add_argument("--file-id", required=True)
    q.set_defaults(func=cmd_bind)

    q = sp.add_parser("verify")
    q.add_argument("--manifest", required=True)
    q.add_argument("--file", required=True)
    q.set_defaults(func=cmd_verify)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
