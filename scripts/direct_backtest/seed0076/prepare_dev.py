#!/usr/bin/env python3
"""Recover only the already frozen XAU 2018-2019 DEV stream; no shard data."""
import hashlib, json, os, zipfile
from pathlib import Path
R=Path('/mnt/data')
O=R/'seed0076_direct_dev'/'XAUUSD_DEV_PACKED17_151382388.bin'
EXPECTED='3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53'
CHUNK=8*1024*1024
if O.exists():
    h=hashlib.sha256()
    with O.open('rb') as f:
        for b in iter(lambda:f.read(CHUNK),b''):h.update(b)
    if O.stat().st_size!=2573500596 or h.hexdigest()!=EXPECTED:raise SystemExit('EXISTING_DEV_HASH_MISMATCH')
    print('DEV_REUSE_PASS',O.stat().st_size,h.hexdigest());raise SystemExit(0)
tmp=O.with_suffix('.partial')
h=hashlib.sha256();tot=0
try:
 with tmp.open('wb') as output:
  for part in range(1,9):
   zp=R/f'QROS_XAU_FULL_HISTORY_v2_part{part:03d}-of-035.zip'
   with zipfile.ZipFile(zp) as z:
    member=next((i for i in z.infolist() if i.filename.startswith('XAU_PACKED17_rows_')),None)
    if not member or member.file_size!=340000000:raise RuntimeError(f'BAD_ZIP_MEMBER_{part}')
    needed=340000000 if part<8 else 11382388*17
    with z.open(member) as src:
     left=needed
     while left:
      b=src.read(min(left,CHUNK))
      if not b:raise RuntimeError(f'EARLY_EOF_{part}')
      output.write(b);h.update(b);tot+=len(b);left-=len(b)
   print('DEV_PART_DONE',part,tot,flush=True)
  output.flush();os.fsync(output.fileno())
 if tot!=2573500596 or h.hexdigest()!=EXPECTED:raise RuntimeError('FINAL_DEV_IDENTITY_MISMATCH')
 os.replace(tmp,O)
 print('DEV_EXACT_PASS',tot,tot//17,h.hexdigest(),flush=True)
except BaseException:
 tmp.unlink(missing_ok=True)
 raise
