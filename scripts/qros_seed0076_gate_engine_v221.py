from __future__ import annotations
import json, datetime as _dt
from zoneinfo import ZoneInfo
from pathlib import Path
import numpy as np

LADDER=['M5','M15','H1','H4','D1','W1']
TF_MIN={'M1':1,'M2':2,'M3':3,'M4':4,'M5':5,'M6':6,'M10':10,'M12':12,'M15':15,'M20':20,'M30':30,'H1':60,'H2':120,'H3':180,'H4':240,'D1':1440,'W1':10080}
NY=ZoneInfo('America/New_York'); LONDON=ZoneInfo('Europe/London')

def _valid_idx(idx,n): return (idx>=0)&(idx<n)
def _safe(arr,idx):
    out=np.full(len(idx),np.nan);v=_valid_idx(idx,len(arr));out[v]=arr[idx[v]];return out

def trend_eval(ind,idx,side,variant):
    idx=np.asarray(idx,dtype=np.int64); fast,mid,slow=map(int,variant['ema_triple']);mode=variant['mode']
    ef=_safe(ind[f'EMA{fast}'],idx);em=_safe(ind[f'EMA{mid}'],idx);es=_safe(ind[f'EMA{slow}'],idx)
    close=None
    if side=='BUY': ok=(ef>em)&(em>es)
    else: ok=(ef<em)&(em<es)
    if mode.startswith('PRICE_'):
        close=_safe(ind['_CLOSE'],idx);ok &= (close>ef if side=='BUY' else close<ef)
    if mode.endswith('_SLOPE'):
        ip=idx-1;pf=_safe(ind[f'EMA{fast}'],ip);pm=_safe(ind[f'EMA{mid}'],ip);ps=_safe(ind[f'EMA{slow}'],ip)
        if side=='BUY':ok &= (ef>pf)&(em>pm)&(es>ps)
        else:ok &= (ef<pf)&(em<pm)&(es<ps)
    return ok & ~np.isnan(ef)&~np.isnan(em)&~np.isnan(es)

def geometry_eval(ind,idx,bar_idx,side,variant,sh,sl,boxhist,active_trend=None):
    idx=np.asarray(idx,np.int64);bar_idx=np.asarray(bar_idx,np.int64);n=len(idx);ok=np.ones(n,dtype=bool)
    valid=_valid_idx(bar_idx,len(sh))&_valid_idx(idx,len(ind['ATR14']));ok &= valid
    fh=_safe(sh,bar_idx);fl=_safe(sl,bar_idx);atr=_safe(ind['ATR14'],idx);ok &= ~np.isnan(fh)&~np.isnan(fl)
    cn=variant['contraction_n'];mba=variant['max_box_atr'];mm=variant['max_midpoint_to_fast_ema_atr']
    if cn!='OFF':
        k=int(cn); vals=np.full((n,k),np.nan)
        vv=valid.copy(); vals[vv]=boxhist[bar_idx[vv],-k:]
        ok &= ~np.isnan(vals).any(axis=1)
        for j in range(k-1):ok &= vals[:,j]>vals[:,j+1]
    if mba!='OFF':ok &= (atr>0)&(np.abs(fh-fl)/atr<=float(mba))
    if mm!='OFF':
        fast=int(active_trend['ema_triple'][0]) if active_trend else 35
        ef=_safe(ind[f'EMA{fast}'],idx);mid=(fh+fl)/2.0
        ok &= (atr>0)&~np.isnan(ef)&(np.abs(mid-ef)/atr<=float(mm))
    return ok

def volatility_eval(ind,idx,variant):
    a=_safe(ind['ATR14'],idx);b=_safe(ind['ATR50'],idx);r=np.divide(a,b,out=np.full(len(idx),np.nan),where=b>0);th=float(variant['threshold'])
    return (r>th) if variant['rule']=='ATR_FAST_SLOW_GT' else (r<th)

