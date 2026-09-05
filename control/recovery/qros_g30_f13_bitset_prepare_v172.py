#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, fcntl, hashlib, json, math, os, pickle, sqlite3, sys, time
from pathlib import Path
import numpy as np
from numba import njit

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import qros_g30_f13_primary_v171 as sa
import qros_g30_f13_independent_v171 as sb
import qros_g30_f10_exec_core_v127 as ex
import qros_g30_f13_transactional_v171 as old

RAW_PER_PAIR=324
SEMANTIC_FUNCTIONS=('pack_bool','tail_mask','shift_fwd','refractory_words','refractory_matrix','mask_digest_packed','old_digest_from_words','build_bar_inputs','primitive_prep','prepack_static','shift_fwd_matrix','confirm_matrix','generate_18','audit_against_v171')
SEMANTIC_CORE_SHA256='2db4b70c3e5e59a9eec2c6bc6ecc72452fc5b1c3d3645c2ea1ac1ee167744cc1'
PERS=list(sa.persistence_specs())
assert len(PERS)==18
PAIR_SPECS=list(old.pair_specs())
assert len(PAIR_SPECS)==2229

# Canonical packed mask: little-endian bit i corresponds to signal bar i.
def pack_bool(x:np.ndarray)->np.ndarray:
    b=np.packbits(np.asarray(x,dtype=np.uint8), bitorder='little')
    pad=(-len(b))%8
    if pad:b=np.pad(b,(0,pad))
    return np.ascontiguousarray(b).view('<u8')

def tail_mask(n:int)->np.uint64:
    r=n&63
    return np.uint64((1<<r)-1) if r else np.uint64(0xFFFFFFFFFFFFFFFF)

def shift_fwd(w:np.ndarray,j:int,n:int)->np.ndarray:
    if j==0:return w.copy()
    z=np.empty_like(w);z[0]=w[0]<<np.uint64(j)
    if len(w)>1:z[1:]=(w[1:]<<np.uint64(j)) | (w[:-1]>>np.uint64(64-j))
    z[-1]&=tail_mask(n);return z

CTZ16=np.empty(65536,np.uint8);CTZ16[0]=0
for _i in range(1,65536):CTZ16[_i]=((_i & -_i).bit_length()-1)

@njit(cache=True)
def refractory_words(words,r,nbits,ctz):
    out=np.zeros(len(words),np.uint64);last=-10**12
    for wi in range(len(words)):
        w=words[wi]
        while w!=0:
            lo=int(w & np.uint64(65535))
            if lo:off=int(ctz[lo])
            else:
                lo=int((w>>np.uint64(16)) & np.uint64(65535))
                if lo:off=16+int(ctz[lo])
                else:
                    lo=int((w>>np.uint64(32)) & np.uint64(65535))
                    if lo:off=32+int(ctz[lo])
                    else:off=48+int(ctz[int((w>>np.uint64(48)) & np.uint64(65535))])
            idx=wi*64+off
            if idx>=nbits:break
            if idx-last>r:
                out[wi] |= np.uint64(1)<<np.uint64(off);last=idx
            w &= w-np.uint64(1)
    return out

@njit(cache=True)
def refractory_matrix(mat,r,nbits,ctz):
    out=np.zeros(mat.shape,np.uint64)
    for row in range(mat.shape[0]):
        last=-10**12
        for wi in range(mat.shape[1]):
            w=mat[row,wi]
            while w!=0:
                lo=int(w & np.uint64(65535))
                if lo:off=int(ctz[lo])
                else:
                    lo=int((w>>np.uint64(16)) & np.uint64(65535))
                    if lo:off=16+int(ctz[lo])
                    else:
                        lo=int((w>>np.uint64(32)) & np.uint64(65535))
                        if lo:off=32+int(ctz[lo])
                        else:off=48+int(ctz[int((w>>np.uint64(48)) & np.uint64(65535))])
                idx=wi*64+off
                if idx>=nbits:break
                if idx-last>r:
                    out[row,wi] |= np.uint64(1)<<np.uint64(off);last=idx
                w &= w-np.uint64(1)
    return out

