#!/usr/bin/env python3
from __future__ import annotations
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

EMA_PERIODS=(5,8,9,10,13,18,20,21,26,34,35,44,50,53,55,70,79,88,89,100,105,131,140,144,158,200,210)

def ema(x,n):
    x=np.asarray(x,dtype=np.float64); out=np.full(len(x),np.nan)
    if len(x)<n:return out
    seed=float(np.mean(x[:n])); out[n-1]=seed; a=2.0/(n+1.0)
    prev=seed
    for i in range(n,len(x)):
        prev=a*x[i]+(1-a)*prev; out[i]=prev
    return out

def true_range(h,l,c):
    h=np.asarray(h,float);l=np.asarray(l,float);c=np.asarray(c,float); out=np.empty(len(c),float)
    if not len(c):return out
    out[0]=h[0]-l[0]
    pc=c[:-1]; out[1:]=np.maximum(h[1:]-l[1:],np.maximum(np.abs(h[1:]-pc),np.abs(l[1:]-pc)))
    return out

def wilder_rma(x,n,start=0):
    x=np.asarray(x,float);out=np.full(len(x),np.nan); end=start+n
    if end>len(x):return out
    seed=float(np.mean(x[start:end])); idx=end-1;out[idx]=seed;prev=seed
    for i in range(idx+1,len(x)):
        prev=(prev*(n-1)+x[i])/n;out[i]=prev
    return out

def atr(h,l,c,n=14): return wilder_rma(true_range(h,l,c),n,0)

def rsi(c,n=14):
    c=np.asarray(c,float);out=np.full(len(c),np.nan)
    if len(c)<=n:return out
    d=np.diff(c);g=np.maximum(d,0.0);loss=np.maximum(-d,0.0)
    ag=float(np.mean(g[:n]));al=float(np.mean(loss[:n]));idx=n
    def val(a,b):
        if b==0 and a==0:return 50.0
        if b==0:return 100.0
        if a==0:return 0.0
        return 100.0-100.0/(1.0+a/b)
    out[idx]=val(ag,al)
    for t in range(idx+1,len(c)):
        ag=(ag*(n-1)+g[t-1])/n;al=(al*(n-1)+loss[t-1])/n;out[t]=val(ag,al)
    return out

def roc(c,n=5):
    c=np.asarray(c,float);out=np.full(len(c),np.nan)
    if len(c)>n:
        den=c[:-n]; ok=den!=0; vals=np.full(len(den),np.nan);vals[ok]=100.0*(c[n:][ok]/den[ok]-1.0);out[n:]=vals
    return out

def cci(h,l,c,n=20):
    tp=(np.asarray(h,float)+np.asarray(l,float)+np.asarray(c,float))/3.0;out=np.full(len(tp),np.nan)
    if len(tp)<n:return out
    w=sliding_window_view(tp,n); sma=w.mean(axis=1); md=np.mean(np.abs(w-sma[:,None]),axis=1);num=tp[n-1:]-sma
    vals=np.zeros_like(num);nz=md>0;vals[nz]=num[nz]/(0.015*md[nz]);out[n-1:]=vals;return out

def stoch(h,l,c,n=14,smooth=3):
    h=np.asarray(h,float);l=np.asarray(l,float);c=np.asarray(c,float);raw=np.full(len(c),np.nan);out=np.full(len(c),np.nan)
    if len(c)<n:return raw,out
    hw=sliding_window_view(h,n);lw=sliding_window_view(l,n);hh=hw.max(axis=1);ll=lw.min(axis=1);den=hh-ll;v=np.full(len(den),50.0);nz=den>0;v[nz]=100.0*(c[n-1:][nz]-ll[nz])/den[nz];raw[n-1:]=v
    if len(v)>=smooth:
        sm=sliding_window_view(v,smooth).mean(axis=1);out[n-1+smooth-1:]=sm
    return raw,out

def adx(h,l,c,n=14):
    h=np.asarray(h,float);l=np.asarray(l,float);c=np.asarray(c,float);m=len(c);out=np.full(m,np.nan)
    if m<n:return out
    tr=true_range(h,l,c);pdm=np.zeros(m);mdm=np.zeros(m)
    up=h[1:]-h[:-1];down=l[:-1]-l[1:];pdm[1:]=np.where((up>down)&(up>0),up,0);mdm[1:]=np.where((down>up)&(down>0),down,0)
    atrn=wilder_rma(tr,n,0);sp=wilder_rma(pdm,n,0);sm=wilder_rma(mdm,n,0)
    pdi=np.full(m,np.nan);mdi=np.full(m,np.nan);valid=~np.isnan(atrn);nz=valid&(atrn>0);pdi[nz]=100*sp[nz]/atrn[nz];mdi[nz]=100*sm[nz]/atrn[nz];pdi[valid&~nz]=0;mdi[valid&~nz]=0
    dx=np.full(m,np.nan);s=pdi+mdi;v=valid&(s>0);dx[v]=100*np.abs(pdi[v]-mdi[v])/s[v];dx[valid&~v]=0
    first=n-1
    if m>=first+n:
        idx=first+n-1; seed=float(np.mean(dx[first:first+n]));out[idx]=seed;prev=seed
        for i in range(idx+1,m):prev=(prev*(n-1)+dx[i])/n;out[i]=prev
    return out

def compute_all(h,l,c):
    r={'ATR14':atr(h,l,c,14),'ATR50':atr(h,l,c,50),'RSI14':rsi(c,14),'ROC5':roc(c,5),'CCI20':cci(h,l,c,20),'ADX14':adx(h,l,c,14)}
    raw,sm=stoch(h,l,c,14,3);r['STOCH14_RAW']=raw;r['STOCH14_3']=sm
    for n in EMA_PERIODS:r[f'EMA{n}']=ema(c,n)
    return r