def momentum_eval(ind,idx,side,variant):
    rule=variant['rule']
    if rule=='RSI14_DIRECTIONAL':
        x=_safe(ind['RSI14'],idx);return x>=float(variant['buy_min']) if side=='BUY' else x<=float(variant['sell_max'])
    if rule=='ROC5_SIGN_ALIGNED':x=_safe(ind['ROC5'],idx);return x>0 if side=='BUY' else x<0
    if rule=='CCI20_SIGN_ALIGNED':x=_safe(ind['CCI20'],idx);return x>0 if side=='BUY' else x<0
    if rule=='STOCH14_3_DIRECTIONAL_50':x=_safe(ind['STOCH14_3'],idx);return x>50 if side=='BUY' else x<50
    raise ValueError(rule)

def trend_strength_eval(ind,idx,side,variant):
    rule=variant['rule'];th=float(variant['threshold'])
    if rule=='ADX14_GE':return _safe(ind['ADX14'],idx)>=th
    e=_safe(ind['EMA20'],idx);p=_safe(ind['EMA20'],np.asarray(idx)-1);a=_safe(ind['ATR14'],idx);s=np.divide(e-p,a,out=np.full(len(idx),np.nan),where=a>0)
    return s>=th if side=='BUY' else s<=-th

def _cross_recent(ind,idx,side,fast,mid,n):
    f=ind[f'EMA{fast}'];m=ind[f'EMA{mid}'];cross=np.zeros(len(f),dtype=np.int8)
    if side=='BUY':cross[1:]=((f[1:]>m[1:])&(f[:-1]<=m[:-1])&~np.isnan(f[1:])&~np.isnan(m[1:])&~np.isnan(f[:-1])&~np.isnan(m[:-1])).astype(np.int8)
    else:cross[1:]=((f[1:]<m[1:])&(f[:-1]>=m[:-1])&~np.isnan(f[1:])&~np.isnan(m[1:])&~np.isnan(f[:-1])&~np.isnan(m[:-1])).astype(np.int8)
    cs=np.r_[0,np.cumsum(cross,dtype=np.int64)];idx=np.asarray(idx,np.int64);out=np.zeros(len(idx),bool);v=_valid_idx(idx,len(f));ii=idx[v];lo=np.maximum(0,ii-n+1);out[v]=(cs[ii+1]-cs[lo])>0;return out

def ema_cross_eval(ind,idx,side,variant,active_trend=None):
    if active_trend:fast,mid=map(int,active_trend['ema_triple'][:2])
    else:fast,mid=35,70
    return _cross_recent(ind,idx,side,fast,mid,int(variant['lookback_bars']))

def higher_tf(signal_tf,steps):
    d=TF_MIN[signal_tf];xs=[x for x in LADDER if TF_MIN[x]>d];return xs[steps-1] if len(xs)>=steps else None

def mtf_context_index(context_bars,source_idx):
    comp=context_bars['first_source_index'][1:] # comp[j] is completion availability of context bar j
    return np.searchsorted(comp,np.asarray(source_idx,np.int64),side='left')-1

def mtf_eval(loader,signal_tf,source_idx,side,variant,active_trend=None):
    rule=variant['rule'];steps=2 if rule.startswith('TWO_STEPS') else 1;tf=higher_tf(signal_tf,steps)
    if tf is None:return np.zeros(len(source_idx),bool)
    bars,ind=loader(tf);ci=mtf_context_index(bars,source_idx)
    if rule.endswith('TREND_ALIGN'):
        tv=active_trend if active_trend else {'mode':'PRICE_EMA_ORDER','ema_triple':[35,70,105]};return trend_eval(ind,ci,side,tv)
    if 'RSI_DIRECTIONAL_50' in rule:
        x=_safe(ind['RSI14'],ci);return x>=50 if side=='BUY' else x<=50
    if 'CCI_SIGN_ALIGNED' in rule:
        x=_safe(ind['CCI20'],ci);return x>0 if side=='BUY' else x<0
    raise ValueError(rule)

