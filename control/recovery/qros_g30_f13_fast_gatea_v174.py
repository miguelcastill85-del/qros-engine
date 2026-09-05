#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, sqlite3, struct, sys, time
from pathlib import Path
import numpy as np
from numba import njit
sys.path.insert(0,'/mnt/data')
import qros_g30_f13_transactional_v171 as r
import qros_g30_f13_primary_v171 as sa
import qros_g30_f13_independent_v171 as sb
import qros_g30_f10_exec_core_v127 as ex
import f13_local_prepare as fl

SCHEMA='QROS_G30_F13_FAST_GATE_A_V174_v1'
PERS=list(sa.persistence_specs()); PAIRS=list(r.pair_specs())
assert len(PERS)==18 and len(PAIRS)==2229 and r.EXPECTED_RAW==722196
CTZ16=np.empty(65536,np.uint8);CTZ16[0]=0
for _i in range(1,65536):CTZ16[_i]=((_i & -_i).bit_length()-1)

@njit(cache=True)
def eval_words(words, nbits, et, xt, rr, cons, sev, year18, ctz):
    n=0; sc=0.0; sk=0.0; ss=0.0; posc=0.0; negc=0.0; posk=0.0; negk=0.0; poss=0.0; negs=0.0; y18=0.0; y19=0.0
    prev=np.int64(-1)
    for wi in range(len(words)):
        w=words[wi]
        while w!=0:
            lo=int(w & np.uint64(65535))
            if lo: off=int(ctz[lo])
            else:
                lo=int((w>>np.uint64(16)) & np.uint64(65535))
                if lo: off=16+int(ctz[lo])
                else:
                    lo=int((w>>np.uint64(32)) & np.uint64(65535))
                    if lo: off=32+int(ctz[lo])
                    else: off=48+int(ctz[int((w>>np.uint64(48)) & np.uint64(65535))])
            q=wi*64+off
            if q>=nbits: break
            if et[q]>=0 and et[q]>prev:
                prev=xt[q]; n+=1
                a=rr[q]; b=cons[q]; c=sev[q]
                sc+=a; sk+=b; ss+=c
                if a>0:posc+=a
                elif a<0:negc-=a
                if b>0:posk+=b
                elif b<0:negk-=b
                if c>0:poss+=c
                elif c<0:negs-=c
                if year18[q]:y18+=a
                else:y19+=a
            w &= w-np.uint64(1)
    pfc=(np.inf if posc>0 else 0.0) if negc==0 else posc/negc
    pfk=(np.inf if posk>0 else 0.0) if negk==0 else posk/negk
    pfs=(np.inf if poss>0 else 0.0) if negs==0 else poss/negs
    passed=n>=60 and pfc>=1.20 and pfk>=1.10 and pfs>=1.00 and sc>0 and sk>0 and ss>0 and y18>0 and y19>0
    return n,sc,sk,ss,pfc,pfk,pfs,y18,y19,passed

def sha_file(p):return r.sha_file(Path(p))
def safe(v):return r.safe(v)
def load_exec_metrics(work,side,src):
    work=Path(work);src=Path(src)
    et=np.load(work/f'{side}_et.npy');xt=np.load(work/f'{side}_xt.npy');ei=np.load(work/f'{side}_ei.npy');xi=np.load(work/f'{side}_xi.npy');dist=np.load(work/f'{side}_dist.npy');rr=np.load(work/f'{side}_rr.npy')
    mm=np.memmap(src,dtype=ex.DT,mode='r');extra=np.zeros(len(rr),np.float64);ok=(ei>=0)&(xi>=0)&(dist>0);ix=np.flatnonzero(ok)
    spr=(mm['ask'][ei[ix]]-mm['bid'][ei[ix]]).astype(np.float64)+(mm['ask'][xi[ix]]-mm['bid'][xi[ix]]).astype(np.float64);extra[ix]=spr/dist[ix]
    return (et,xt,rr,rr-.5*extra,rr-extra,et<ex.CUT_2019), {'et':et,'xt':xt,'ei':ei,'xi':xi,'dist':dist,'rr':rr}, mm

