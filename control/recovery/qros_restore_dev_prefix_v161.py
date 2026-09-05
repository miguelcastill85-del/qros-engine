"""Recover only the exact authorized development prefix from enumerated ZIP parts."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path, PurePosixPath
import numpy as np

DT = np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])

def main():
    import zipfile
    ap=argparse.ArgumentParser()
    ap.add_argument('--receipt',type=Path,required=True)
    ap.add_argument('--parts',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--audit',type=Path,required=True)
    a=ap.parse_args(); authority=json.loads(a.receipt.read_text())
    wanted=authority['development_prefix']; a.out.parent.mkdir(parents=True,exist_ok=True)
    temp=a.out.with_suffix(a.out.suffix+'.partial'); whole=hashlib.sha256(); rows=[]
    with temp.open('wb') as out:
        for part in authority['parts']:
            path=a.parts/part['file']; count=part['bytes_consumed']; ph=hashlib.sha256()
            with zipfile.ZipFile(path) as z:
                infos=z.infolist()
                if len(infos)!=2 or len({i.filename for i in infos})!=2:
                    raise ValueError('unexpected archive members')
                for info in infos:
                    p=PurePosixPath(info.filename)
                    if p.is_absolute() or '..' in p.parts or (info.external_attr>>16)&0o170000==0o120000:
                        raise ValueError('unsafe archive path')
                meta=json.loads(z.read('PART_META.json')); member=meta['payload_member']
                if z.getinfo(member).file_size!=meta['payload_bytes'] or not 0<count<=meta['payload_bytes']:
                    raise ValueError('payload size mismatch')
                left=count
                with z.open(member) as src:
                    while left:
                        block=src.read(min(8<<20,left))
                        if not block:raise ValueError('truncated payload')
                        out.write(block);whole.update(block);ph.update(block);left-=len(block)
                if ph.hexdigest()!=part['sha256_consumed']:raise ValueError('part prefix hash mismatch')
                rows.append({'file':path.name,'bytes_consumed':count,'sha256_consumed':ph.hexdigest()})
                print(json.dumps({'phase':'verified_part','part':len(rows),'total':len(authority['parts']),'bytes':out.tell()}),flush=True)
        out.flush();os.fsync(out.fileno())
    if temp.stat().st_size!=wanted['expected_bytes'] or whole.hexdigest()!=wanted['expected_sha256']:
        raise ValueError('canonical development hash mismatch')
    mm=np.memmap(temp,dtype=DT,mode='r'); n=len(mm); prev=None; oo=zero=cross=0;years={};flags={}
    for start in range(0,n,2_000_000):
        x=mm[start:start+2_000_000];ts=x['ts'];b=x['bid'].astype(np.int64);ak=x['ask'].astype(np.int64)
        oo+=int(np.sum(ts[1:]<ts[:-1]))+int(prev is not None and ts[0]<prev);prev=int(ts[-1])
        zero+=int(np.sum(ak==b));cross+=int(np.sum(ak<b))
        if np.any(ts<1514764800000) or np.any(ts>=1577836800000):raise ValueError('outside authorized development')
        for y,k in [('2018',int(np.sum(ts<1546300800000))),('2019',int(np.sum(ts>=1546300800000)))]:years[y]=years.get(y,0)+k
        fs,ns=np.unique(x['flags'],return_counts=True)
        for f,c in zip(fs,ns):flags[str(int(f))]=flags.get(str(int(f)),0)+int(c)
    audit={'schema':'QROS_DEV_REMATERIALIZATION_V161_v1','asset':authority['asset'],'bytes':temp.stat().st_size,'records':n,'sha256':whole.hexdigest(),'first_timestamp_ms':int(mm['ts'][0]),'last_timestamp_ms':int(mm['ts'][-1]),'out_of_order_pairs':oo,'zero_spread':zero,'crossed_spread':cross,'year_counts':years,'flags_hist':flags,'parts':rows,'clock':'DARWINEX_MT5_SERVER_TIME_AS_STORED_NO_TRANSFORMATION','economic_scoring':False,'holdout_opened':False}
    ref=authority['tick_audit']
    for key in ('first_timestamp_ms','last_timestamp_ms','out_of_order_pairs','zero_spread','crossed_spread','flags_hist'):
        if audit[key]!=ref[key]:raise ValueError('structural audit mismatch: '+key)
    if years!=ref['epoch_year_counts_diagnostic_only']:raise ValueError('year count mismatch')
    del mm;os.replace(temp,a.out);audit['status']='PASS_EXACT_CANONICAL_PREFIX_AND_STRUCTURAL_AUDIT'
    a.audit.parent.mkdir(parents=True,exist_ok=True);a.audit.write_text(json.dumps(audit,sort_keys=True,indent=2)+'\n')
    print(json.dumps(audit,sort_keys=True),flush=True)

if __name__=='__main__':main()