def mask_digest_packed(b:np.ndarray,s:np.ndarray,n:int)->str:
    h=hashlib.sha256();h.update(np.int64(n).tobytes());h.update(memoryview(np.ascontiguousarray(b)).cast('B'));h.update(memoryview(np.ascontiguousarray(s)).cast('B'));return h.hexdigest()

def old_digest_from_words(b,s,n):
    bb=np.unpackbits(b.view(np.uint8),bitorder='little')[:n].astype(bool)
    ss=np.unpackbits(s.view(np.uint8),bitorder='little')[:n].astype(bool)
    return ex.mask_digest(bb,ss)

def build_bar_inputs(cache,tf,fs):
    z=np.load(cache);mb=z['mb'];ks=('bo','bh','bl','bc') if fs=='BID' else ('mo','mh','ml','mc');vals=[z[k] for k in ks]
    A=sa.bars(mb,*vals,tf);B=sb.bars(mb,*vals,tf)
    if old.digest_arrays(A)!=old.digest_arrays(B):raise SystemExit('BAR_PARITY_FAIL')
    return z,mb,A,B

def primitive_prep(A,tc,sp,asset):
    pa=sa.prepare(*A,sp,tc,asset);n=len(A[0]);shock_words={}
    shock_params=set()
    for pair in PAIR_SPECS:
        q=sa.pair_params(pair);shock_params.add((q['shock_measure'],int(q['atr_period']),q['atr_smoothing']))
    for meas,p,sm in sorted(shock_params):
        a1=sa.atr(A[2],A[3],A[4],p,sm);num1=pa['numerators'][meas]
        for timing in sa.TIM:
            den1=a1 if timing==sa.TIM[0] else np.r_[np.nan,a1[:-1]]
            r1=np.divide(num1,den1,out=np.full(n,np.nan),where=np.isfinite(num1)&np.isfinite(den1)&(den1>0))
            for th in sa.TH:
                m1=(r1>=th)&(pa['weekday']<5);shock_words[(meas,p,sm,timing,float(th))]=pack_bool(m1)
    return pa,shock_words

def prepack_static(pa,A):
    n=len(A[0]);Pbuy=[];Psell=[]
    for fam,nv in PERS:
        if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':b=A[4]>A[1];s=A[4]<A[1]
        else:b,s=pa['bases'][(fam,nv)]
        Pbuy.append(pack_bool(b));Psell.append(pack_bool(s))
    d={
      'pers_buy':np.stack(Pbuy),'pers_sell':np.stack(Psell),
      'loc':{k:(pack_bool(v[0]),pack_bool(v[1])) for k,v in pa['loc'].items()},
      'wick':{k:(pack_bool(v[0]),pack_bool(v[1])) for k,v in pa['wick'].items()},
      'vol':{k:pack_bool(v) for k,v in pa['vol_ctx'].items()},
      'spread':{k:pack_bool(v) for k,v in pa['spread_ctx'].items()},
      'tick':{k:pack_bool(v) for k,v in pa['tick_ctx'].items()},
      'day':{name:pack_bool(pa['weekday']==i) for i,name in enumerate(sa.DOW)},
    }
    o,h,l,c=A[1],A[2],A[3],A[4];bucket=A[0];step=int(bucket[1]-bucket[0]) if n>1 else 0
    bad=np.zeros(n,np.int64);bad[1:]=(bucket[1:]-bucket[:-1]!=step).astype(np.int64);pref=np.cumsum(bad)
    conf={}
    variants=[('NEXT_BAR_DIRECTIONAL_CLOSE',w) for w in (1,2,3)]+[('NEXT_BAR_BREAK_SHOCK_EXTREME',w) for w in (1,2,3)]+[('TWO_BAR_CONTINUATION',w) for w in (2,3)]
    for kind,w in variants:
      js=range(1,w+1) if kind!='TWO_BAR_CONTINUATION' else range(2,w+1)
      for side in (1,-1):
       for j in js:
        origin=np.zeros(n,bool)
        contiguous=(pref[j:]-pref[:-j])==0
        if kind=='NEXT_BAR_DIRECTIONAL_CLOSE':cond=(c[j:]>o[j:]) if side==1 else (c[j:]<o[j:])
        elif kind=='NEXT_BAR_BREAK_SHOCK_EXTREME':cond=(h[j:]>h[:-j]) if side==1 else (l[j:]<l[:-j])
        else:
         if side==1:cond=(c[j-1:-1]>o[j-1:-1])&(c[j:]>o[j:])&(c[j:]>c[j-1:-1])&(c[j-1:-1]>c[:-j])
         else:cond=(c[j-1:-1]<o[j-1:-1])&(c[j:]<o[j:])&(c[j:]<c[j-1:-1])&(c[j-1:-1]<c[:-j])
        origin[:-j]=contiguous&cond;conf[(kind,w,side,j)]=pack_bool(origin)
    d['conf']=conf;d['n']=n;d['tail']=tail_mask(n);return d

