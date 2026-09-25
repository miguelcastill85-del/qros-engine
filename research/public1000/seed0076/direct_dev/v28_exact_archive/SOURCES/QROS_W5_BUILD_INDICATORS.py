import numpy as np,json,pathlib,hashlib,time,os
from qros_seed0076_indicators_v220 import compute_all
r=pathlib.Path('/mnt/data/QROS_W5_REALDATA_20260924');b=np.load(r/'XAUUSD_M1_BID_BARS.npy',mmap_mode='r',allow_pickle=False);t=time.monotonic()
h=b['high_bid'].astype(np.float64)*.01;l=b['low_bid'].astype(np.float64)*.01;c=b['close_bid'].astype(np.float64)*.01;d=compute_all(h,l,c);comp=np.full(len(b),-1,dtype=np.int64);comp[:-1]=b['first_source_index'][1:];d['completion_source_index']=comp
p=r/'XAUUSD_M1_INDICATORS.npz';np.savez(p,**d);H=hashlib.sha256();f=open(p,'rb')
for x in iter(lambda:f.read(8_388_608),b''):H.update(x)
f.close();want='f30da86f6c11b5a6573b3571ffd3c3621bbe4d51134258c89d956d6f9ab115b5';rec={'schema':'QROS_W5_M1_INDICATOR_REBUILD_V220','rows':len(b),'sha256':H.hexdigest(),'expected_old_manifest_sha256':want,'exact_match_old_sha':H.hexdigest()==want,'bytes':p.stat().st_size,'indicator_count':len(d),'elapsed_seconds':round(time.monotonic()-t,2),'holdout_open':False,'PNL_read':False};(r/'IND_REBUILD_RECEIPT.json').write_text(json.dumps(rec,indent=2,sort_keys=True)+'\n');print(json.dumps(rec),flush=True)
