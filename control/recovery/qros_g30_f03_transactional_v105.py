#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,sys,gc
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_f03_gate_a_v97 as g
import qros_g30_f03_signal_primary_v97 as sa
import qros_g30_f03_signal_independent_v97 as sb
import qros_g30_f03_execution_primary_v97 as ea
import qros_g30_f03_execution_independent_fast_v99 as eb
import qros_g30_f03_transactional_v104 as v104

def save_arr(root,name,a):np.save(root/f'{name}.npy',a,allow_pickle=False)
def shard_name(tf,fs):return ('H1' if tf==60 else f'M{tf}')+'_'+fs

def prepare(a):
    root=a.work;root.mkdir(parents=True,exist_ok=True);unit=g.verify_unit_receipt(a.unit_receipt);auth=g.ASSET_AUTH[a.asset]
    if g.sha_file(a.src)!=auth['src']:raise SystemExit('DEV_SHA_MISMATCH')
    if g.sha_file(a.cache)!=auth['cache']:raise SystemExit('CACHE_SHA_MISMATCH')
    mm=np.memmap(a.src,dtype=g.DT,mode='r')
    with np.load(a.cache) as z:
        mb=z['mb'];ks=('bo','bh','bl','bc') if a.feature_side=='BID' else ('mo','mh','ml','mc');vals=[z[k] for k in ks]
        A=sa.bars(mb,*vals,a.tf);B=sb.bars(mb,*vals,a.tf);bdA=g.digest_arrays(A);bdB=g.digest_arrays(B)
        if bdA!=bdB:raise SystemExit('BAR_PARITY_FAIL')
        pa=sa.prepare(*A);pb=sb.prepare(*B);atrA=sa.atr(A[2],A[3],A[4],14);atrB=sb.atr(B[2],B[3],B[4],14)
        if not np.array_equal(np.nan_to_num(atrA,nan=-1.0),np.nan_to_num(atrB,nan=-1.0)):raise SystemExit('MANAGEMENT_ATR14_PARITY_FAIL')
        seq=hashlib.sha256();by={};order=[];uB=np.zeros(len(A[0]),bool);uS=np.zeros(len(A[0]),bool);raw=0
        for sp in g.specs():
            raw+=1;key=g.spec_key(sp);bA,sA=sa.mask(pa,*A[1:],*sp);bB,sB=sb.mask(pb,*B[1:],*sp)
            if not np.array_equal(bA,bB) or not np.array_equal(sA,sB):raise SystemExit('SIGNAL_PARITY_FAIL '+key)
            d=g.mask_digest(bA,sA)
            if d!=g.mask_digest(bB,sB):raise SystemExit('SIGNAL_DIGEST_PARITY_FAIL '+key)
            seq.update(key.encode()+b'\0'+bytes.fromhex(d));uB|=bA;uS|=sA
            if d not in by:by[d]={'key':key,'aliases':[key],'spec':list(sp)};order.append(d)
            else:by[d]['aliases'].append(key)
        if raw!=g.EXPECTED_RAW:raise SystemExit('RAW_CARDINALITY_FAIL')
        del pa,pb;gc.collect()
        ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')];step=a.tf*60000
        oaB=ea.outcome(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,uB,1);obB=eb.outcome_core(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,*ex,uB,1)
        q=np.flatnonzero(uB)
        for k in range(6):
            if not np.array_equal(oaB[k][q],obB[k][q]):raise SystemExit('RAW_OUTCOME_PARITY_FAIL BUY')
        del obB;gc.collect()
        oaS=ea.outcome(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,uS,-1);obS=eb.outcome_core(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,*ex,uS,-1)
        q=np.flatnonzero(uS)
        for k in range(6):
            if not np.array_equal(oaS[k][q],obS[k][q]):raise SystemExit('RAW_OUTCOME_PARITY_FAIL SELL')
        del obS;gc.collect()
        for side,OA in [('B',oaB),('S',oaS)]:
            for k,name in enumerate(('et','xt','ei','xi','dist','rr')):save_arr(root,f'{side}_{name}',OA[k])
        meta={'asset':a.asset,'shard':shard_name(a.tf,a.feature_side),'bars':int(len(A[0])),'raw_identities':raw,'unique_masks':len(order),'exact_alias_count':raw-len(order),'bar_digest':bdA,'raw_identity_sequence_sha256':seq.hexdigest(),'unique_mask_set_sha256':hashlib.sha256(('\n'.join(sorted(by))+'\n').encode()).hexdigest(),'union_buy':int(uB.sum()),'union_sell':int(uS.sum()),'order':order,'by':by,'unit_input_sha256':unit.get('input_sha256'),'src':str(a.src),'cache':str(a.cache),'tf':a.tf,'feature_side':a.feature_side}
        (root/'manifest.json').write_text(json.dumps(meta,separators=(',',':')),encoding='utf-8')
        print(json.dumps({k:meta[k] for k in ['asset','shard','bars','raw_identities','unique_masks','exact_alias_count','union_buy','union_sell']},sort_keys=True))

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('prepare');p.add_argument('--asset',choices=['NQX','XAUUSD'],required=True);p.add_argument('--src',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--tf',type=int,choices=[1,5,10,15,30,60],required=True);p.add_argument('--feature-side',choices=['BID','MID'],required=True);p.add_argument('--unit-receipt',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    p=sub.add_parser('score');p.add_argument('--work',type=Path,required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True);p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('merge');p.add_argument('--work',type=Path,required=True);p.add_argument('--chunks',nargs='+',required=True);p.add_argument('--out',type=Path,required=True)
    a=ap.parse_args(); {'prepare':prepare,'score':v104.score,'merge':v104.merge}[a.cmd](a)
if __name__=='__main__':main()
