#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os
from pathlib import Path
import qros_g30_f03_gate_a_v97 as g
import qros_g30_f03_transactional_v105 as v105
import qros_g30_f03_transactional_v104 as v104

def validate_receipt(path:Path,asset:str,src:Path,cache:Path):
    r=json.loads(path.read_text(encoding='utf-8'))
    if r.get('schema')!='QROS_RUNTIME_VERIFIED_INPUT_IDENTITY_1.0' or r.get('status')!='PASS_REUSE_PREVIOUSLY_VERIFIED_BYTES' or r.get('scope')!='CURRENT_RUNTIME_ONLY' or r.get('asset')!=asset:
        raise SystemExit('RUNTIME_INPUT_RECEIPT_INVALID')
    auth=g.ASSET_AUTH[asset]
    expected={'source':(src.resolve(),auth['src']),'cache':(cache.resolve(),auth['cache'])}
    resolved={}
    for role,(p,sha) in expected.items():
        x=r.get('items',{}).get(role)
        if not isinstance(x,dict):raise SystemExit('RUNTIME_INPUT_RECEIPT_MISSING_'+role.upper())
        if Path(x.get('path','')).resolve()!=p or x.get('sha256')!=sha:raise SystemExit('RUNTIME_INPUT_RECEIPT_AUTHORITY_MISMATCH_'+role.upper())
        s=os.stat(p)
        got=(s.st_size,s.st_dev,s.st_ino,s.st_mtime_ns)
        exp=(x.get('size'),x.get('st_dev'),x.get('st_ino'),x.get('mtime_ns'))
        if got!=exp:raise SystemExit('RUNTIME_INPUT_OBJECT_CHANGED_'+role.upper())
        resolved[str(p)]=sha
    return resolved

def prepare(a):
    resolved=validate_receipt(a.input_identity_receipt,a.asset,a.src,a.cache)
    original=g.sha_file
    def certified_sha(p):
        q=str(Path(p).resolve())
        if q in resolved:return resolved[q]
        return original(Path(p))
    g.sha_file=certified_sha
    try:v105.prepare(a)
    finally:g.sha_file=original

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('prepare');p.add_argument('--asset',choices=['NQX','XAUUSD'],required=True);p.add_argument('--src',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--tf',type=int,choices=[1,5,10,15,30,60],required=True);p.add_argument('--feature-side',choices=['BID','MID'],required=True);p.add_argument('--unit-receipt',type=Path,required=True);p.add_argument('--input-identity-receipt',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    p=sub.add_parser('score');p.add_argument('--work',type=Path,required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True);p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('merge');p.add_argument('--work',type=Path,required=True);p.add_argument('--chunks',nargs='+',required=True);p.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();{'prepare':prepare,'score':v104.score,'merge':v104.merge}[a.cmd](a)
if __name__=='__main__':main()