def shift_fwd_matrix(M:np.ndarray,j:int,n:int)->np.ndarray:
    if j==0:return M.copy()
    z=np.empty_like(M);z[:,0]=M[:,0]<<np.uint64(j)
    if M.shape[1]>1:z[:,1:]=(M[:,1:]<<np.uint64(j)) | (M[:,:-1]>>np.uint64(64-j))
    z[:,-1]&=tail_mask(n);return z

def confirm_matrix(base,static,kind,w,side):
    rem=base.copy();out=np.zeros_like(base);n=static['n']
    js=range(1,w+1) if kind!='TWO_BAR_CONTINUATION' else range(2,w+1)
    for j in js:
        cand=rem & static['conf'][(kind,w,side,j)][None,:]
        out |= shift_fwd_matrix(cand,j,n)
        rem &= ~cand
    out[:,-1]&=static['tail'];return out

def generate_18(static,shock,pair):
    q=sa.pair_params(pair)
    bbase=shock.copy();sbase=shock.copy()
    if q['close_location_filter'] is not None:
      x,y=static['loc'][q['close_location_filter']];bbase&=x;sbase&=y
    if q['wick_filter'] is not None:
      x,y=static['wick'][q['wick_filter']];bbase&=x;sbase&=y
    if q['volatility_regime_context'] is not None:
      x=static['vol'][(q['volatility_regime_context'],q['volatility_lookback'])];bbase&=x;sbase&=x
    if q['spread_context'] is not None:
      x=static['spread'][(q['spread_context'],q['spread_lookback'])];bbase&=x;sbase&=x
    if q['tick_intensity_context'] is not None:
      x=static['tick'][(q['tick_intensity_context'],q['tick_intensity_lookback'])];bbase&=x;sbase&=x
    B=static['pers_buy'] & bbase[None,:];S=static['pers_sell'] & sbase[None,:]
    if q['post_shock_confirmation'] is not None:
      B=confirm_matrix(B,static,q['post_shock_confirmation'],q['confirmation_window_bars'],1)
      S=confirm_matrix(S,static,q['post_shock_confirmation'],q['confirmation_window_bars'],-1)
    if q['day_of_week'] is not None:
      dw=static['day'][q['day_of_week']];B&=dw[None,:];S&=dw[None,:]
    if q['event_refractory_bars']:
      r=int(q['event_refractory_bars'])
      B=refractory_matrix(B,r,static['n'],CTZ16);S=refractory_matrix(S,r,static['n'],CTZ16)
    B[:,-1]&=static['tail'];S[:,-1]&=static['tail'];return B,S