def build_outcomes(asset,src,cache,context_dir,tf,fs,vdir,outcome_dir):
    t=time.time();asset=str(asset);src=Path(src);cache=Path(cache);context_dir=Path(context_dir);vdir=Path(vdir);outcome_dir=Path(outcome_dir);outcome_dir.mkdir(parents=True,exist_ok=True)
    srcs=r.verify_sources();auth=r.AUTH[asset]
    if sha_file(src)!=auth['src'] or sha_file(cache)!=auth['cache']:raise SystemExit('DATA_AUTH_FAIL')
    local=json.loads((vdir/'manifest_local.json').read_text());shard=r.shard_name(tf,fs)
    if local['asset']!=asset or local['shard']!=shard or local['raw_identities']!=r.EXPECTED_RAW or local.get('economic_results_present') is not False:raise SystemExit('V172_MANIFEST_BINDING_FAIL')
    z=np.load(cache);mm=np.memmap(src,dtype=ex.DT,mode='r')
    try:
        cnt,spr,ctxmeta=r.load_context(context_dir,asset,src,cache);mb=z['mb'];ks=('bo','bh','bl','bc') if fs=='BID' else ('mo','mh','ml','mc');A=sa.bars(mb,*[z[k] for k in ks],tf);B=sb.bars(mb,*[z[k] for k in ks],tf)
        if r.digest_arrays(A)!=r.digest_arrays(B):raise SystemExit('BAR_PARITY_FAIL')
        tc,sp=r.aggregate_contexts(mb,cnt,spr,tf);pa=sa.prepare(*A,sp,tc,asset);pb=sb.prepare(*B,sp,tc,asset)
        if not np.array_equal(np.nan_to_num(pa['management_atr14'],nan=-1.),np.nan_to_num(pb['management_atr14'],nan=-1.)):raise SystemExit('ATR_PARITY_FAIL')
        n=len(A[0]);ub=np.load(vdir/'union_buy.npy');us=np.load(vdir/'union_sell.npy');uB=np.unpackbits(ub.view(np.uint8),bitorder='little')[:n].astype(bool);uS=np.unpackbits(us.view(np.uint8),bitorder='little')[:n].astype(bool)
        if int(uB.sum())!=local['union_buy'] or int(uS.sum())!=local['union_sell']:raise SystemExit('UNION_COUNT_FAIL')
        ebars=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')];step=tf*60000
        oaB=ex.outcome_primary(mm['ts'],mm['bid'],mm['ask'],A[0],pa['management_atr14'],step,*ebars,uB,1);obB=ex.outcome_independent(mm['ts'],mm['bid'],mm['ask'],B[0],pb['management_atr14'],step,*ebars,uB,1)
        oaS=ex.outcome_primary(mm['ts'],mm['bid'],mm['ask'],A[0],pa['management_atr14'],step,*ebars,uS,-1);obS=ex.outcome_independent(mm['ts'],mm['bid'],mm['ask'],B[0],pb['management_atr14'],step,*ebars,uS,-1)
        for OA,OB,label in ((oaB,obB,'BUY'),(oaS,obS,'SELL')):
            for k in range(6):
                if not np.array_equal(OA[k],OB[k]):raise SystemExit(f'OUTCOME_PARITY_FAIL {label} {k}')
        for side,O in [('B',oaB),('S',oaS)]:
            for name,arr in zip(('et','xt','ei','xi','dist','rr'),O):np.save(outcome_dir/f'{side}_{name}.npy',arr,allow_pickle=False)
        meta={'schema':'QROS_G30_F13_V174_OUTCOME_CACHE_v1','asset':asset,'shard':shard,'bars':n,'bar_digest':r.digest_arrays(A),'union_buy':int(uB.sum()),'union_sell':int(uS.sum()),'raw_execution_parity':'PASS_EXACT','src_sha256':auth['src'],'cache_sha256':auth['cache'],'context_manifest':ctxmeta,'source_sha256':srcs,'economic_results_present':False,'future_2020_plus_pnl_read':False,'holdout_opened':False,'elapsed_s':time.time()-t}
        (outcome_dir/'manifest.json').write_text(json.dumps(safe(meta),sort_keys=True,separators=(',',':')));return meta
    finally:z.close()

