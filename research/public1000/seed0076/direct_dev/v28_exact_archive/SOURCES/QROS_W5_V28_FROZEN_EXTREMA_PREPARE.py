#!/usr/bin/env python3
"""One-time no-trade computation of executable quote extrema, SHA-pinned for resumable route execution."""
import json,os,pathlib,hashlib,numpy as np,sys
R=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(R))
from qros_w5_v28_frozen_exploratory_economic_kernel import bar_valid_extrema
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert json.load(open(R/'V27_INDEPENDENT_ALL_22352_FULL10_BYTE_CLOSURE.json'))['status']=='PASS'
p=R/'V28_EXECUTABLE_BAR_EXTREMA.npz';receipt=R/'V28_EXECUTABLE_BAR_EXTREMA_RECEIPT.json'
if p.exists() and receipt.exists():
 j=json.load(open(receipt));assert sha(p)==j['sha256'];print('PASS_REUSE_SHA_VERIFIED',j);raise SystemExit
T=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);t=np.memmap(R/'XAUUSD_DEV_PACKED17_151382388.bin',dtype=T,mode='r');b=np.load(R/'XAUUSD_M1_VALID_BID_BARS_V24.npy',allow_pickle=False,mmap_mode='r')
mi,ma=bar_valid_extrema(t['bid'],t['ask'],b['first_source_index'],b['last_source_index']);assert bool(np.array_equal(mi,b['low_bid'])) and len(mi)==len(b) and np.all(mi>0) and np.all(ma>=mi)
# Independent bounded per-minute direct reference across interval edges and deterministic spread of 2048 bars.
for i in np.unique(np.r_[np.arange(25),np.arange(len(b)-25,len(b)),np.linspace(0,len(b)-1,2048,dtype=int)]):
 s,e=int(b['first_source_index'][i]),int(b['last_source_index'][i]);v=(t['bid'][s:e+1]>0)&(t['ask'][s:e+1]>t['bid'][s:e+1]);assert v.any() and int(mi[i])==int(t['bid'][s:e+1][v].min()) and int(ma[i])==int(t['ask'][s:e+1][v].max())
tmp=p.with_suffix('.npz.partial');
with open(tmp,'wb') as f:np.savez_compressed(f,minb=mi,maxa=ma)
os.replace(tmp,p);j={'schema':'QROS_W5_V28_EXECUTABLE_BAR_EXTREMA_V1','status':'PASS','sha256':sha(p),'bytes':p.stat().st_size,'bars':len(b),'independent_direct_quote_spot_checks':2098,'source_real_ticks_sha256_pin':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','NO_PNL':True};w=receipt.with_suffix('.json.partial');w.write_text(json.dumps(j,sort_keys=True,indent=2)+'\n');os.replace(w,receipt);print(json.dumps(j))