def audit_against_v171(pa,static,shock_words,A,pair_indices):
    checks=0;root=hashlib.sha256()
    for pi in pair_indices:
      pair=PAIR_SPECS[pi];q=sa.pair_params(pair)
      for timing in (sa.TIM[0],):
       for th in (2.0,):
        shock=shock_words[(q['shock_measure'],int(q['atr_period']),q['atr_smoothing'],timing,float(th))]
        MB,MS=generate_18(static,shock,pair)
        high_risk=('F07_POST_SHOCK_CONFIRMATION' in pair['frontiers']) or ('F11_REFRACTORY' in pair['frontiers'])
        ks=(0,8,17) if high_risk else (0,)
        for k in ks:
          fam,nv=PERS[k]
          ba,ss=sa.mask(pa,pair,timing,th,fam,nv)
          x=pack_bool(ba);y=pack_bool(ss)
          if not np.array_equal(x,MB[k]) or not np.array_equal(y,MS[k]):raise SystemExit(f'BITSET_V171_PARITY_FAIL pair={pi} {timing} {th} {fam} {nv}')
          root.update(bytes.fromhex(mask_digest_packed(MB[k],MS[k],static['n'])));checks+=1
    return checks,root.hexdigest()

def compute_semantic_core_sha256(path:Path)->str:
    tree=ast.parse(path.read_text())
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in SEMANTIC_FUNCTIONS]
    if len(nodes)!=len(SEMANTIC_FUNCTIONS) or {n.name for n in nodes}!=set(SEMANTIC_FUNCTIONS):raise SystemExit('SEMANTIC_CORE_FUNCTION_SET_MISMATCH')
    blob='\n'.join(ast.dump(n,annotate_fields=True,include_attributes=False) for n in nodes).encode()
    return hashlib.sha256(blob).hexdigest()

def semantic_cache_binding(asset,tf,fs,auth,ctxmeta,srcs):
    return {'asset':asset,'tf':int(tf),'feature_side':fs,'semantic_core_sha256':SEMANTIC_CORE_SHA256,'dev_sha256':auth['src'],'bar_cache_sha256':auth['cache'],'tick_count_sha256':ctxmeta['tick_count_sha256'],'spread_m1_sha256':ctxmeta['spread_m1_sha256'],'frozen_sources':srcs}

def save_semantic_cache(work,binding,static,shock_words,checks,audit_root):
    obj={'static':static,'shock_words':shock_words};raw=pickle.dumps(obj,protocol=5);rsha=hashlib.sha256(raw).hexdigest()
    cp=work/'semantic_precomp_v172.pkl';tmp=cp.with_suffix('.tmp');tmp.write_bytes(raw);os.replace(tmp,cp)
    meta={'schema':'QROS_G30_F13_EPHEMERAL_SEMANTIC_PRECOMP_V172_v1','binding':binding,'raw_sha256':rsha,'bytes':len(raw),'audit_checks':int(checks),'audit_root_sha256':audit_root,'economic_results_present':False}
    mp=work/'semantic_precomp_v172.json';mt=mp.with_suffix('.tmp');mt.write_text(json.dumps(meta,sort_keys=True,separators=(',',':')));os.replace(mt,mp);return meta

def load_semantic_cache(work,binding):
    cp=work/'semantic_precomp_v172.pkl';mp=work/'semantic_precomp_v172.json'
    if not (cp.exists() and mp.exists()):return None
    meta=json.loads(mp.read_text())
    if meta.get('binding')!=binding:return None
    raw=cp.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=meta.get('raw_sha256'):raise SystemExit('SEMANTIC_PRECOMP_SHA_MISMATCH')
    return pickle.loads(raw),meta

