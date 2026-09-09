"""Read-only CLI. Emits inspection evidence; no dispatch or scientific writes."""
import argparse
import json
from pathlib import Path

from .runtime import ContractError, Snapshot, authority_receipt, inspect_active_queue, observe_authority, inspect_control_bootstrap


def run(repo_root: Path, manifest_blob: str) -> dict:
    observation = observe_authority(Snapshot(repo_root), manifest_blob)
    return {"schema": "QRCEL_SHADOW_INSPECTION_V1", "status": "PASS",
            "authority": authority_receipt(observation), "queue": inspect_active_queue(observation),
            "control_bootstrap": inspect_control_bootstrap(Snapshot(repo_root), manifest_blob),
            "scientific_writes": 0, "economic_reads": 0, "dispatch_authorized": False,
            "qrcel_promoted": False, "parity_claim": "INSUFFICIENT_EVIDENCE"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--manifest-blob", required=True,
                        help="Expected blob from authenticated pinned commit; never self-derived from untrusted input")
    args = parser.parse_args()
    try:
        result = run(args.repo_root, args.manifest_blob)
    except ContractError as exc:
        result = {"schema": "QRCEL_SHADOW_INSPECTION_V1", "status": "FAIL", "error": exc.code,
                  "detail": str(exc), "dispatch_authorized": False,
                  "scientific_writes": 0, "economic_reads": 0}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
