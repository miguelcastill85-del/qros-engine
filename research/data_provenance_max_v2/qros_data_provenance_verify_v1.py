#!/usr/bin/env python3
import argparse, hashlib, json, zipfile
from pathlib import Path
import numpy as np

REC=np.dtype([('t','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')], align=False)
WIDTH=REC.itemsize
assert WIDTH==17

def sha256_file(path, chunk=8<<20):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(chunk), b''): h.update(b)
    return h.hexdigest()

def audit_manifest(path):
    raw=Path(path).read_bytes(); m=json.loads(raw); parts=m['multipart']['parts']; carrier=m['carrier']
    errs=[]; exp_start=0; prev_last=None
    for i,p in enumerate(parts,1):
        if p['index']!=i: errs.append(f'index:{i}:{p["index"]}')
        if p['parts_count']!=len(parts): errs.append(f'parts_count:{i}')
        if p['start_record']!=exp_start: errs.append(f'start_record:{i}:{p["start_record"]}:{exp_start}')
        if p['payload_bytes']!=p['records']*WIDTH: errs.append(f'payload_bytes:{i}')
        if prev_last is not None and p['first_timestamp_ms'] < prev_last: errs.append(f'boundary_reverse:{i}')
        exp_start += p['records']; prev_last=p['last_timestamp_ms']
    total_records=sum(p['records'] for p in parts); total_bytes=sum(p['payload_bytes'] for p in parts)
    if len(parts)!=m['multipart']['parts_count']: errs.append('manifest_parts_count')
    if total_records!=carrier['records']: errs.append('carrier_records')
    if total_bytes!=carrier['bytes']: errs.append('carrier_bytes')
    if parts[0]['first_timestamp_ms']!=carrier['first_timestamp_ms']: errs.append('carrier_first_timestamp')
    if parts[-1]['last_timestamp_ms']!=carrier['last_timestamp_ms']: errs.append('carrier_last_timestamp')
    return {'file':Path(path).name,'sha256':hashlib.sha256(raw).hexdigest(),'asset':m['asset'],'parts':len(parts),'records':total_records,'payload_bytes':total_bytes,'carrier_sha256':carrier['sha256'],'errors':errs,'status':'PASS' if not errs else 'FAIL'},m

def _scalar_tuple(a): return (int(a['t']),int(a['bid']),int(a['ask']),int(a['flags']))

def scan_payload_stream(zf, member, chunk_bytes=34_000_000):
    h=hashlib.sha256(); total=0; records=0; reversals=same_ts=zero=crossed=nonpos=exact=0; flags={}; first=None; last=None; prev=None; carry=b''
    with zf.open(member,'r') as f:
        while True:
            b=f.read(chunk_bytes)
            if not b: break
            h.update(b); total += len(b); data=carry+b; n=len(data)//WIDTH; used=n*WIDTH; carry=data[used:]
            if not n: continue
            a=np.frombuffer(data[:used], dtype=REC); records += n
            t=a['t']; bid=a['bid']; ask=a['ask']; fl=a['flags']
            if first is None: first=_scalar_tuple(a[0])
            if prev is not None:
                reversals += int(t[0] < prev[0]); same_ts += int(t[0] == prev[0]); exact += int(_scalar_tuple(a[0]) == prev)
            if n>1:
                reversals += int(np.count_nonzero(t[1:] < t[:-1])); same_ts += int(np.count_nonzero(t[1:] == t[:-1]))
                exact += int(np.count_nonzero((t[1:]==t[:-1]) & (bid[1:]==bid[:-1]) & (ask[1:]==ask[:-1]) & (fl[1:]==fl[:-1])))
            zero += int(np.count_nonzero(ask==bid)); crossed += int(np.count_nonzero(ask<bid)); nonpos += int(np.count_nonzero((bid<=0)|(ask<=0)))
            u,c=np.unique(fl,return_counts=True)
            for x,y in zip(u,c): flags[str(int(x))]=flags.get(str(int(x)),0)+int(y)
            last=_scalar_tuple(a[-1]); prev=last
    if carry: raise ValueError(f'payload length not divisible by {WIDTH}: remainder={len(carry)}')
    return {'payload_sha256':h.hexdigest(),'payload_bytes':total,'records':records,'first_record':first,'last_record':last,'timestamp_reversals':reversals,'identical_timestamps_adjacent':same_ts,'zero_spread':zero,'crossed_spread':crossed,'nonpositive_bid_or_ask':nonpos,'exact_consecutive_records':exact,'flag_counts':flags}

def audit_zip(path, manifests):
    p=Path(path); zh=sha256_file(p); candidates=[]
    for m in manifests:
        candidates += [x for x in m['multipart']['parts'] if x['sha256']==zh]
    if len(candidates)!=1: return {'file':p.name,'zip_sha256':zh,'status':'FAIL','errors':[f'manifest_match_count={len(candidates)}']}
    exp=candidates[0]; errs=[]
    with zipfile.ZipFile(p) as z:
        bad=z.testzip()
        if bad: errs.append(f'zip_crc:{bad}')
        names=z.namelist()
        if exp['payload_member'] not in names: errs.append('payload_member_missing')
        if 'PART_META.json' not in names: errs.append('part_meta_missing')
        meta=json.loads(z.read('PART_META.json')) if 'PART_META.json' in names else {}
        for k in ['asset','carrier_sha256','first_timestamp_ms','index','last_timestamp_ms','parts_count','payload_bytes','payload_member','payload_sha256','records','schema','start_record']:
            if k in exp and meta.get(k)!=exp.get(k): errs.append(f'meta:{k}')
        scan=scan_payload_stream(z,exp['payload_member']) if exp['payload_member'] in names else {}
    for k in ['payload_sha256','payload_bytes','records']:
        if scan.get(k)!=exp.get(k): errs.append(f'{k}:{scan.get(k)}:{exp.get(k)}')
    if scan.get('first_record') and scan['first_record'][0]!=exp['first_timestamp_ms']: errs.append('first_timestamp')
    if scan.get('last_record') and scan['last_record'][0]!=exp['last_timestamp_ms']: errs.append('last_timestamp')
    if scan.get('timestamp_reversals',1)!=0: errs.append('timestamp_reversals')
    return {'file':p.name,'zip_sha256':zh,'expected_file':exp['file'],'asset':exp['asset'],'scan':scan,'errors':errs,'status':'PASS' if not errs else 'FAIL'}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--manifest',action='append',required=True); ap.add_argument('--zip',action='append',default=[]); ap.add_argument('--out',required=True); args=ap.parse_args()
    mans=[]; ma=[]
    for x in args.manifest:
        a,m=audit_manifest(x); ma.append(a); mans.append(m)
    za=[audit_zip(x,mans) for x in args.zip]
    out={'schema':'QROS_DATA_PROVENANCE_INDEPENDENT_VERIFY_1.0','record_width':WIDTH,'manifest_audits':ma,'zip_audits':za}
    out['status']='PASS' if all(x['status']=='PASS' for x in ma+za) else 'FAIL'
    Path(args.out).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':out['status'],'out':args.out,'sha256':sha256_file(args.out)},sort_keys=True))
    return 0 if out['status']=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