def prepare_fast(a):
    t0=time.time();actual_sem=compute_semantic_core_sha256(Path(__file__))
    if actual_sem!=SEMANTIC_CORE_SHA256:raise SystemExit(f'SEMANTIC_CORE_SHA_MISMATCH {actual_sem}')
    a.work.mkdir(parents=True,exist_ok=True);lockfh=(a.work/'.prepare.lock').open('a+')
    try:fcntl.flock(lockfh.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('PREPARE_WORKDIR_LOCKED')
    print('STAGE verify_sources',flush=True);srcs=old.verify_sources();auth=old.AUTH[a.asset]
    if old.sha_file(a.src)!=auth['src'] or old.sha_file(a.cache)!=auth['cache']:raise SystemExit('DATA_SHA_MISMATCH')
    cnt_m1,spr_m1,ctxmeta=old.load_context(a.context_dir,a.asset,a.src,a.cache);print('STAGE context_loaded',round(time.time()-t0,3),flush=True)
    z=None
    try:
      pair_group_first=[];seen=set()
      for i,p in enumerate(PAIR_SPECS):
        key=tuple(p['frontiers'])
        if key not in seen:seen.add(key);pair_group_first.append(i)
      audit_indices=sorted(set([0,len(PAIR_SPECS)-1]+pair_group_first))
      dbp=a.work/'unique.sqlite';map_p=a.work/'raw_to_uid.partial.npy';statep=a.work/'fast_prepare_state.json';prest=json.loads(statep.read_text()) if statep.exists() else None
      binding=semantic_cache_binding(a.asset,a.tf,a.feature_side,auth,ctxmeta,srcs);cached=load_semantic_cache(a.work,binding)
      if cached is not None:
        obj,cmeta=cached;static=obj['static'];shock_words=obj['shock_words'];n=int(static['n']);checks=int(cmeta['audit_checks']);audit_root=cmeta['audit_root_sha256']
        if prest is not None and (prest.get('audit_root_sha256')!=audit_root or int(prest.get('audit_checks',-1))!=checks):raise SystemExit('SEMANTIC_PRECOMP_CHECKPOINT_AUDIT_MISMATCH')
        print('STAGE semantic_precomp_loaded',cmeta['bytes'],round(time.time()-t0,3),flush=True)
      else:
        z,mb,A,B=build_bar_inputs(a.cache,a.tf,a.feature_side);tc,sp=old.aggregate_contexts(mb,cnt_m1,spr_m1,a.tf);print('STAGE aggregated',round(time.time()-t0,3),flush=True)
        pa,shock_words=primitive_prep(A,tc,sp,a.asset);print('STAGE primitives',round(time.time()-t0,3),flush=True);static=prepack_static(pa,A);n=static['n'];print('STAGE static_packed',round(time.time()-t0,3),flush=True)
        if prest is not None and prest.get('semantic_core_sha256')==SEMANTIC_CORE_SHA256:checks=int(prest['audit_checks']);audit_root=prest['audit_root_sha256'];print('STAGE directed_audit_reused',checks,round(time.time()-t0,3),flush=True)
        else:
          checks,audit_root=audit_against_v171(pa,static,shock_words,A,audit_indices);print('STAGE directed_audit',checks,round(time.time()-t0,3),flush=True)
          if prest is not None and prest.get('audit_root_sha256') not in (None,audit_root):raise SystemExit('CHECKPOINT_AUDIT_ROOT_CHANGED')
        cmeta=save_semantic_cache(a.work,binding,static,shock_words,checks,audit_root);print('STAGE semantic_precomp_saved',cmeta['bytes'],round(time.time()-t0,3),flush=True)
      db=sqlite3.connect(dbp);db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=NORMAL');db.execute('CREATE TABLE IF NOT EXISTS unique_masks(uid INTEGER PRIMARY KEY,digest TEXT UNIQUE NOT NULL,canonical_raw_idx INTEGER NOT NULL)');db.commit()
      if statep.exists():
        st=json.loads(statep.read_text());start_group=int(st['next_group']);raw_done=int(st['raw_done'])
        if raw_done!=start_group*RAW_PER_PAIR:raise SystemExit(f'CHECKPOINT_RAW_GROUP_MISMATCH {raw_done} {start_group}')
        if st.get('audit_root_sha256')!=audit_root or int(st.get('audit_checks',-1))!=checks:raise SystemExit('CHECKPOINT_AUDIT_IDENTITY_MISMATCH')
        raw_to_uid=np.lib.format.open_memmap(map_p,mode='r+');db.execute('DELETE FROM unique_masks WHERE canonical_raw_idx>?',(raw_done,));db.commit()
        q=db.execute('SELECT COUNT(*),COALESCE(MIN(uid),0),COALESCE(MAX(uid),0),COALESCE(MAX(canonical_raw_idx),0) FROM unique_masks').fetchone();cnt,umin,umax,rmax=map(int,q);unique=cnt
        if cnt and (umin!=1 or umax!=cnt):raise SystemExit(f'CHECKPOINT_UID_NOT_CONTIGUOUS {q}')
        if rmax>raw_done:raise SystemExit(f'CHECKPOINT_DB_RAW_AHEAD_AFTER_TRUNCATE {rmax}>{raw_done}')
        head=np.asarray(raw_to_uid[:raw_done])
        if raw_done and (np.any(head==0) or int(head.max())>unique):raise SystemExit('CHECKPOINT_MAPPING_HEAD_INVALID')
        raw_to_uid[raw_done:]=0;raw_to_uid.flush();ub=np.load(a.work/'union_buy.partial.npy');us=np.load(a.work/'union_sell.partial.npy')
        if len(ub)!=len(static['pers_buy'][0]) or len(us)!=len(ub):raise SystemExit('CHECKPOINT_UNION_SHAPE_MISMATCH')
        state_changed=False;repair={'unique':unique,'audit_checks':checks,'audit_root_sha256':audit_root,'semantic_core_sha256':SEMANTIC_CORE_SHA256,'engine_source_sha256':old.sha_file(Path(__file__))}
        for rk,rv in repair.items():
          if st.get(rk)!=rv:st[rk]=rv;state_changed=True
        if state_changed:
          tmp=statep.with_suffix('.tmp');tmp.write_text(json.dumps(st,sort_keys=True,separators=(',',':')));os.replace(tmp,statep)
          print(json.dumps({'checkpoint_reconciled':True,'raw_done':raw_done,'unique':unique,'semantic_core_sha256':SEMANTIC_CORE_SHA256},sort_keys=True),flush=True)
      else:
        start_group=0;unique=0;raw_to_uid=np.lib.format.open_memmap(map_p,mode='w+',dtype=np.uint32,shape=(old.EXPECTED_RAW,));raw_to_uid[:]=0;ub=np.zeros(len(static['pers_buy'][0]),np.uint64);us=np.zeros_like(ub)
      raw_index=start_group*RAW_PER_PAIR;end_group=len(PAIR_SPECS) if a.max_groups_per_run<=0 else min(len(PAIR_SPECS),start_group+a.max_groups_per_run)
      for gi in range(start_group,end_group):
        pair=PAIR_SPECS[gi];q=sa.pair_params(pair);batch=[]
        for timing in sa.TIM:
          for th in sa.TH:
            shock=shock_words[(q['shock_measure'],int(q['atr_period']),q['atr_smoothing'],timing,float(th))];MB,MS=generate_18(static,shock,pair);ub |= np.bitwise_or.reduce(MB,axis=0);us |= np.bitwise_or.reduce(MS,axis=0)
            for k in range(18):raw_index+=1;batch.append((raw_index,mask_digest_packed(MB[k],MS[k],n)))
        ordered_unique=list(dict.fromkeys(d for _,d in batch));marks=','.join('?' for _ in ordered_unique);existing={} if not ordered_unique else {d:int(u) for d,u in db.execute(f'SELECT digest,uid FROM unique_masks WHERE digest IN ({marks})',ordered_unique)};newrows=[]
        for ridx,d in batch:
          uid=existing.get(d)
          if uid is None:unique+=1;uid=unique;existing[d]=uid;newrows.append((uid,d,ridx))
          raw_to_uid[ridx-1]=uid
        if newrows:db.executemany('INSERT INTO unique_masks(uid,digest,canonical_raw_idx) VALUES(?,?,?)',newrows)
        if (gi+1)%a.checkpoint_groups==0 or gi+1==end_group or gi+1==len(PAIR_SPECS):
          db.commit();raw_to_uid.flush();old.atomic_npy(a.work/'union_buy.partial.npy',ub);old.atomic_npy(a.work/'union_sell.partial.npy',us)
          st={'schema':'QROS_G30_F13_FAST_PREPARE_STATE_V172_v1','asset':a.asset,'shard':old.shard_name(a.tf,a.feature_side),'next_group':gi+1,'raw_done':raw_index,'unique':unique,'audit_checks':checks,'audit_root_sha256':audit_root,'semantic_core_sha256':SEMANTIC_CORE_SHA256,'engine_source_sha256':old.sha_file(Path(__file__)),'status':'RUNNING' if gi+1<len(PAIR_SPECS) else 'COMPLETE_NO_ECONOMIC_SCORING'};tmp=statep.with_suffix('.tmp');tmp.write_text(json.dumps(st,sort_keys=True,separators=(',',':')));os.replace(tmp,statep)
          print(json.dumps({'group':gi+1,'groups':len(PAIR_SPECS),'raw_done':raw_index,'unique':unique,'elapsed_s':round(time.time()-t0,3)},sort_keys=True),flush=True)
      if end_group<len(PAIR_SPECS):print(json.dumps({'status':'PARTIAL_CHECKPOINT_CLEAN','next_group':end_group,'raw_done':raw_index,'unique':unique},sort_keys=True),flush=True);return
      if raw_index!=old.EXPECTED_RAW:raise SystemExit(f'RAW_COUNT_FAIL {raw_index}')
      db.commit();dig=[x[0] for x in db.execute('SELECT digest FROM unique_masks ORDER BY digest')];set_root=hashlib.sha256(('\n'.join(dig)+'\n').encode()).hexdigest();raw_to_uid.flush();map_sha=old.sha_file(map_p)
      obj={'schema':'QROS_G30_F13_FAST_PREPARED_SHARD_V172_v1','asset':a.asset,'shard':old.shard_name(a.tf,a.feature_side),'bars':n,'raw_identities':raw_index,'unique_masks':unique,'exact_alias_count':raw_index-unique,'packed_mask_semantics':'LITTLE_ENDIAN_BIT_I_EQUALS_SIGNAL_BAR_I; SHA256(INT64_NBARS||BUY_WORD_BYTES||SELL_WORD_BYTES)','unique_mask_set_sha256':set_root,'raw_to_uid_sha256':map_sha,'union_buy':int(np.unpackbits(ub.view(np.uint8),bitorder='little')[:n].sum()),'union_sell':int(np.unpackbits(us.view(np.uint8),bitorder='little')[:n].sum()),'source_sha256':srcs,'context_manifest':ctxmeta,'independence_authority':{'parent_real_parity':'F02_F12_PRIOR_GATE_A_RECEIPTS_PASS_EXACT_ON_SAME_DEV','f13_independent_composition':'V171_SYNTHETIC_1444392_MASKS_PASS_EXACT'},'v172_prepare_source_sha256':old.sha_file(Path(__file__)),'internal_directed_real_data_audit':{'pair_groups_total':55,'pair_indices_tested':len(audit_indices),'timings_tested':[sa.TIM[0]],'thresholds_tested':[2.0],'persistence_rule':'NON_HIGH_RISK_K0; F07_OR_F11_K0_K8_K17','buy_sell_masks_per_identity':2,'identity_checks':checks,'status':'PASS_EXACT','root_sha256':audit_root},'external_expanded_real_data_audit_ref':'QROS_G30_F13_V172_REAL_DATA_EQUIVALENCE_AUDIT_v1.json','economic_results_present':False,'status':'PREPARED_FAST_NO_ECONOMIC_SCORING','elapsed_s':round(time.time()-t0,3)}
      (a.work/'manifest_fast.json').write_text(json.dumps(obj,sort_keys=True,separators=(',',':')));print(json.dumps(obj,sort_keys=True,separators=(',',':')))
    finally:
      if z is not None:z.close()
      try:fcntl.flock(lockfh.fileno(),fcntl.LOCK_UN)
      finally:lockfh.close()

def main():
 p=argparse.ArgumentParser();p.add_argument('--asset',choices=sorted(old.AUTH),required=True);p.add_argument('--src',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--context-dir',type=Path,required=True);p.add_argument('--tf',type=int,choices=[1,5,10,15,30,60],required=True);p.add_argument('--feature-side',choices=['BID','MID'],required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--checkpoint-groups',type=int,default=10);p.add_argument('--max-groups-per-run',type=int,default=0);a=p.parse_args();prepare_fast(a)
if __name__=='__main__':main()
