#!/usr/bin/env python3
from pathlib import Path
import re
import hashlib
import sys

root = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else Path(__file__).resolve().parents[1]
profiles = root / "profiles"
active = [p for p in profiles.iterdir() if p.is_file()]
errors = []
index_path = profiles / "ACTIVE_DATA_AUTHORITIES_v0_4.txt"
sidecar = profiles / "ACTIVE_DATA_AUTHORITIES_v0_4.sha256"
index_names = set()
for line in index_path.read_text().splitlines():
    match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_]+\.authority)", line)
    if not match:
        errors.append("invalid active authority index record")
        continue
    expected, name = match.groups()
    if name in index_names:
        errors.append("duplicate authority index record")
    index_names.add(name)
    target = profiles / name
    if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        errors.append(f"authority index hash mismatch: {name}")
if index_names != {"NQX_FULL_HISTORY_ZIP_v2.authority", "XAU_FULL_HISTORY_ZIP_v2.authority"}:
    errors.append("active authority set mismatch")
expected_sidecar = hashlib.sha256(index_path.read_bytes()).hexdigest() + "  ACTIVE_DATA_AUTHORITIES_v0_4.txt\n"
if sidecar.read_text() != expected_sidecar:
    errors.append("active authority index sidecar mismatch")
for p in active:
    text = p.read_text(encoding="utf-8", errors="strict")
    # Legacy extension or former RAR source stem in an active authority is a hard failure.
    if re.search(r"(?i)\.rar(?:\b|$)", text) or "NDX_201801251306_202607270911" in text:
        errors.append(f"legacy RAR reference in active profile: {p.name}")

required = {
    "NQX_FULL_HISTORY_ZIP_v2.authority": ["parts_count=28", "carrier_sha256=6da9cf67310c2c6689bd82c20882e5e8b652196147a458be58796e5103a22608"],
    "XAU_FULL_HISTORY_ZIP_v2.authority": ["parts_count=35", "carrier_sha256=c386dc3028943f7462f6091d1417a9733237be5e25b07aa5732c111ce11f92e4"],
}
for name, needles in required.items():
    p = profiles / name
    if not p.is_file():
        errors.append(f"missing active authority: {name}")
        continue
    text = p.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            errors.append(f"{name}: missing {needle}")

if errors:
    raise SystemExit("FAIL\n" + "\n".join(errors))
print("PASS active_authorities=2 legacy_rar_active=0")