def session_eval_ms(server_ms,variant):
    """Evaluate frozen civil-session windows on exact event signal time.
    server_ms are Darwinex source-server civil labels encoded as epoch-like ms.
    V219 byte-level binding: server civil = America/New_York civil + 7h.
    London conversion uses IANA offsets per NY civil date; DST transition Sundays are non-session.
    """
    server=np.asarray(server_ms,dtype=np.int64)
    nyms=server-np.int64(7*3600000)
    mins=((nyms//60000)%1440).astype(np.int16)
    rule=variant['rule']
    if rule=='NY_RTH': return (mins>=570)&(mins<960)
    if rule=='NY_OPEN_120': return (mins>=570)&(mins<690)
    if rule=='NY_MIDDAY': return (mins>=690)&(mins<840)
    if rule=='NY_CLOSE_120': return (mins>=840)&(mins<960)
    day=np.floor_divide(nyms,np.int64(86400000))
    uniq,inv=np.unique(day,return_inverse=True)
    diffs=np.empty(len(uniq),dtype=np.int16)
    epoch_date=_dt.date(1970,1,1)
    for i,d in enumerate(uniq):
        date=epoch_date+_dt.timedelta(days=int(d))
        ndt=_dt.datetime(date.year,date.month,date.day,12,0,tzinfo=NY)
        ldt=ndt.astimezone(LONDON)
        diffs[i]=(_dt.date(ldt.year,ldt.month,ldt.day)-date).days*1440 + ldt.hour*60+ldt.minute-720
    lmins=(mins.astype(np.int32)+diffs[inv].astype(np.int32))%1440
    london=(lmins>=480)&(lmins<990)
    if rule=='LONDON': return london
    if rule=='LONDON_NY_OVERLAP': return london&(mins>=570)&(mins<960)
    raise ValueError(rule)

class GateContext:
    def __init__(self,asset,tf,side,bar_root,ind_root,point):
        self.asset=asset;self.tf=tf;self.side=side;self.bar_root=Path(bar_root);self.ind_root=Path(ind_root);self.point=point;self._cache={}
        self.bars,self.ind=self.load(tf)
    def load(self,tf):
        if tf not in self._cache:
            b=np.load(self.bar_root/f'{self.asset}_{tf}_BID_BARS.npy',mmap_mode='r',allow_pickle=False);z=np.load(self.ind_root/f'{self.asset}_{tf}_INDICATORS.npz',allow_pickle=False);d={k:z[k] for k in z.files};d['_CLOSE']=b['close_bid'].astype(np.float64)*self.point;self._cache[tf]=(b,d)
        return self._cache[tf]
    def eval_family(self,family,variant,source_idx,bar_idx,sh,sl,boxhist,active_trend=None,session_server_ms=None):
        ii=np.asarray(bar_idx,np.int64)-1
        if family=='TREND':return trend_eval(self.ind,ii,self.side,variant)
        if family=='GEOMETRY':return geometry_eval(self.ind,ii,bar_idx,self.side,variant,sh,sl,boxhist,active_trend)
        if family=='VOLATILITY':return volatility_eval(self.ind,ii,variant)
        if family=='MOMENTUM':return momentum_eval(self.ind,ii,self.side,variant)
        if family=='SESSION':
            if session_server_ms is None: raise ValueError('SESSION_SERVER_MS_REQUIRED')
            return session_eval_ms(session_server_ms,variant)
        if family=='MULTI_TF':return mtf_eval(self.load,self.tf,source_idx,self.side,variant,active_trend)
        if family=='TREND_STRENGTH':return trend_strength_eval(self.ind,ii,self.side,variant)
        if family=='EMA_CROSS_RECENCY':return ema_cross_eval(self.ind,ii,self.side,variant,active_trend)
        raise ValueError(family)
    def eval_gates(self,gates,source_idx,bar_idx,sh,sl,boxhist,session_server_ms=None):
        out=np.ones(len(source_idx),bool);active_trend=gates.get('TREND')
        for family in sorted(gates):out &= self.eval_family(family,gates[family],source_idx,bar_idx,sh,sl,boxhist,active_trend if family in ('GEOMETRY','MULTI_TF','EMA_CROSS_RECENCY') else None,session_server_ms)
        return out
