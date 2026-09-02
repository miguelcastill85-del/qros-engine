#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,math,sys
from pathlib import Path
import numpy as np
from numba import njit
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_f03_gate_a_v97 as g
import qros_g30_f03_signal_primary_v97 as sa
import qros_g30_f03_signal_independent_v97 as sb
import qros_g30_f03_execution_primary_v97 as ea
import qros_g30_f03_execution_independent_fast_v99 as eb

@njit(cache=True)
def select_idx_A(ids,et,xt):
    out=np.empty(len(ids),np.int64);k=0;prev=np.int64(-1)
    for ii in range(len(ids)):
        q=ids[ii]
        if et[q]<0 or et[q]<=prev:continue
        out[k]=q;k+=1;prev=xt[q]
    return out[:k]

@njit(cache=True)
def select_idx_B(ids,et,xt):
    out=np.empty(len(ids),np.int64);k=0;prev=np.int64(-1);i=0
    while i<len(ids):
        q=ids[i]
        if et[q]>=0 and et[q]>prev:
            out[k]=q;k+=1;prev=xt[q]
        i+=1
    return out[:k]

def ledger_sha_fast(ch,et,xt,rr):
    rec=np.empty(len(ch),dtype=np.dtype([('et','<i8'),('xt','<i8'),('rr','<f8')]))
    rec['et']=et[ch];rec['xt']=xt[ch];rec['rr']=rr[ch]
    return hashlib.sha256(rec.tobytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--asset',choices=['NQX','XAUUSD'],required=True);ap.add_argument('--src',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--tf',type=int,choices=[1,5,10,15,30,60],required=True);ap.add_argument('--feature-side',choices=['BID','MID'],required=True);ap.add_argument('--unit-receipt',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    unit_receipt=g.verify_unit_receipt(a.unit_receipt);auth=g.ASSET_AUTH[a.asset]
    if g.sha_file(a.src)!=auth['src']:raise SystemExit('DEV_SHA_MISMATCH')
    if g.sha_file(a.cache)!=auth['cache']:raise SystemExit('CACHE_SHA_MISMATCH')
    mm=np.memmap(a.src,dtype=g.DT,mode='r')
    with np.load(a.cache) as z:
        mb=z['mb'];ks=('bo','bh','bl','bc') if a.feature_side=='BID' else ('mo','mh','ml','mc');vals=[z[k] for k in ks]
        A=sa.bars(mb,*vals,a.tf);B=sb.bars(mb,*vals,a.tf);bar_digest_A=g.digest_arrays(A);bar_digest_B=g.digest_arrays(B)
        if bar_digest_A!=bar_digest_B:raise SystemExit('BAR_PARITY_FAIL')
        pa=sa.prepare(*A);pb=sb.prepare(*B);atr14A=sa.atr(A[2],A[3],A[4],14);atr14B=sb.atr(B[2],B[3],B[4],14)
        if not np.array_equal(np.nan_to_num(atr14A,nan=-1.0),np.nan_to_num(atr14B,nan=-1.0)):raise SystemExit('MANAGEMENT_ATR14_PARITY_FAIL')
        seq=hashlib.sha256();by={};order=[];unionBA=np.zeros(len(A[0]),bool);unionSA=np.zeros(len(A[0]),bool);raw=0
        for sp in g.specs():
            raw+=1;key=g.spec_key(sp);bA,sA=sa.mask(pa,*A[1:],*sp);bB,sB=sb.mask(pb,*B[1:],*sp)
            if not np.array_equal(bA,bB) or not np.array_equal(sA,sB):raise SystemExit('SIGNAL_PARITY_FAIL '+key)
            dA=g.mask_digest(bA,sA);dB=g.mask_digest(bB,sB)
            if dA!=dB:raise SystemExit('SIGNAL_DIGEST_PARITY_FAIL '+key)
            seq.update(key.encode()+b'\0'+bytes.fromhex(dA));unionBA|=bA;unionSA|=sA
            if dA not in by:
                by[dA]={'spec':sp,'key':key,'aliases':[key],'buy_idx':np.flatnonzero(bA).astype(np.int64),'sell_idx':np.flatnonzero(sA).astype(np.int64)};order.append(dA)
            else:by[dA]['aliases'].append(key)
        if raw!=g.EXPECTED_RAW:raise SystemExit(f'RAW_CARDINALITY_FAIL {raw}')
        setroot=hashlib.sha256(('\n'.join(sorted(by))+'\n').encode()).hexdigest();rawroot=seq.hexdigest();ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')];step=a.tf*60000
        oaB=ea.outcome(mm['ts'],mm['bid'],mm['ask'],A[0],atr14A,step,*ex,unionBA,1);obB=eb.outcome(mm['ts'],mm['bid'],mm['ask'],B[0],atr14B,step,unionBA,1)
        oaS=ea.outcome(mm['ts'],mm['bid'],mm['ask'],A[0],atr14A,step,*ex,unionSA,-1);obS=eb.outcome(mm['ts'],mm['bid'],mm['ask'],B[0],atr14B,step,unionSA,-1)
        for OA,OB,u,label in ((oaB,obB,unionBA,'BUY'),(oaS,obS,unionSA,'SELL')):
            q=np.flatnonzero(u)
            for k in range(6):
                if not np.array_equal(OA[k][q],OB[k][q]):raise SystemExit('RAW_OUTCOME_PARITY_FAIL '+label)
        records=[];passers=[]
        for d in order:
            meta=by[d];key=meta['key']
            for side,ids,OA,OB in [('BUY',meta['buy_idx'],oaB,obB),('SELL',meta['sell_idx'],oaS,obS)]:
                chA=select_idx_A(ids,OA[0],OA[1]);chB=select_idx_B(ids,OB[0],OB[1])
                if not np.array_equal(chA,chB):raise SystemExit('SELECT_PARITY_FAIL '+key+' '+side)
                if len(chA):
                    for k in range(6):
                        if not np.array_equal(OA[k][chA],OB[k][chB]):raise SystemExit('TRADE_PARITY_FAIL '+key+' '+side)
                rr=OA[5][chA].astype(float);ei=OA[2][chA];xi=OA[3][chA];dist=OA[4][chA];et=OA[0][chA]
                if len(chA):
                    spread=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spread,dist,out=np.zeros(len(spread)),where=dist>0);cons=rr-0.5*extra;sev=rr-extra
                else:cons=rr.copy();sev=rr.copy()
                y18=float(rr[et<g.CUT_2019].sum());y19=float(rr[et>=g.CUT_2019].sum());pfc=g.pf(rr);pfk=g.pf(cons);pfs=g.pf(sev)
                passed=len(chA)>=60 and pfc>=1.20 and pfk>=1.10 and pfs>=1.00 and rr.sum()>0 and cons.sum()>0 and sev.sum()>0 and y18>0 and y19>0
                rec={'id':key,'aliases':meta['aliases'],'signal_sha256':d,'side':side,'n':int(len(chA)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':pfc,'pf_k':pfk,'pf_s':pfs,'r2018':y18,'r2019':y19,'ledger_sha256':ledger_sha_fast(chA,OA[0],OA[1],OA[5]),'pass':bool(passed)}
                records.append(rec)
                if passed:passers.append(rec)
        shard=('H1' if a.tf==60 else f'M{a.tf}')+'_'+a.feature_side
        obj={'schema':'QROS_G30_F03_GATE_A_SHARD_V97_v1','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F03_ATR_PERIOD','asset':a.asset,'scope':'EXPOSED_DEV_2018_2019_ONLY_NO_2020_PLUS_PNL','shard':shard,'bars':int(len(A[0])),'raw_identities':raw,'unique_masks':len(order),'exact_alias_count':raw-len(order),'evaluated_configurations':len(records),'bar_digest':bar_digest_A,'raw_identity_sequence_sha256':rawroot,'unique_mask_set_sha256':setroot,'union_buy':int(unionBA.sum()),'union_sell':int(unionSA.sum()),'signal_parity':'PASS_EXACT','trade_parity':'PASS_EXACT','management':{'signal_atr_periods':[7,10,20,28,50],'stop_atr_period':14,'atr_stop_mult':3.0,'reward_r_multiple':1.5,'time_stop_bars':20},'unit_binding':{'receipt_input_sha256':unit_receipt.get('input_sha256'),'status':'PASS','effective_stop_atr_mult':3.0},'gate':{'min_trades':60,'pf_central_min':1.20,'pf_conservative_min':1.10,'pf_severe_min':1.00,'both_dev_years_positive_central':True,'net_positive_all_costs':True},'passed':len(passers),'passed_buy':sum(x['side']=='BUY' for x in passers),'passed_sell':sum(x['side']=='SELL' for x in passers),'passers':passers,'all_records':records,'future_pnl_read':False,'historical_holdout_opened':False,'status':'PASS'}
        a.out.write_text(json.dumps(g.safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8')
        print(json.dumps({k:obj[k] for k in ['asset','shard','bars','raw_identities','unique_masks','exact_alias_count','evaluated_configurations','passed','passed_buy','passed_sell','signal_parity','trade_parity']},sort_keys=True))
if __name__=='__main__':main()
