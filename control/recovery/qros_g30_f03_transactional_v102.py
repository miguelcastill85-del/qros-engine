#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_f03_gate_a_v97 as g
import qros_g30_f03_signal_primary_v97 as sa
import qros_g30_f03_signal_independent_v97 as sb
import qros_g30_f03_execution_primary_v97 as ea
import qros_g30_f03_execution_independent_fast_v99 as eb
import qros_g30_f03_gate_a_fastscore_v101 as v101

def save_arr(root,name,a): np.save(root/f'{name}.npy',a,allow_pickle=False)
def load_arr(root,name): return np.load(root/f'{name}.npy',mmap_mode='r')
def shard_name(tf,fs): return ('H1' if tf==60 else f'M{tf}')+'_'+fs

def prepare(a):
    root=a.work;root.mkdir(parents=True,exist_ok=True)
    unit=g.verify_unit_receipt(a.unit_receipt);auth=g.ASSET_AUTH[a.asset]
    if g.sha_file(a.src)!=auth['src']:raise SystemExit('DEV_SHA_MISMATCH')
    if g.sha_file(a.cache)!=auth['cache']:raise SystemExit('CACHE_SHA_MISMATCH')
    mm=np.memmap(a.src,dtype=g.DT,mode='r')
    with np.load(a.cache) as z:
        mb=z['mb'];ks=('bo','bh','bl','bc') if a.feature_side=='BID' else ('mo','mh','ml','mc');vals=[z[k] for k in ks]
        A=sa.bars(mb,*vals,a.tf);B=sb.bars(mb,*vals,a.tf);bdA=g.digest_arrays(A);bdB=g.digest_arrays(B)
        if bdA!=bdB:raise SystemExit('BAR_PARITY_FAIL')
        pa=sa.prepare(*A);pb=sb.prepare(*B);atrA=sa.atr(A[2],A[3],A[4],14);atrB=sb.atr(B[2],B[3],B[4],14)
        if not np.array_equal(np.nan_to_num(atrA,nan=-1.0),np.nan_to_num(atrB,nan=-1.0)):raise SystemExit('MANAGEMENT_ATR14_PARITY_FAIL')
        seq=hashlib.sha256();by={};order=[];unionB=np.zeros(len(A[0]),bool);unionS=np.zeros(len(A[0]),bool);raw=0
        bpath=root/'buy_idx.i32';spath=root/'sell_idx.i32';boff=soff=0
        with bpath.open('wb') as fb, spath.open('wb') as fs:
            for sp in g.specs():
                raw+=1;key=g.spec_key(sp);bA,sA=sa.mask(pa,*A[1:],*sp);bB,sB=sb.mask(pb,*B[1:],*sp)
                if not np.array_equal(bA,bB) or not np.array_equal(sA,sB):raise SystemExit('SIGNAL_PARITY_FAIL '+key)
                d=g.mask_digest(bA,sA)
                if d!=g.mask_digest(bB,sB):raise SystemExit('SIGNAL_DIGEST_PARITY_FAIL '+key)
                seq.update(key.encode()+b'\0'+bytes.fromhex(d));unionB|=bA;unionS|=sA
                if d not in by:
                    bi=np.flatnonzero(bA).astype('<i4');si=np.flatnonzero(sA).astype('<i4')
                    bi.tofile(fb);si.tofile(fs)
                    by[d]={'key':key,'aliases':[key],'buy_off':boff,'buy_n':int(len(bi)),'sell_off':soff,'sell_n':int(len(si))}
                    boff+=len(bi);soff+=len(si);order.append(d)
                else: by[d]['aliases'].append(key)
        if raw!=g.EXPECTED_RAW:raise SystemExit('RAW_CARDINALITY_FAIL')
        setroot=hashlib.sha256(('\n'.join(sorted(by))+'\n').encode()).hexdigest();rawroot=seq.hexdigest();ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')];step=a.tf*60000
        oaB=ea.outcome(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,unionB,1);obB=eb.outcome(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,unionB,1)
        oaS=ea.outcome(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,unionS,-1);obS=eb.outcome(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,unionS,-1)
        for OA,OB,u,label in ((oaB,obB,unionB,'BUY'),(oaS,obS,unionS,'SELL')):
            q=np.flatnonzero(u)
            for k in range(6):
                if not np.array_equal(OA[k][q],OB[k][q]):raise SystemExit('RAW_OUTCOME_PARITY_FAIL '+label)
        for side,OA in [('B',oaB),('S',oaS)]:
            for k,name in enumerate(('et','xt','ei','xi','dist','rr')):save_arr(root,f'{side}_{name}',OA[k])
        meta={'asset':a.asset,'shard':shard_name(a.tf,a.feature_side),'bars':int(len(A[0])),'raw_identities':raw,'unique_masks':len(order),'exact_alias_count':raw-len(order),'bar_digest':bdA,'raw_identity_sequence_sha256':rawroot,'unique_mask_set_sha256':setroot,'union_buy':int(unionB.sum()),'union_sell':int(unionS.sum()),'order':order,'by':by,'unit_input_sha256':unit.get('input_sha256'),'src':str(a.src),'tf':a.tf,'feature_side':a.feature_side}
        (root/'manifest.json').write_text(json.dumps(meta,separators=(',',':')),encoding='utf-8')
        print(json.dumps({k:meta[k] for k in ['asset','shard','bars','raw_identities','unique_masks','exact_alias_count','union_buy','union_sell']},sort_keys=True))