def full_rec(uid,key,side,Wbuy,Wsell,words,arrays,mm,n):
    bits=np.unpackbits(words.view(np.uint8),bitorder='little')[:n].astype(bool);ids=np.flatnonzero(bits).astype(np.int64);ch=ex.select_a(ids,arrays['et'],arrays['xt']);chb=ex.select_b(ids,arrays['et'],arrays['xt'])
    if not np.array_equal(ch,chb):raise SystemExit('SELECT_PARITY_FAIL '+key+' '+side)
    rr=arrays['rr'][ch];ei=arrays['ei'][ch];xi=arrays['xi'][ch];dist=arrays['dist'][ch];et=arrays['et'][ch]
    if len(ch):
        spr=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spr,dist,out=np.zeros(len(spr)),where=dist>0);cons=rr-.5*extra;sev=rr-extra
    else:cons=rr.copy();sev=rr.copy()
    bb=np.unpackbits(Wbuy.view(np.uint8),bitorder='little')[:n].astype(bool);ss=np.unpackbits(Wsell.view(np.uint8),bitorder='little')[:n].astype(bool)
    return safe({'uid':int(uid),'id':key,'signal_sha256':ex.mask_digest(bb,ss),'side':side,'n':int(len(ch)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':ex.pf(rr),'pf_k':ex.pf(cons),'pf_s':ex.pf(sev),'r2018':float(rr[et<ex.CUT_2019].sum()),'r2019':float(rr[et>=ex.CUT_2019].sum()),'ledger_sha256':ex.ledger_sha(ch,arrays['et'],arrays['xt'],arrays['rr']),'pass':True})

def score_shard(asset,src,cache,context_dir,tf,fs,vdir,outcome_dir,out):
    t0=time.time();asset=str(asset);src=Path(src);cache=Path(cache);context_dir=Path(context_dir);vdir=Path(vdir);outcome_dir=Path(outcome_dir);out=Path(out)
    srcs=r.verify_sources();auth=r.AUTH[asset]
    if sha_file(src)!=auth['src'] or sha_file(cache)!=auth['cache']:raise SystemExit('DATA_AUTH_FAIL')
    local=json.loads((vdir/'manifest_local.json').read_text());shard=r.shard_name(tf,fs);unique=int(local['unique_masks']);vmap=np.load(vdir/'raw_to_uid.partial.npy',mmap_mode='r')
    if len(vmap)!=r.EXPECTED_RAW or int(vmap.max())!=unique or sha_file(vdir/'raw_to_uid.partial.npy')!=local['raw_to_uid_sha256']:raise SystemExit('V172_MAPPING_AUTH_FAIL')
    vdb=sqlite3.connect(vdir/'unique.sqlite');exp={int(u):d for u,d in vdb.execute('select uid,digest from unique_masks')};vdb.close()
    if len(exp)!=unique:raise SystemExit('V172_UNIQUE_DB_FAIL')
    om=json.loads((outcome_dir/'manifest.json').read_text())
    if om['asset']!=asset or om['shard']!=shard or om['raw_execution_parity']!='PASS_EXACT':raise SystemExit('OUTCOME_CACHE_BINDING_FAIL')
    MBmet,Barr,mm=load_exec_metrics(outcome_dir,'B',src);MSmet,Sarr,mm2=load_exec_metrics(outcome_dir,'S',src);eval_words(np.zeros(1,np.uint64),1,*[np.zeros(1,dtype=x.dtype) for x in MBmet],CTZ16)
    z=np.load(cache)
    try:
        cnt,spr,ctxmeta=r.load_context(context_dir,asset,src,cache);mb=z['mb'];ks=('bo','bh','bl','bc') if fs=='BID' else ('mo','mh','ml','mc');A=fl.bars(mb,*[z[k] for k in ks],tf);tc,sp=r.aggregate_contexts(mb,cnt,spr,tf);fp=fl.prepare(A,tc,sp,asset);st=fl.prepack(fp,A);shocks=fl.shock_cache(fp,A);n=st['n']
        if n!=local['bars'] or n!=len(MBmet[0]):raise SystemExit('BAR_COUNT_FAIL')
        raw=0;seen=0;decision=np.zeros(unique+1,np.uint8);passers=[];palias={};metric_h=hashlib.sha256();verified_digests=0
        for pair in PAIRS:
            q=sa.pair_params(pair)
            for timing in sa.TIM:
                for th in sa.TH:
                    shock=shocks[(q['shock_measure'],int(q['atr_period']),q['atr_smoothing'],timing,float(th))];BM,SM=fl.generate18(st,shock,pair)
                    for k,(fam,nv) in enumerate(PERS):
                        raw+=1;uid=int(vmap[raw-1]);pd=fl.mask_digest(BM[k],SM[k],n)
                        if pd!=exp[uid]:raise SystemExit(f'FULL_V172_DIGEST_PARITY_FAIL raw={raw} uid={uid}')
                        verified_digests+=1;key=r.identity_key(pair,timing,th,fam,nv)
                        if uid<=seen:
                            if uid in palias:palias[uid].append(key)
                            continue
                        if uid!=seen+1:raise SystemExit(f'UID_FIRST_OCCURRENCE_ORDER_FAIL {uid} {seen}')
                        seen=uid;b=eval_words(BM[k],n,*MBmet,CTZ16);s=eval_words(SM[k],n,*MSmet,CTZ16)
                        for code,m in ((1,b),(2,s)):metric_h.update(struct.pack('<IBi8dB',uid,code,int(m[0]),*[float(x) for x in m[1:9]],1 if m[9] else 0))
                        if b[-1] or s[-1]:palias[uid]=[key]
                        if b[-1]:decision[uid]|=1;passers.append(full_rec(uid,key,'BUY',BM[k],SM[k],BM[k],Barr,mm,n))
                        if s[-1]:decision[uid]|=2;passers.append(full_rec(uid,key,'SELL',BM[k],SM[k],SM[k],Sarr,mm,n))
        if raw!=r.EXPECTED_RAW or seen!=unique or verified_digests!=r.EXPECTED_RAW:raise SystemExit('FULL_ENUMERATION_FAIL')
        for rec in passers:rec['aliases']=palias[int(rec['uid'])]
        obj={'schema':SCHEMA,'campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F13_PAIRWISE_INTERACTIONS','asset':asset,'shard':shard,'scope':'EXPOSED_DEV_2018_2019_ONLY_NO_2020_PLUS_PNL','raw_identities':raw,'unique_masks':unique,'exact_alias_count':raw-unique,'evaluated_configurations':2*unique,'full_v172_raw_digest_comparisons':verified_digests,'signal_parity':'PASS_EXACT_V172_DIGEST_EVERY_RAW_IDENTITY','trade_semantics':'FROZEN_V171_OUTCOMES_DUAL_PARITY','full_metrics_root_sha256':metric_h.hexdigest(),'gate_decision_vector_sha256':hashlib.sha256(decision[1:].tobytes()).hexdigest(),'passed':len(passers),'passed_buy':sum(x['side']=='BUY' for x in passers),'passed_sell':sum(x['side']=='SELL' for x in passers),'passers':passers,'all_gate_passers_advance':True,'source_sha256':srcs,'v172_mapping_sha256':local['raw_to_uid_sha256'],'v172_unique_mask_set_sha256':local['unique_mask_set_sha256'],'future_pnl_read':False,'historical_holdout_opened':False,'retuning':False,'mt5':False,'status':'PASS','elapsed_s':time.time()-t0}
        out.write_text(json.dumps(safe(obj),sort_keys=True,separators=(',',':'),allow_nan=False));print(json.dumps({k:obj[k] for k in ('asset','shard','unique_masks','evaluated_configurations','passed','passed_buy','passed_sell','elapsed_s')},sort_keys=True));return obj
    finally:z.close()

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
    for name in ('build-outcomes','score'):
        p=sub.add_parser(name);p.add_argument('--asset',choices=sorted(r.AUTH),required=True);p.add_argument('--src',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--context-dir',type=Path,required=True);p.add_argument('--tf',type=int,choices=[1,5,10,15,30,60],required=True);p.add_argument('--feature-side',choices=['BID','MID'],required=True);p.add_argument('--v172-dir',type=Path,required=True);p.add_argument('--outcome-dir',type=Path,required=True)
        if name=='score':p.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    if a.cmd=='build-outcomes':print(json.dumps(safe(build_outcomes(a.asset,a.src,a.cache,a.context_dir,a.tf,a.feature_side,a.v172_dir,a.outcome_dir)),sort_keys=True,separators=(',',':')))
    else:score_shard(a.asset,a.src,a.cache,a.context_dir,a.tf,a.feature_side,a.v172_dir,a.outcome_dir,a.out)
if __name__=='__main__':main()
