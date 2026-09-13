#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, sys, tempfile, zipfile
from pathlib import Path

CHUNK = 8 * 1024 * 1024

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(CHUNK), b''): h.update(b)
    return h.hexdigest()

def fail(msg: str) -> None:
    raise RuntimeError(msg)

def stream_asset(asset: str, spec: dict, source_dir: Path, out_dir: Path, record_bytes: int) -> dict:
    expected_bytes=int(spec['target_bytes']); expected_records=int(spec['target_records'])
    if expected_bytes != expected_records * record_bytes: fail(f'{asset}: target byte/record mismatch')
    if sum(int(p['take_records']) for p in spec['parts']) != expected_records: fail(f'{asset}: part record sum mismatch')
    out_dir.mkdir(parents=True, exist_ok=True)
    final=out_dir/spec['target_file']
    fd,tmp_name=tempfile.mkstemp(prefix=final.name+'.tmp.', dir=str(out_dir)); os.close(fd); tmp=Path(tmp_name)
    target_hash=hashlib.sha256(); written=0; part_receipts=[]
    try:
        with tmp.open('wb') as out:
            for idx,p in enumerate(spec['parts']):
                zp=source_dir/p['file']
                if not zp.is_file(): fail(f'{asset}: missing source ZIP {p["file"]}')
                size=zp.stat().st_size
                if size != int(p['zip_bytes']): fail(f'{asset}: ZIP size mismatch {p["file"]}: {size}')
                zsha=sha256_file(zp)
                if zsha.lower()!=p['zip_sha256'].lower(): fail(f'{asset}: ZIP SHA256 mismatch {p["file"]}')
                take_records=int(p['take_records']); member_records=int(p['member_records']); take_bytes=take_records*record_bytes
                if take_records<=0 or take_records>member_records: fail(f'{asset}: invalid take_records {p["file"]}')
                with zipfile.ZipFile(zp,'r') as zf:
                    try: info=zf.getinfo(p['member'])
                    except KeyError: fail(f'{asset}: missing member {p["member"]}')
                    expected_member_bytes=member_records*record_bytes
                    if info.file_size != expected_member_bytes: fail(f'{asset}: member size mismatch {p["file"]}: {info.file_size}')
                    member_hash=hashlib.sha256(); copied=0; fully_consumed=(take_records==member_records)
                    with zf.open(info,'r') as src:
                        remaining=take_bytes
                        while remaining:
                            b=src.read(min(CHUNK,remaining))
                            if not b: fail(f'{asset}: premature EOF {p["file"]}')
                            out.write(b); target_hash.update(b); member_hash.update(b); copied+=len(b); written+=len(b); remaining-=len(b)
                        if fully_consumed:
                            extra=src.read(1)
                            if extra: fail(f'{asset}: unexpected member bytes after full consume {p["file"]}')
                    if copied != take_bytes: fail(f'{asset}: copied byte mismatch {p["file"]}')
                    consumed_sha=member_hash.hexdigest()
                    if fully_consumed and consumed_sha.lower()!=p['member_sha256'].lower(): fail(f'{asset}: full member SHA256 mismatch {p["file"]}')
                part_receipts.append({'file':p['file'],'zip_sha256':zsha,'member':p['member'],'member_file_size':expected_member_bytes,'take_records':take_records,'take_bytes':take_bytes,'fully_consumed':fully_consumed,'consumed_prefix_sha256':consumed_sha,'full_member_sha256_verified':fully_consumed})
            out.flush(); os.fsync(out.fileno())
        actual_hash=target_hash.hexdigest()
        if written != expected_bytes: fail(f'{asset}: final byte mismatch {written} != {expected_bytes}')
        if actual_hash.lower()!=spec['target_sha256'].lower(): fail(f'{asset}: final DEV SHA256 mismatch {actual_hash}')
        os.replace(tmp,final)
        return {'asset':asset,'status':'PASS','output':str(final),'bytes':written,'records':expected_records,'sha256':actual_hash,'parts':part_receipts}
    except Exception:
        try: tmp.unlink(missing_ok=True)
        finally: raise

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',required=True); ap.add_argument('--source-dir',required=True); ap.add_argument('--out-dir',required=True)
    ap.add_argument('--asset',choices=['NQX','XAUUSD','ALL'],default='ALL'); ap.add_argument('--receipt',required=True)
    a=ap.parse_args()
    receipt={'schema':'QROS_SEED0076_MINIMAL_DEV_MATERIALIZATION_RECEIPT_1.0','status':'FAIL','pnl_read':False,'holdout_open':False,'results':[]}
    try:
        manifest=json.loads(Path(a.manifest).read_text(encoding='utf-8')); rb=int(manifest['record_bytes'])
        assets=['NQX','XAUUSD'] if a.asset=='ALL' else [a.asset]
        for asset in assets: receipt['results'].append(stream_asset(asset,manifest[asset],Path(a.source_dir),Path(a.out_dir),rb))
        receipt['status']='PASS'; receipt['decision']='DEV_BYTES_MATERIALIZED_AND_HASH_VERIFIED'
    except Exception as exc:
        receipt['decision']='DEV_MATERIALIZATION_FORBIDDEN'; receipt['error']=f'{type(exc).__name__}:{exc}'
    payload=json.dumps(receipt,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode(); receipt['receipt_sha256']=hashlib.sha256(payload).hexdigest()
    Path(a.receipt).write_text(json.dumps(receipt,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(receipt['decision'])
    return 0 if receipt['status']=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
