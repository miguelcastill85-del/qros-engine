#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json

SCHEMA = "QROS_RUNNER_SOURCE_DURABILITY_CANARY_v1"
FIXTURE = b"QROS|RUNNER|SOURCE|DURABILITY|CANARY|v1\n" + bytes(range(256)) * 16


def canonical_receipt() -> bytes:
    payload = {
        "fixture_bytes": len(FIXTURE),
        "fixture_sha256": hashlib.sha256(FIXTURE).hexdigest(),
        "schema": SCHEMA,
        "status": "PASS",
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"


if __name__ == "__main__":
    import sys
    sys.stdout.buffer.write(canonical_receipt())