def score(a):
    root=a.work;meta=json.loads((root/'manifest.json').read_text());order=meta['order'];end=min(a.end,len(order))
    if a.start<0 or a.start>=end:raise SystemExit('BAD_RANGE')
    mm=np.memmap(meta['src'],dtype=g.DT,mode='r');bidx=np.memmap(root/'buy_idx.i32',dtype='<i4',mode='r');sidx=np.memmap(root/'sell_idx.i32',dtype='<i4',mode='r')
    OA_B=tuple(load_arr(root,'B_'+x) for x in ('et','xt','ei','xi','dist','rr'));OA_S=tuple(load_arr(root,'S_'+x) for x in ('et','xt','ei','xi','dist','rr'))
    recs=[];passers=[]
    for i in range(a.start,end):
        d=order[i];m=meta['by'][d];
        for side,arr,off,n,OA in [('BUY',bidx,m['buy_off'],m['buy_n'],OA_B),('SELL',sidx,m['sell_off'],m['sell_n'],OA_S)]:
            ids=np.asarray(arr[off:off+n],dtype=np.int64);chA=v101.select_idx_A(ids,OA[0],OA[1]);chB=v101.select_idx_B(ids,OA[0],OA[1])
            if not np.array_equal(chA,chB):raise SystemExit('SELECT_PARITY_FAIL '+m['key']+' '+side)
            rr=OA[5][chA].astype(float);ei=OA[2][chA];xi=OA[3][chA];dist=OA[4][chA];et=OA[0][chA]
            if len(chA):
                spread=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spread,dist,out=np.zeros(len(spread)),where=dist>0);cons=rr-0.5*extra;sev=rr-extra
            else:cons=rr.copy();sev=rr.copy()
            y18=float(rr[et<g.CUT_2019].sum());y19=float(rr[et>=g.CUT_2019].sum());pfc=g.pf(rr);pfk=g.pf(cons);pfs=g.pf(sev)
            passed=len(chA)>=60 and pfc>=1.20 and pfk>=1.10 and pfs>=1.00 and rr.sum()>0 and cons.sum()>0 and sev.sum()>0 and y18>0 and y19>0
            rec={'id':m['key'],'aliases':m['aliases'],'signal_sha256':d,'side':side,'n':int(len(chA)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':pfc,'pf_k':pfk,'pf_s':pfs,'r2018':y18,'r2019':y19,'ledger_sha256':v101.ledger_sha_fast(chA,OA[0],OA[1],OA[5]),'pass':bool(passed)}
            recs.append(rec)
            if passed:passers.append(rec)
    out={'start':a.start,'end':end,'records':recs,'passers':passers}
    a.out.write_text(json.dumps(g.safe(out),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({'start':a.start,'end':end,'records':len(recs),'passers':len(passers)},sort_keys=True))

def merge(a):
    root=a.work;meta=json.loads((root/'manifest.json').read_text());chunks=[]
    for p in a.chunks:
        o=json.loads(Path(p).read_text());chunks.append(o)
    chunks.sort(key=lambda x:x['start']);cur=0;records=[];passers=[]
    for c in chunks:
        if c['start']!=cur:raise SystemExit(f'CHUNK_GAP expected={cur} got={c["start"]}')
        cur=c['end'];records.extend(c['records']);passers.extend(c['passers'])
    if cur!=meta['unique_masks']:raise SystemExit(f'INCOMPLETE {cur}/{meta["unique_masks"]}')
    obj={'schema':'QROS_G30_F03_GATE_A_SHARD_V97_v1','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F03_ATR_PERIOD','asset':meta['asset'],'scope':'EXPOSED_DEV_2018_2019_ONLY_NO_2020_PLUS_PNL','shard':meta['shard'],'bars':meta['bars'],'raw_identities':meta['raw_identities'],'unique_masks':meta['unique_masks'],'exact_alias_count':meta['exact_alias_count'],'evaluated_configurations':len(records),'bar_digest':meta['bar_digest'],'raw_identity_sequence_sha256':meta['raw_identity_sequence_sha256'],'unique_mask_set_sha256':meta['unique_mask_set_sha256'],'union_buy':meta['union_buy'],'union_sell':meta['union_sell'],'signal_parity':'PASS_EXACT','trade_parity':'PASS_EXACT','management':{'signal_atr_periods':[7,10,20,28,50],'stop_atr_period':14,'atr_stop_mult':3.0,'reward_r_multiple':1.5,'time_stop_bars':20},'unit_binding':{'receipt_input_sha256':meta['unit_input_sha256'],'status':'PASS','effective_stop_atr_mult':3.0},'gate':{'min_trades':60,'pf_central_min':1.20,'pf_conservative_min':1.10,'pf_severe_min':1.00,'both_dev_years_positive_central':True,'net_positive_all_costs':True},'passed':len(passers),'passed_buy':sum(x['side']=='BUY' for x in passers),'passed_sell':sum(x['side']=='SELL' for x in passers),'passers':passers,'all_records':records,'future_pnl_read':False,'historical_holdout_opened':False,'status':'PASS'}
    a.out.write_text(json.dumps(g.safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({k:obj[k] for k in ['asset','shard','raw_identities','unique_masks','evaluated_configurations','passed','passed_buy','passed_sell','signal_parity','trade_parity']},sort_keys=True))

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('prepare');p.add_argument('--asset',choices=['NQX','XAUUSD'],required=True);p.add_argument('--src',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--tf',type=int,choices=[1,5,10,15,30,60],required=True);p.add_argument('--feature-side',choices=['BID','MID'],required=True);p.add_argument('--unit-receipt',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    p=sub.add_parser('score');p.add_argument('--work',type=Path,required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True);p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('merge');p.add_argument('--work',type=Path,required=True);p.add_argument('--chunks',nargs='+',required=True);p.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();{'prepare':prepare,'score':score,'merge':merge}[a.cmd](a)
if __name__=='__main__':main()
