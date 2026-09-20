#!/usr/bin/env python3
from __future__ import annotations
import argparse, json

MAX_PROJECTED_STORAGE_BYTES = 9_000_000_000
MAX_PROJECTED_CLASS_A = 900_000
MAX_PROJECTED_CLASS_B = 9_000_000

def main() -> int:
    ap = argparse.ArgumentParser(description="Fail-closed Cloudflare R2 zero-additional-cost guard for QROS carriers.")
    ap.add_argument("--existing-storage-bytes", type=int, required=True)
    ap.add_argument("--planned-storage-bytes", type=int, required=True)
    ap.add_argument("--existing-class-a", type=int, required=True)
    ap.add_argument("--planned-class-a", type=int, required=True)
    ap.add_argument("--existing-class-b", type=int, required=True)
    ap.add_argument("--planned-class-b", type=int, required=True)
    ap.add_argument("--storage-class", required=True)
    args = ap.parse_args()

    vals = {
        "existing_storage_bytes": args.existing_storage_bytes,
        "planned_storage_bytes": args.planned_storage_bytes,
        "existing_class_a": args.existing_class_a,
        "planned_class_a": args.planned_class_a,
        "existing_class_b": args.existing_class_b,
        "planned_class_b": args.planned_class_b,
    }
    if any(v < 0 for v in vals.values()):
        raise SystemExit("FAIL_NEGATIVE_USAGE")

    projected_storage = args.existing_storage_bytes + args.planned_storage_bytes
    projected_a = args.existing_class_a + args.planned_class_a
    projected_b = args.existing_class_b + args.planned_class_b

    receipt = {
        "schema": "QROS_R2_ZERO_COST_GUARD_RECEIPT_1.0",
        "storage_class": args.storage_class,
        "limits": {
            "max_projected_storage_bytes": MAX_PROJECTED_STORAGE_BYTES,
            "max_projected_class_a": MAX_PROJECTED_CLASS_A,
            "max_projected_class_b": MAX_PROJECTED_CLASS_B,
        },
        "projected": {
            "storage_bytes": projected_storage,
            "class_a": projected_a,
            "class_b": projected_b,
        },
    }

    failures = []
    if args.storage_class != "STANDARD":
        failures.append("NON_STANDARD_STORAGE_CLASS")
    if projected_storage > MAX_PROJECTED_STORAGE_BYTES:
        failures.append("PROJECTED_STORAGE_EXCEEDS_ZERO_COST_GUARD")
    if projected_a > MAX_PROJECTED_CLASS_A:
        failures.append("PROJECTED_CLASS_A_EXCEEDS_ZERO_COST_GUARD")
    if projected_b > MAX_PROJECTED_CLASS_B:
        failures.append("PROJECTED_CLASS_B_EXCEEDS_ZERO_COST_GUARD")

    receipt["status"] = "PASS" if not failures else "FAIL"
    receipt["failures"] = failures
    print(json.dumps(receipt, sort_keys=True))
    return 0 if not failures else 2

if __name__ == "__main__":
    raise SystemExit(main())
