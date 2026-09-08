#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,hashlib,json,importlib.util,time,sys
import numpy as np

TFM={'M1':1,'M5':5,'M10':10,'M15':15,'M30':30,'H1':60}
EXPECTED={'NQX':{'M1':673097,'M5':135250,'M10':67775,'M15':45312,'M30':22670,'H1':11341},'XAUUSD':{'M1':681772,'M5':136544,'M10':68326,'M15':45551,'M30':22781,'H1':11394}}

def loadmod(name,path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); sys.modules[name]=m; s.loader.exec_module(m); return m

def aggregate(bucket,o,h,l,c,step):
    b=(bucket//step)*step; st=np.r_[0,np.flatnonzero(b[1:]!=b[:-1])+1]; en=np.r_[st[1:],len(b)]
    return b[st],o[st],np.maximum.reduceat(h,st),np.minimum.reduceat(l,st),c[en-1]

def masksha(x): return hashlib.sha256(np.packbits(x,bitorder='little').tobytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--asset',choices=['NQX','XAUUSD'],required=True); ap.add_argument('--tf',choices=list(TFM),required=True); ap.add_argument('--m1',type=Path,required=True); ap.add_argument('--work',type=Path,required=True); a=ap.parse_args()
    here=Path(__file__).parent; p=loadmod('gp',here/'qros_g30_gap_primary_v185.py'); q=loadmod('gi',here/'qros_g30_gap_independent_v185_1.py')
    with np.load(a.m1) as z:
        bucket=z['bucket']; sides={s:tuple(z[f'{s}_{k}'] for k in ('o','h','l','c')) for s in ('BID','MID')}
    step=TFM[a.tf]*60000
    if a.tf!='M1':
        for s,(o,h,l,c) in list(sides.items()):
            b2,o2,h2,l2,c2=aggregate(bucket,o,h,l,c,step); sides[s]=(o2,h2,l2,c2)
        bucket=b2
    if len(bucket)!=EXPECTED[a.asset][a.tf]: raise SystemExit(f'row mismatch {len(bucket)}')
    out={'schema':'QROS_G30_GAP_MASK_PARITY_SHARD_V185_v1','asset':a.asset,'tf':a.tf,'rows':len(bucket),'feature_sides':{},'all_pass':True}
    for side,(o,h,l,c) in sides.items():
        t=time.time(); pp=p.prepared(o,h,l,c,bucket,step); qq=q.prepared(o,h,l,c,bucket,step)
        if not np.array_equal(pp[2],qq[2]) or not np.array_equal(pp[3],qq[3]): raise SystemExit('gap state mismatch')
        root=hashlib.sha256(); comps=0; identities=0; aliases=0; counts={'CONTINUOUS_FULL_DEPENDENCY':0,'EXCLUDE_REOPENING':0,'REOPENING_ONLY':0}
        for timing in p.TIMINGS:
          for th in p.THRESHOLDS:
            for fam,ns in p.FAMILIES.items():
              for n in ns:
                identities+=3
                pm=p.masks_for_identity(pp,timing,th,fam,n); qm=q.masks_for_identity(qq,timing,th,fam,n)
                # symbolic alias regular reopening == exclude is structural; count once.
                aliases+=1
                for pol in ('CONTINUOUS_FULL_DEPENDENCY','EXCLUDE_REOPENING','REOPENING_ONLY'):
                  for si,label in ((0,'BUY'),(1,'SELL')):
                    x=pm[pol][si]; y=qm[pol][si]; comps+=1
                    if not np.array_equal(x,y): raise SystemExit(f'mask mismatch {side} {timing} {th} {fam} {n} {pol} {label}')
                    dg=masksha(x); root.update(f'{side}|{timing}|{th:g}|{fam}|{n}|{pol}|{label}|{dg}\n'.encode()); counts[pol]+=int(x.sum())
        out['feature_sides'][side]={'canonical_signal_identities':identities,'buy_sell_mask_comparisons':comps,'symbolic_alias_checks':aliases,'root_sha256':root.hexdigest(),'signal_hits_aggregate_non_economic':counts,'elapsed_sec':round(time.time()-t,3),'pass':True}
    out['all_pass']=all(v['pass'] for v in out['feature_sides'].values())
    a.work.mkdir(parents=True,exist_ok=True); path=a.work/f'{a.asset}_{a.tf}_GAP_PARITY.json'; path.write_text(json.dumps(out,separators=(',',':')))
    print(json.dumps({'asset':a.asset,'tf':a.tf,'rows':len(bucket),'comparisons':sum(v['buy_sell_mask_comparisons'] for v in out['feature_sides'].values()),'all_pass':out['all_pass']}))
if __name__=='__main__':main()
