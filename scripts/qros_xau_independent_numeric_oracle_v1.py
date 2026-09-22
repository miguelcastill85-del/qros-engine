#!/usr/bin/env python3
"""Numeric oracle uses scipy.signal lfilter, not frozen QROS indicator functions.
Only checks reproducibility of frozen formulas, not scientific alpha or execution.
"""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.signal import lfilter
ROOT=Path('/mnt/data/qros_seed0076_delta_20260922')
report={}
for tf in ['M1','M5','M15']:
 b=np.load(ROOT/'bars_full'/f'XAUUSD_{tf}_BID_BARS.npy',allow_pickle=False,mmap_mode='r');d=np.load(ROOT/'indicators_full'/f'XAUUSD_{tf}_INDICATORS.npz',allow_pickle=False)
 c=b['close_bid'].astype(np.float64)/100.;h=b['high_bid'].astype(np.float64)/100.;l=b['low_bid'].astype(np.float64)/100.
 metrics={}
 for n in [20,105,210]:
  alpha=2.0/(n+1.0);v=np.full(len(c),np.nan);seed=np.mean(c[:n]);v[n-1]=seed
  v[n:]=lfilter([alpha],[1.,-(1-alpha)],c[n:],zi=[(1-alpha)*seed])[0]
  got=d[f'EMA{n}'];err=float(np.nanmax(np.abs(got-v)))
  if err>2e-9 or not np.array_equal(np.isnan(got),np.isnan(v)):raise ValueError(f'EMA{n}_DIFFERENCE_{tf}_{err}')
  metrics[f'EMA{n}_max_abs_error']=err
 previous=np.r_[c[0],c[:-1]]
 tr=np.maximum.reduce((h-l,np.abs(h-previous),np.abs(l-previous)))
 for n in [14,50]:
  alpha=1.0/n;v=np.full(len(c),np.nan);seed=np.mean(tr[:n]);v[n-1]=seed
  v[n:]=lfilter([alpha],[1.,-(1-alpha)],tr[n:],zi=[(1-alpha)*seed])[0]
  got=d[f'ATR{n}'];err=float(np.nanmax(np.abs(got-v)))
  if err>2e-10 or not np.array_equal(np.isnan(got),np.isnan(v)):raise ValueError(f'ATR{n}_DIFFERENCE_{tf}_{err}')
  metrics[f'ATR{n}_max_abs_error']=err
 report[tf]={'bars':len(c),'oracle':'scipy.signal.lfilter independently seeded canonical EMA and Wilder TR','metrics':metrics}
out={'schema':'QROS_XAU_DEV_INDICATOR_NUMERIC_ORACLE_1.0','source_core':'SCIPY_LFILTER_NOT_QROS_INTERNAL','status':'PASS','timeframes':report,'independent_formulas_per_tf':5,'economic_pnl_read':False,'holdout_open':False}
p=ROOT/'XAU_DEV_INDICATOR_NUMERIC_ORACLE_V1.json';p.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print('PASS_SCIPY_INDEPENDENT',json.dumps(report,sort_keys=True))
