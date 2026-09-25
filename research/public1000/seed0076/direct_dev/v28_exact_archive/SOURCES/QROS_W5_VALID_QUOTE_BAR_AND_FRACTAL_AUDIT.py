#!/usr/bin/env python3
"""Real 2018-2019 full tick valid-quote OHLC forensic, independent of PnL."""
import sys,json,os,hashlib,pathlib,time
import numpy as np
import numba as nb
root=pathlib.Path('/mnt/data/QROS_W5_REALDATA_20260924')
sys.path.insert(0,str(pathlib.Path('/mnt/data/qros_nonstall_v23/work/legacy/source_pins')))
from frozen_structural import structural_states
D=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);t=np.memmap(root/'XAUUSD_DEV_PACKED17_151382388.bin',dtype=D,mode='r');b=np.load(root/'XAUUSD_M1_BID_BARS.npy',mmap_mode='r',allow_pickle=False)
@nb.njit(cache=True)
def rebuild(bid,ask,first,last):
 n=len(first);h=np.empty(n,np.int32);lo=np.empty(n,np.int32);o=np.empty(n,np.int32);c=np.empty(n,np.int32);empty=0;firstbad=0;lastbad=0
 for bi in range(n):
  start=first[bi];end=last[bi];found=False;hh=-2147483647;ll=2147483647;opening=0;closing=0
  if not(bid[start]>0 and ask[start]>bid[start]):firstbad+=1
  if not(bid[end]>0 and ask[end]>bid[end]):lastbad+=1
  for j in range(start,end+1):
   if bid[j]<=0 or ask[j]<=bid[j]:continue
   v=bid[j]
   if not found:opening=v;found=True
   if v>hh:hh=v
   if v<ll:ll=v
   closing=v
  if not found:empty+=1;o[bi]=-1;h[bi]=-1;lo[bi]=-1;c[bi]=-1
  else:o[bi]=opening;h[bi]=hh;lo[bi]=ll;c[bi]=closing
 return o,h,lo,c,empty,firstbad,lastbad
start=time.monotonic();o,h,lo,c,empty,firstbad,lastbad=rebuild(t['bid'],t['ask'],b['first_source_index'],b['last_source_index']);d={x:int(np.count_nonzero(y!=b[x+'_bid'])) for x,y in [('open',o),('high',h),('low',lo),('close',c)]}
# Compare frozen original W5 structure against structure recomputed from valid quotes only.
orig=structural_states(b['high_bid'].astype(np.float64)*.01,b['low_bid'].astype(np.float64)*.01,5,0)
if empty: # no synthetic fill across a bar where no tradable bid/ask is available
 structural='UNRESOLVED_EMPTY_VALID_QUOTE_BAR';masks={}
else:
 valid=structural_states(h.astype(np.float64)*.01,lo.astype(np.float64)*.01,5,0)
 masks={'W5_buy_level_value_diff':int(np.count_nonzero(~np.isclose(orig[0],valid[0],equal_nan=True,rtol=0,atol=0))),
 'W5_sell_level_value_diff':int(np.count_nonzero(~np.isclose(orig[1],valid[1],equal_nan=True,rtol=0,atol=0))),
 'W5_buy_level_id_diff':int(np.count_nonzero(orig[2]!=valid[2])),
 'W5_sell_level_id_diff':int(np.count_nonzero(orig[3]!=valid[3]))};structural='W5_ORIGINAL_VS_VALID_QUOTES_COMPARED'
receipt={'schema':'QROS_W5_V24_FULL_REAL_TICK_BAR_CAUSALITY_GUARD_AUDIT','status':'AUDITED_FULL_REAL_TICK_NO_PNL','source_raw_SHA256':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','bar_actual_SHA256':'35a8644644daab5fc04a218d5527c3839b5248471801f8a56ebb8a71a7457f59','rows':len(t),'M1_bars':len(b),'bars_without_any_valid_tick':int(empty),'bar_first_quote_invalid_count':int(firstbad),'bar_last_quote_invalid_count':int(lastbad),'old_raw_vs_valid_quote_bar_diff':d,'W5_unsafe_structural_signal_diff':masks,'comparison_state':structural,'elapsed_seconds':round(time.monotonic()-start,3),'economics_executed':False,'holdout_open':False,'GA2_open':False,'economic_gate_open':False}
p=root/'V24_REAL_QUOTE_BAR_W5_CAUSALITY_AUDIT.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');os.replace(tmp,p);print(json.dumps(receipt),flush=True)
