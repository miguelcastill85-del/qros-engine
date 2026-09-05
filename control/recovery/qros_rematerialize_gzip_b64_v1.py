#!/usr/bin/env python3
from __future__ import annotations
import argparse,base64,gzip,hashlib
from pathlib import Path

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--carrier',type=Path,required=True);p.add_argument('--carrier-sha256',required=True);p.add_argument('--raw-sha256',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 carrier=a.carrier.read_bytes()
 if sha(carrier)!=a.carrier_sha256:raise SystemExit('CARRIER_SHA_MISMATCH')
 raw=gzip.decompress(base64.b64decode(carrier,validate=True))
 if sha(raw)!=a.raw_sha256:raise SystemExit('RAW_SHA_MISMATCH')
 a.out.parent.mkdir(parents=True,exist_ok=True);tmp=a.out.with_name(a.out.name+'.tmp');tmp.write_bytes(raw);tmp.replace(a.out)
 print(f'PASS {len(raw)} {sha(raw)} {a.out}')
if __name__=='__main__':main()
