#!/usr/bin/env python3
"""Generate declared SYNTHETIC fixtures missing from the recovered v0.4 archive.

These are newly generated test inputs. No original receipts, real tick carriers,
broker evidence or scientific checkpoint is reconstructed by this adapter.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = data.encode() if isinstance(data, str) else data
    if path.exists() and path.read_bytes() != encoded:
        raise RuntimeError(f"fixture output conflict: {path}")
    path.write_bytes(encoded)


def prepare(binary, root):
    source = root/"examples/custody_v1/source"
    data = [b"alpha-part-001\n", b"beta-part-002-synthetic".ljust(29,b".")+b"\n", b"gamma-part-003\n"]
    assert sum(map(len, data)) == 60
    parts = []
    for i, raw in enumerate(data, 1):
        p = source/f"SYNTH_SOURCE.part{i:02d}.bin"
        write(p, raw)
        parts.append(f"part={i},{p.name},{len(raw)},{sha(p)}")
    decoded = source/"SYNTH_SOURCE.decoded.bin"
    write(decoded, b"".join(data))
    profile = source.parent/"profile.custody"
    write(profile, "\n".join(["QROS_SOURCE_CUSTODY_PROFILE_V1", "profile_id=SYNTH_CUSTODY_V1",
        "source_id=SYNTH_SOURCE_001", "source_class=SYNTHETIC_MULTIPART", "namespace_prefix=SYNTH_SOURCE.",
        "parts_count=3", "total_bytes=60", *parts, "decoded_required=1", "decoded_name="+decoded.name,
        "decoded_bytes=60", "decoded_sha256="+sha(decoded), "decoder_id=QROS_CONCAT_V1", "historical_lineage_status=TEST_ONLY"])+"\n")
    subprocess.run([str(binary), "source-custody", str(profile), str(source), str(source.parent/"custody_test.receipt")],
                   check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=30)
    root_q = root/"examples/qdata_v1"
    ticks = root_q/"ticks.csv"; sessions = root_q/"sessions.csv"
    write(ticks, "seq,ts_ns,session_day,bid_u,ask_u\n1,1000000000,20260827,1000,1010\n2,1000000001,20260827,1005,1015\n3,1000000001,20260827,1010,1020\n4,1000000002,20260827,1021,1031\n5,1000000003,20260827,1030,1040\n6,1000000004,20260827,1020,1030\n")
    write(sessions, "session_day,open_seq,close_seq,open_ts_ns,close_ts_ns,utc_offset_seconds\n20260827,1,6,1000000000,1000000004,-14400\n")
    timezone = root_q/"timezone_evidence.txt"; provenance = root_q/"source_evidence.txt"
    write(timezone, "QROS_TIMEZONE_EVIDENCE_V1\nauthority_id=SYNTHETIC_QDATA_V1\ntimezone_name=TEST_FIXED_MINUS_04\nmethod=SYNTHETIC_FIXED_OFFSET\ncoverage_first_day=20260827\ncoverage_last_day=20260827\nsessions_sha256="+sha(sessions)+"\nobserved_offset_transitions=0\nmax_offset_jump_seconds=0\nstatus=TEST_ONLY\n")
    write(provenance, "QROS_SOURCE_EVIDENCE_V1\nauthority_id=SYNTHETIC_QDATA_V1\nsource_kind=SYNTHETIC_TEST\nsource_id=SYNTH_QDATA_FIXTURE\nmethod=SYNTHETIC_GENERATOR\ndataset_sha256="+sha(ticks)+"\nsessions_sha256="+sha(sessions)+"\nstatus=TEST_ONLY\n")
    manifest = root_q/"manifest.qdata"
    write(manifest, "QROS_QDATA_MANIFEST_V1\nauthority_id=SYNTHETIC_QDATA_V1\nsymbol=NQX_TEST\ndataset_sha256="+sha(ticks)+"\nsessions_sha256="+sha(sessions)+"\nschema=TICKS_CSV_V1\nexpected_rows=6\nfirst_seq=1\nlast_seq=6\nfirst_ts_ns=1000000000\nlast_ts_ns=1000000004\nprice_decimals=1\npoint_size_u=1\ntick_size_u=1\ntimezone_name=TEST_FIXED_MINUS_04\ntimezone_status=TEST_ONLY\ntimezone_evidence_sha256="+sha(timezone)+"\nsource_kind=SYNTHETIC_TEST\nsource_id=SYNTH_QDATA_FIXTURE\nsource_evidence_sha256="+sha(provenance)+"\npurpose=TEST_ONLY\nsession_policy_id=ONE_SESSION\nmax_zero_spread_ppm=0\nallow_nonpositive_prices=0\n")
    contract = subprocess.check_output([str(binary), "contracts"], text=True, timeout=10)
    contracts = dict(line.split("=",1) for line in contract.splitlines() if "=" in line)
    write(root_q/"buy_tp_v2.qros", "QROS_INTENT_V2\nstrategy_id=SYNTH_BUY_TP\ndata_sha256="+sha(ticks)+"\nside=BUY\nsignal_seq=1\nsignal_ts_ns=1000000000\nsignal_session_day=20260827\nsession_close_seq=6\nstop_distance_u=20\ntarget_distance_u=10\nqdata_manifest_sha256="+sha(manifest)+"\nsessions_sha256="+sha(sessions)+"\nevent_contract_sha256="+contracts["event_contract_sha256"]+"\nexecution_policy_sha256="+contracts["execution_policy_sha256"]+"\n")
    write(root/"SYNTHETIC_FIXTURES_ONLY.txt", "Generated software fixtures. Not recovered originals. No broker provenance or scientific validation is asserted.\n")
    print("SYNTHETIC_FIXTURES_PREPARED", flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("root", type=Path)
    args=parser.parse_args()
    prepare(args.binary.resolve(), args.root.resolve())
